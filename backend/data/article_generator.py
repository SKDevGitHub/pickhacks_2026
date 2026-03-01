"""
Article generator using the Google Gemini API.

Reads emerging-technology metadata from data/emergent_tech/ and uses Gemini
to produce short research-style articles.  Articles are persisted as individual
JSON files in data/articles/.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[2]
ARTICLES_DIR = ROOT_DIR / "data" / "articles"
EMERGENT_TECH_DIR = ROOT_DIR / "data" / "emergent_tech"

# Ensure the articles directory exists
ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

# ── Gemini REST config ─────────────────────────────────────────────────────
load_dotenv()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
SOURCE_MAX_AGE_YEARS = int(os.getenv("ARTICLE_SOURCE_MAX_AGE_YEARS", "6"))
MAX_VALIDATED_SOURCES = int(os.getenv("ARTICLE_MAX_VALIDATED_SOURCES", "4"))
MIN_VALIDATED_SOURCES = int(os.getenv("ARTICLE_MIN_VALIDATED_SOURCES", "1"))
HTTP_HEADERS = {
    "User-Agent": "TechSignalsArticleBot/1.0 (contact: local-dev)",
}


def _slug(text: str) -> str:
    """Turn arbitrary text into a filesystem / URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def _query_tokens(text: str) -> set[str]:
    keep_short = {"ai", "ml", "hpc"}
    return {
        t for t in re.findall(r"[a-z0-9]+", str(text).lower())
        if len(t) > 2 or t in keep_short
    }


def _extract_date_parts(value) -> Optional[tuple[int, int, int]]:
    if not isinstance(value, list) or not value:
        return None
    year = int(value[0]) if len(value) >= 1 else 1
    month = int(value[1]) if len(value) >= 2 else 1
    day = int(value[2]) if len(value) >= 3 else 1
    month = max(1, min(month, 12))
    day = max(1, min(day, 28))
    return year, month, day


def _source_is_recent(published_at: str) -> bool:
    if not published_at:
        return False
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    age_years = (now - dt).days / 365.25
    return age_years <= SOURCE_MAX_AGE_YEARS


def _url_exists(url: str) -> bool:
    if not url:
        return False
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True, headers=HTTP_HEADERS) as client:
            try:
                head = client.head(url)
                if head.status_code < 400:
                    return True
            except httpx.HTTPError:
                pass
            get = client.get(url)
            return get.status_code < 400
    except httpx.HTTPError:
        return False


def _discover_validated_sources(tech_stem: Optional[str], techs: list[dict]) -> list[dict]:
    """Discover and validate relevant, recent sources via Crossref.

    Returns sources with fields: title, url, publishedAt, publisher.
    """
    query_name = tech_stem.replace("_", " ") if tech_stem else "emerging technologies environmental impact"
    if techs and techs[0].get("_name"):
        query_name = str(techs[0].get("_name")) if tech_stem else query_name
    if tech_stem:
        query_name = f"{query_name} ai data center energy water environmental impact"

    tokens = _query_tokens(query_name)
    primary_tokens = _query_tokens((tech_stem or "").replace("_", " "))
    impact_tokens = {
        "energy", "water", "emission", "carbon", "pollution", "data",
        "center", "computing", "hpc", "training", "sustainability",
        "electricity", "cooling",
    }
    current_year = datetime.now(timezone.utc).year
    from_pub_date = f"{max(2000, current_year - SOURCE_MAX_AGE_YEARS)}-01-01"

    params = {
        "query.title": query_name,
        "rows": 12,
        "sort": "published",
        "order": "desc",
        "filter": f"from-pub-date:{from_pub_date}",
    }

    validated: list[dict] = []
    try:
        resp = httpx.get("https://api.crossref.org/works", params=params, timeout=12.0, headers=HTTP_HEADERS)
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
    except httpx.HTTPError:
        items = []

    for item in items:
        titles = item.get("title") or []
        title = str(titles[0]).strip() if titles else ""
        if not title:
            continue

        title_tokens = _query_tokens(title)
        overlap = len(tokens & title_tokens)
        if tech_stem:
            has_primary = bool(title_tokens & primary_tokens)
            has_ai_phrase = "artificial intelligence" in title.lower() or " ai " in f" {title.lower()} "
            has_impact = bool(title_tokens & impact_tokens)
            if not ((has_primary or has_ai_phrase) and has_impact):
                continue
        else:
            if overlap < 2 and tokens:
                continue

        date_parts = None
        for key in ("published-print", "published-online", "issued", "created"):
            parts = item.get(key, {}).get("date-parts", [])
            if parts and parts[0]:
                date_parts = _extract_date_parts(parts[0])
                if date_parts:
                    break

        published_at = ""
        if date_parts:
            y, m, d = date_parts
            published_at = f"{y:04d}-{m:02d}-{d:02d}T00:00:00+00:00"
        if not _source_is_recent(published_at):
            continue

        doi = str(item.get("DOI", "")).strip()
        url = str(item.get("URL", "")).strip()
        if doi:
            url = f"https://doi.org/{doi}"
        if not _url_exists(url):
            continue

        validated.append({
            "title": title,
            "url": url,
            "publishedAt": published_at,
            "publisher": str(item.get("publisher", "")).strip(),
            "sourceType": "crossref",
        })
        if len(validated) >= MAX_VALIDATED_SOURCES:
            break

    if validated:
        return validated

    # Secondary fallback: OpenAlex
    try:
        oa_resp = httpx.get(
            "https://api.openalex.org/works",
            params={
                "search": query_name,
                "per-page": 15,
                "filter": f"from_publication_date:{from_pub_date}",
            },
            timeout=12.0,
            headers=HTTP_HEADERS,
        )
        oa_resp.raise_for_status()
        oa_results = oa_resp.json().get("results", [])
    except httpx.HTTPError:
        oa_results = []

    for item in oa_results:
        title = str(item.get("display_name", "")).strip()
        if not title:
            continue

        title_tokens = _query_tokens(title)
        overlap = len(tokens & title_tokens)
        if tech_stem:
            has_primary = bool(title_tokens & primary_tokens)
            has_ai_phrase = "artificial intelligence" in title.lower() or " ai " in f" {title.lower()} "
            has_impact = bool(title_tokens & impact_tokens)
            if not ((has_primary or has_ai_phrase) and has_impact):
                continue
        else:
            if overlap < 2 and tokens:
                continue

        publication_date = str(item.get("publication_date", "")).strip()
        published_at = f"{publication_date}T00:00:00+00:00" if publication_date else ""
        if not _source_is_recent(published_at):
            continue

        location = item.get("primary_location") or {}
        landing = str(location.get("landing_page_url") or "").strip()
        doi = str(item.get("doi") or "").strip()
        url = landing or doi
        if not url:
            continue
        if not _url_exists(url):
            continue

        validated.append({
            "title": title,
            "url": url,
            "publishedAt": published_at,
            "publisher": str((location.get("source") or {}).get("display_name", "")).strip(),
            "sourceType": "openalex",
        })
        if len(validated) >= MAX_VALIDATED_SOURCES:
            break

    if validated:
        return validated

    return []


def _find_free_image(query: str) -> Optional[dict]:
    """Find a free licensed image from Wikimedia Commons (non-AI-generated)."""
    search_query = f"{query} environmental technology"
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": search_query,
        "gsrnamespace": 6,
        "gsrlimit": 8,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
    }
    commons_headers = {
        "User-Agent": "TechSignalsArticleBot/1.0 (contact: local-dev)",
    }
    try:
        resp = httpx.get(
            "https://commons.wikimedia.org/w/api.php",
            params=params,
            headers=commons_headers,
            timeout=12.0,
        )
        resp.raise_for_status()
        pages = (resp.json().get("query", {}).get("pages", {}) or {}).values()
    except httpx.HTTPError:
        pages = []

    for page in pages:
        info_list = page.get("imageinfo") or []
        if not info_list:
            continue
        info = info_list[0]
        url = str(info.get("url", "")).strip()
        description_url = str(info.get("descriptionurl", "")).strip()
        meta = info.get("extmetadata", {}) or {}
        license_name = str((meta.get("LicenseShortName") or {}).get("value", "")).strip()
        artist = str((meta.get("Artist") or {}).get("value", "")).strip()
        artist = re.sub(r"<[^>]+>", "", artist).strip()
        if not url or not description_url:
            continue
        if not license_name:
            continue
        if "fair" in license_name.lower() or "non-free" in license_name.lower():
            continue
        return {
            "url": url,
            "sourcePage": description_url,
            "license": license_name,
            "author": artist,
            "provider": "Wikimedia Commons",
        }

    # Fallback: Openverse (free-license search index)
    try:
        ov_resp = httpx.get(
            "https://api.openverse.org/v1/images/",
            params={
                "q": query,
                "license_type": "all",
                "page_size": 10,
            },
            timeout=12.0,
        )
        ov_resp.raise_for_status()
        results = ov_resp.json().get("results", [])
    except httpx.HTTPError:
        results = []

    for item in results:
        img_url = str(item.get("url") or item.get("thumbnail") or "").strip()
        page_url = str(item.get("foreign_landing_url") or "").strip()
        license_name = str(item.get("license") or "").strip()
        creator = str(item.get("creator") or "").strip()
        if not img_url or not page_url or not license_name:
            continue
        if "all-rights-reserved" in license_name.lower():
            continue
        return {
            "url": img_url,
            "sourcePage": page_url,
            "license": license_name,
            "author": creator,
            "provider": "Openverse",
        }

    return None


def _load_tech_context(tech_stem: Optional[str] = None) -> list[dict]:
    """Load technology JSON files to supply as context to the LLM."""
    techs: list[dict] = []
    if not EMERGENT_TECH_DIR.exists():
        return techs

    for path in sorted(EMERGENT_TECH_DIR.glob("*.json")):
        if tech_stem and path.stem.lower() != tech_stem.lower():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_stem"] = path.stem
            payload["_name"] = path.stem.replace("_", " ").strip().title()
            techs.append(payload)
        except (OSError, json.JSONDecodeError):
            continue
    return techs


def _call_gemini(prompt: str, temperature: float = 0.45, max_output_tokens: int = 2048) -> str:
    """Send a prompt to the Gemini REST API and return the text response."""
    gemini_api_key = os.getenv("GEMINI_KEY", "").strip()

    if not gemini_api_key:
        raise RuntimeError(
            "GEMINI_KEY is not set. Add it to backend/.env "
            "(e.g. GEMINI_KEY=AIza…) and restart the server."
        )

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }

    try:
        resp = httpx.post(
            GEMINI_URL,
            params={"key": gemini_api_key},
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        raise RuntimeError(f"Gemini API returned {exc.response.status_code if exc.response is not None else 'an error'}: {detail}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Gemini API request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini API returned invalid JSON response payload.") from exc

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


def _build_prompt(tech: dict, sources: list[dict]) -> str:
    """Construct a structured first-pass prompt for single-technology generation."""
    name = tech["_name"]
    source = tech.get("source", "N/A")
    power = tech.get("power", tech.get("power_usage", {}))
    water = tech.get("water", tech.get("water_usage", {}))
    air = tech.get("air_pollution", tech.get("pollution", {}))

    source_listing = "\n".join(
        f"- [{idx+1}] {s.get('title', '')} | {s.get('url', '')} | {s.get('publishedAt', '')}"
        for idx, s in enumerate(sources)
    )

    return f"""You are a senior cleantech editor writing for Chartr AI.

TASK
Write one high-quality article about this technology using concrete numbers from the provided data.

QUALITY REQUIREMENTS
- 500-750 words in the Markdown content field.
- Use at least 4 Markdown H2 sections (##).
- Include at least 4 numeric facts from the data (indices, deltas, demand, projections, etc.).
- Be specific and analytical; avoid generic hype language.
- Include both downside risks and practical opportunities.
- Ground claims in the validated sources list below and include source markers like [1], [2] in markdown.
- Do NOT include JSON inside the markdown content.

REQUIRED OUTPUT SCHEMA (valid JSON only)
{{
    "title": "string",
    "summary": "string (1-2 sentences, concrete)",
    "content": "markdown string",
    "tags": ["3-6 short strings"]
}}

TECHNOLOGY CONTEXT
Technology: {name}
Source: {source}
Power data: {json.dumps(power)}
Water data: {json.dumps(water)}
Air pollution data: {json.dumps(air)}

VALIDATED SOURCES (EXISTENCE + RELEVANCE + RECENCY CHECKED)
{source_listing}

Respond with ONLY the JSON object."""


def _build_general_prompt(techs: list[dict], sources: list[dict]) -> str:
    """Structured first-pass prompt for a multi-technology roundup."""
    tech_summaries = []
    for t in techs:
        name = t["_name"]
        power = t.get("power", t.get("power_usage", {}))
        water = t.get("water", t.get("water_usage", {}))
        air = t.get("air_pollution", t.get("pollution", {}))
        tech_summaries.append(
            f"- {name}: power={json.dumps(power)}, water={json.dumps(water)}, pollution={json.dumps(air)}"
        )

    listing = "\n".join(tech_summaries)

    source_listing = "\n".join(
        f"- [{idx+1}] {s.get('title', '')} | {s.get('url', '')} | {s.get('publishedAt', '')}"
        for idx, s in enumerate(sources)
    )

    return f"""You are a senior cleantech editor writing for Chartr AI.

TASK
Write a comparative roundup across ALL technologies below.

QUALITY REQUIREMENTS
- 600-900 words in the Markdown content field.
- Use at least 5 Markdown H2 sections (##).
- Include at least 6 numeric facts from the provided data.
- Rank or clearly compare major tradeoffs across power, water, and air impacts.
- Include policy/operations implications and not just technical description.
- Ground claims in the validated sources list below and include source markers like [1], [2] in markdown.
- Do NOT include JSON inside the markdown content.

REQUIRED OUTPUT SCHEMA (valid JSON only)
{{
    "title": "string",
    "summary": "string (1-2 sentences, concrete)",
    "content": "markdown string",
    "tags": ["3-6 short strings"]
}}

Technologies:
{listing}

VALIDATED SOURCES (EXISTENCE + RELEVANCE + RECENCY CHECKED)
{source_listing}

Respond with ONLY the JSON object."""


def _parse_gemini_json(raw: str) -> dict:
    """Best-effort extraction of JSON from the Gemini response."""
    # Strip markdown fences if Gemini added them anyway
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise RuntimeError("Gemini response could not be parsed as article JSON.")


def _coerce_article_shape(parsed: dict, raw: str, tech_stem: Optional[str] = None) -> dict:
    """Ensure article payload always has required keys and sensible defaults."""
    title = str(parsed.get("title", "")).strip()
    summary = str(parsed.get("summary", "")).strip()
    content = str(parsed.get("content", "")).strip()
    tags = parsed.get("tags", [])

    if not isinstance(tags, list):
        tags = []
    tags = [str(tag).strip() for tag in tags if str(tag).strip()]

    raw_clean = raw.strip()
    raw_lines = [line.strip() for line in raw_clean.splitlines() if line.strip()]
    first_line = raw_lines[0] if raw_lines else ""

    if not title:
        title = _clean_json_field_artifacts(_heuristic_field_from_blob(raw_clean, "title"), "title")
    if not summary:
        summary = _clean_json_field_artifacts(_heuristic_field_from_blob(raw_clean, "summary"), "summary")
    if not content:
        content = _clean_json_field_artifacts(_heuristic_field_from_blob(raw_clean, "content"), "content")

    if not title:
        fallback_title = first_line.lstrip("# ").strip() if first_line else "Emerging Technology Brief"
        if tech_stem:
            tech_name = tech_stem.replace("_", " ").strip().title()
            fallback_title = f"{tech_name}: Environmental Brief"
        title = fallback_title[:180]
    title = _clean_json_field_artifacts(title, "title")

    if not content:
        content = raw_clean or "Article content was generated but could not be formatted."
    content = _clean_json_field_artifacts(content, "content")

    if not summary:
        summary_source = content.replace("\n", " ").strip()
        summary = (summary_source[:220] + "…") if len(summary_source) > 220 else summary_source
        if not summary:
            summary = "A generated article on emerging technology and environmental impact."
    summary = _clean_json_field_artifacts(summary, "summary")

    if not tags:
        tags = ["emerging-tech", "sustainability", "forecast"]
        if tech_stem:
            tags.insert(0, tech_stem.replace("_", "-").lower())

    return {
        "title": title,
        "summary": summary,
        "content": content,
        "tags": tags[:6],
    }


def _clean_json_field_artifacts(value: str, field: str) -> str:
    """Remove JSON spillover fragments from extracted field text."""
    text = str(value or "").strip()
    if not text:
        return ""

    split_patterns = {
        "title": [r'"\s*,\s*"summary"\s*:', r'"\s*,\s*"content"\s*:', r'"\s*,\s*"tags"\s*:'],
        "summary": [r'"\s*,\s*"content"\s*:', r'"\s*,\s*"tags"\s*:'],
        "content": [r'"\s*,\s*"tags"\s*:', r'"\s*\}\s*$'],
    }

    for pattern in split_patterns.get(field, []):
        parts = re.split(pattern, text, maxsplit=1)
        if parts:
            text = parts[0]

    text = text.strip().strip('"').strip().strip("`")
    return text


def _article_quality_issues(article: dict, is_roundup: bool) -> list[str]:
    """Return quality issues found in an article payload."""
    issues: list[str] = []

    title = str(article.get("title", "")).strip()
    summary = str(article.get("summary", "")).strip()
    content = str(article.get("content", "")).strip()

    word_count = len(re.findall(r"\b[\w'-]+\b", content))
    h2_count = len(re.findall(r"^##\s+", content, flags=re.MULTILINE))
    numeric_count = len(re.findall(r"\d+(?:\.\d+)?", content))

    min_words = 600 if is_roundup else 500
    min_h2 = 5 if is_roundup else 4
    min_numeric = 6 if is_roundup else 4

    if not title or len(title) < 20:
        issues.append("Title is too short or missing.")
    if len(title) > 180:
        issues.append("Title is too long.")
    if not summary or len(summary) < 40:
        issues.append("Summary is too short.")
    if word_count < min_words:
        issues.append(f"Content is too short ({word_count} words); need at least {min_words}.")
    if h2_count < min_h2:
        issues.append(f"Content needs at least {min_h2} Markdown H2 sections (##).")
    if numeric_count < min_numeric:
        issues.append(f"Content needs at least {min_numeric} concrete numeric facts.")
    if "{" in content and '"title"' in content:
        issues.append("Content appears to include nested JSON; content must be markdown only.")

    return issues


def _build_rewrite_prompt(
    article: dict,
    issues: list[str],
    tech_stem: Optional[str],
    techs: list[dict],
    sources: list[dict],
) -> str:
    """Build a second-pass rewrite prompt to repair quality problems."""
    is_roundup = tech_stem is None

    if tech_stem and techs:
        tech = techs[0]
        context = (
            f"Technology: {tech.get('_name', tech_stem)}\n"
            f"Source: {tech.get('source', 'N/A')}\n"
            f"Power data: {json.dumps(tech.get('power', tech.get('power_usage', {})))}\n"
            f"Water data: {json.dumps(tech.get('water', tech.get('water_usage', {})))}\n"
            f"Air data: {json.dumps(tech.get('air_pollution', tech.get('pollution', {})))}"
        )
    else:
        context_lines: list[str] = []
        for tech in techs:
            context_lines.append(
                f"- {tech.get('_name', 'Unknown')}: "
                f"power={json.dumps(tech.get('power', tech.get('power_usage', {})))}, "
                f"water={json.dumps(tech.get('water', tech.get('water_usage', {})))}, "
                f"air={json.dumps(tech.get('air_pollution', tech.get('pollution', {})))}"
            )
        context = "\n".join(context_lines)

    issues_block = "\n".join(f"- {issue}" for issue in issues)
    source_listing = "\n".join(
        f"- [{idx+1}] {s.get('title', '')} | {s.get('url', '')} | {s.get('publishedAt', '')}"
        for idx, s in enumerate(sources)
    )
    min_words = 600 if is_roundup else 500
    min_h2 = 5 if is_roundup else 4
    min_numeric = 6 if is_roundup else 4

    return f"""You are a senior editor. Rewrite the draft article below to fix quality issues.

QUALITY ISSUES TO FIX
{issues_block}

HARD REQUIREMENTS
- Markdown content must be at least {min_words} words.
- Must include at least {min_h2} H2 sections using ## headings.
- Must include at least {min_numeric} concrete numeric facts from context.
- Keep the writing clear, specific, and decision-useful.
- Keep summary strictly aligned with validated sources and context.
- Use source markers like [1], [2] in markdown where claims are made.
- Do not output nested JSON in content.

CONTEXT
{context}

VALIDATED SOURCES
{source_listing}

DRAFT ARTICLE JSON
{json.dumps(article, ensure_ascii=False)}

Return valid JSON ONLY with keys: title, summary, content, tags.
"""


def _try_parse_nested_article_blob(text: str) -> Optional[dict]:
    """Try to parse a nested article JSON blob embedded in summary/content."""
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    if "\"title\"" not in cleaned and "\"content\"" not in cleaned:
        return None

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None

    candidate = match.group(0)
    try:
        payload = json.loads(candidate)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        return None
    return None


def _heuristic_field_from_blob(text: str, field: str) -> str:
    """Extract a quoted JSON-like field from possibly truncated blob text."""
    if not text:
        return ""

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    key_marker = f'"{field}"'
    key_idx = cleaned.find(key_marker)
    if key_idx < 0:
        return ""

    colon_idx = cleaned.find(":", key_idx)
    if colon_idx < 0:
        return ""

    value_start = cleaned.find('"', colon_idx)
    if value_start < 0:
        return ""

    value_start += 1

    if field == "content":
        value = cleaned[value_start:]
    else:
        next_key_patterns = ['",\n  "', '",\n"', '",\r\n  "', '","']
        end_idx = -1
        for pattern in next_key_patterns:
            candidate = cleaned.find(pattern, value_start)
            if candidate >= 0:
                end_idx = candidate
                break
        value = cleaned[value_start:] if end_idx < 0 else cleaned[value_start:end_idx]

    value = value.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
    value = value.strip().strip('"').strip().strip("`")
    return value


def _extract_markdown_content(content: str) -> str:
    """Normalize content so stored article content is Markdown text, not nested JSON."""
    raw = str(content or "").strip()
    if not raw:
        return ""

    nested = _try_parse_nested_article_blob(raw)
    if isinstance(nested, dict):
        nested_content = str(nested.get("content", "")).strip()
        if nested_content:
            return nested_content

    # Heuristic recovery if nested JSON is malformed but includes "content"
    heuristic = _heuristic_field_from_blob(raw, "content")
    if heuristic:
        return heuristic

    return raw


def _normalize_sources(sources) -> list[dict]:
    if not isinstance(sources, list):
        return []
    normalized: list[dict] = []
    for src in sources:
        if not isinstance(src, dict):
            continue
        title = str(src.get("title", "")).strip()
        url = str(src.get("url", "")).strip()
        if not title:
            continue
        normalized.append({
            "title": title,
            "url": url,
            "publishedAt": str(src.get("publishedAt", "")).strip(),
            "publisher": str(src.get("publisher", "")).strip(),
            "sourceType": str(src.get("sourceType", "")).strip(),
        })
    return normalized[:8]


def _normalize_image(image) -> Optional[dict]:
    if not isinstance(image, dict):
        return None
    url = str(image.get("url", "")).strip()
    if not url:
        return None
    return {
        "url": url,
        "sourcePage": str(image.get("sourcePage", "")).strip(),
        "license": str(image.get("license", "")).strip(),
        "author": str(image.get("author", "")).strip(),
        "provider": str(image.get("provider", "")).strip(),
    }


def _normalize_article_record(record: dict) -> dict:
    """Normalize article records, including legacy nested JSON-in-content payloads."""
    raw_status = str(record.get("status", "published")).strip().lower()
    normalized_status = raw_status if raw_status in {"draft", "published"} else "published"

    base = {
        "id": str(record.get("id", "")).strip(),
        "title": str(record.get("title", "")).strip(),
        "summary": str(record.get("summary", "")).strip(),
        "content": _extract_markdown_content(record.get("content", "")),
        "tags": record.get("tags", []),
        "generatedAt": str(record.get("generatedAt", "")).strip(),
        "status": normalized_status,
        "sources": _normalize_sources(record.get("sources", [])),
        "image": _normalize_image(record.get("image")),
    }

    nested = _try_parse_nested_article_blob(base["content"]) or _try_parse_nested_article_blob(base["summary"])
    if nested:
        coerced = _coerce_article_shape(nested, base["content"] or base["summary"])
        base["title"] = coerced["title"]
        base["summary"] = coerced["summary"]
        base["content"] = coerced["content"]
        base["tags"] = coerced["tags"]
    else:
        blob_source = base["content"] if "\"title\"" in base["content"] else base["summary"]
        recovered_title = _heuristic_field_from_blob(blob_source, "title")
        recovered_summary = _heuristic_field_from_blob(blob_source, "summary")
        recovered_content = _heuristic_field_from_blob(blob_source, "content")

        if recovered_title:
            base["title"] = recovered_title
        if recovered_summary:
            base["summary"] = recovered_summary
        if recovered_content:
            base["content"] = recovered_content

    if not isinstance(base["tags"], list):
        base["tags"] = []
    base["tags"] = [str(tag).strip() for tag in base["tags"] if str(tag).strip()]
    base["title"] = _clean_json_field_artifacts(base.get("title", ""), "title")
    base["summary"] = _clean_json_field_artifacts(base.get("summary", ""), "summary")
    base["content"] = _clean_json_field_artifacts(base.get("content", ""), "content")

    return {
        key: value
        for key, value in {
            **record,
            **base,
        }.items()
        if value is not None
    }


def _write_article_record(record: dict) -> None:
    filepath = ARTICLES_DIR / f"{record['id']}.json"
    filepath.write_text(json.dumps(record, indent=2), encoding="utf-8")


def _save_article(article: dict) -> dict:
    """Persist article to data/articles/ and return it."""
    slug = _slug(article["title"])
    article_id = f"{slug}-{int(time.time())}"
    record = {
        "id": article_id,
        "title": article["title"],
        "summary": article["summary"],
        "content": article["content"],
        "tags": article.get("tags", []),
        "sources": article.get("sources", []),
        "image": article.get("image"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "draft",
    }

    normalized = _normalize_article_record(record)
    _write_article_record(normalized)
    return normalized


# ── Public API ─────────────────────────────────────────────────────────────

def generate_article(tech_stem: Optional[str] = None) -> dict:
    """
    Generate a single article.

    Parameters
    ----------
    tech_stem : str or None
        If given, generate an article about that specific technology
        (filename stem from data/emergent_tech, e.g. "AI_Campus").
        If None, generate a general roundup article.

    Returns the saved article dict.
    """
    techs = _load_tech_context(tech_stem)
    validated_sources = _discover_validated_sources(tech_stem, techs)
    image_query = tech_stem.replace("_", " ") if tech_stem else "emerging technology sustainability"
    free_image = _find_free_image(image_query)

    # If no external sources found, fall back to the tech's own source URL
    if not validated_sources and techs:
        for t in techs:
            src_url = t.get("source", "")
            if src_url:
                validated_sources.append({
                    "title": t.get("_name", tech_stem or "Technology"),
                    "url": src_url,
                    "publishedAt": "",
                    "publisher": "",
                    "sourceType": "tech_config",
                })
                break

    if len(validated_sources) < MIN_VALIDATED_SOURCES:
        target = tech_stem.replace("_", " ") if tech_stem else "general roundup"
        raise ValueError(
            f"Insufficient validated sources for '{target}'. "
            f"Found {len(validated_sources)}, require at least {MIN_VALIDATED_SOURCES}."
        )

    if tech_stem:
        if not techs:
            raise ValueError(f"No technology found for stem '{tech_stem}'")
        prompt = _build_prompt(techs[0], validated_sources)
    else:
        if not techs:
            techs = _load_tech_context()  # load all
        prompt = _build_general_prompt(techs, validated_sources)

    raw = _call_gemini(prompt, temperature=0.4, max_output_tokens=2300)

    parsed: dict
    try:
        parsed = _parse_gemini_json(raw)
    except RuntimeError:
        parsed = {}

    article_payload = _coerce_article_shape(parsed, raw, tech_stem)
    is_roundup = tech_stem is None
    issues = _article_quality_issues(article_payload, is_roundup=is_roundup)

    if issues:
        rewrite_prompt = _build_rewrite_prompt(article_payload, issues, tech_stem, techs, validated_sources)
        rewrite_raw = _call_gemini(rewrite_prompt, temperature=0.25, max_output_tokens=2600)
        try:
            rewrite_parsed = _parse_gemini_json(rewrite_raw)
        except RuntimeError:
            rewrite_parsed = {}

        rewritten_payload = _coerce_article_shape(rewrite_parsed, rewrite_raw, tech_stem)
        rewritten_issues = _article_quality_issues(rewritten_payload, is_roundup=is_roundup)
        if len(rewritten_issues) <= len(issues):
            article_payload = rewritten_payload

    article_payload["sources"] = validated_sources
    article_payload["image"] = free_image

    article = _save_article(article_payload)

    # Attach the technology reference if applicable
    if tech_stem:
        article["technologyStem"] = tech_stem
        # re-save with the extra field
        _write_article_record(article)

    return article


def list_articles(include_drafts: bool = False) -> list[dict]:
    """Return saved articles, newest first.

    include_drafts=False returns only published articles for public surfaces.
    """
    articles: list[dict] = []
    if not ARTICLES_DIR.exists():
        return articles

    for path in sorted(ARTICLES_DIR.glob("*.json"), reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            normalized = _normalize_article_record(raw)
            if include_drafts or normalized.get("status") == "published":
                articles.append(normalized)

            if normalized != raw:
                path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            continue

    # Sort by generatedAt descending
    articles.sort(key=lambda a: a.get("generatedAt", ""), reverse=True)
    return articles


def get_article(article_id: str, include_drafts: bool = False) -> Optional[dict]:
    """Load a single article by ID.

    include_drafts=False hides drafts from public routes.
    """
    filepath = ARTICLES_DIR / f"{article_id}.json"
    if not filepath.exists():
        return None
    try:
        raw = json.loads(filepath.read_text(encoding="utf-8"))
        normalized = _normalize_article_record(raw)
        if normalized != raw:
            filepath.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        if not include_drafts and normalized.get("status") != "published":
            return None
        return normalized
    except (OSError, json.JSONDecodeError):
        return None


def update_article(article_id: str, updates: dict) -> Optional[dict]:
    """Update editable article fields and persist changes."""
    existing = get_article(article_id, include_drafts=True)
    if not existing:
        return None

    merged = {
        **existing,
        "title": str(updates.get("title", existing.get("title", ""))).strip(),
        "summary": str(updates.get("summary", existing.get("summary", ""))).strip(),
        "content": str(updates.get("content", existing.get("content", ""))).strip(),
        "tags": updates.get("tags", existing.get("tags", [])),
    }

    if "status" in updates:
        next_status = str(updates.get("status", existing.get("status", "draft"))).strip().lower()
        merged["status"] = next_status if next_status in {"draft", "published"} else existing.get("status", "draft")

    normalized = _normalize_article_record(merged)
    if not normalized.get("title"):
        normalized["title"] = "Untitled Article"
    if not normalized.get("summary"):
        normalized["summary"] = "No summary provided."
    if not normalized.get("content"):
        normalized["content"] = "No content provided."

    _write_article_record(normalized)
    return normalized


def set_article_status(article_id: str, status: str) -> Optional[dict]:
    """Set article publication status to draft/published."""
    desired = str(status or "").strip().lower()
    if desired not in {"draft", "published"}:
        return None
    return update_article(article_id, {"status": desired})


def delete_article(article_id: str) -> bool:
    """Delete an article JSON file by ID."""
    filepath = ARTICLES_DIR / f"{article_id}.json"
    if not filepath.exists():
        return False
    try:
        filepath.unlink()
        return True
    except OSError:
        return False


def list_technology_stems() -> list[dict]:
    """Return available technology stems for the admin UI."""
    stems: list[dict] = []
    if not EMERGENT_TECH_DIR.exists():
        return stems
    for path in sorted(EMERGENT_TECH_DIR.glob("*.json")):
        stems.append({
            "stem": path.stem,
            "name": path.stem.replace("_", " ").strip().title(),
        })
    return stems
