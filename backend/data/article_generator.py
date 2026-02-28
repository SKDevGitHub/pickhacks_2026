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


def _slug(text: str) -> str:
    """Turn arbitrary text into a filesystem / URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


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


def _call_gemini(prompt: str) -> str:
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
            "temperature": 0.7,
            "maxOutputTokens": 2048,
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


def _build_prompt(tech: dict) -> str:
    """Construct a detailed prompt for article generation."""
    name = tech["_name"]
    source = tech.get("source", "N/A")
    power = tech.get("power", tech.get("power_usage", {}))
    water = tech.get("water", tech.get("water_usage", {}))
    air = tech.get("air_pollution", tech.get("pollution", {}))

    return f"""You are a senior environmental-technology journalist writing for a
data-driven web platform called "Tech Signals" that forecasts the environmental
impact of emerging technologies.

Write a concise, engaging article (400-600 words) about the emerging technology
below. The article should cover:
1. What the technology is and why it matters
2. Its current environmental footprint (power, water, air pollution)
3. Projected growth trends and what they mean for sustainability
4. Key challenges and opportunities going forward

Use a professional yet accessible tone.  Include a compelling headline.
Return the result as valid JSON with EXACTLY these keys:
  "title"   – the headline (string)
  "summary" – a 1-2 sentence summary (string)
  "content" – the full article in Markdown (string)
  "tags"    – an array of 3-5 short keyword tags (array of strings)

Technology: {name}
Source: {source}
Power data: {json.dumps(power)}
Water data: {json.dumps(water)}
Air pollution data: {json.dumps(air)}

Respond with ONLY the JSON object — no markdown fences, no extra text."""


def _build_general_prompt(techs: list[dict]) -> str:
    """Prompt for a general roundup article covering all technologies."""
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

    return f"""You are a senior environmental-technology journalist writing for a
data-driven web platform called "Tech Signals" that forecasts the environmental
impact of emerging technologies.

Write a concise, engaging roundup article (500-700 words) surveying ALL of the
emerging technologies listed below.  Compare their environmental footprints,
highlight the biggest risks, and note any positive trends.

Use a professional yet accessible tone.  Include a compelling headline.
Return the result as valid JSON with EXACTLY these keys:
  "title"   – the headline (string)
  "summary" – a 1-2 sentence summary (string)
  "content" – the full article in Markdown (string)
  "tags"    – an array of 3-5 short keyword tags (array of strings)

Technologies:
{listing}

Respond with ONLY the JSON object — no markdown fences, no extra text."""


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
        fallback_title = first_line.lstrip("# ").strip() if first_line else "Emerging Technology Brief"
        if tech_stem:
            tech_name = tech_stem.replace("_", " ").strip().title()
            fallback_title = f"{tech_name}: Environmental Brief"
        title = fallback_title[:180]

    if not content:
        content = raw_clean or "Article content was generated but could not be formatted."

    if not summary:
        summary_source = content.replace("\n", " ").strip()
        summary = (summary_source[:220] + "…") if len(summary_source) > 220 else summary_source
        if not summary:
            summary = "A generated article on emerging technology and environmental impact."

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


def _normalize_article_record(record: dict) -> dict:
    """Normalize article records, including legacy nested JSON-in-content payloads."""
    base = {
        "id": str(record.get("id", "")).strip(),
        "title": str(record.get("title", "")).strip(),
        "summary": str(record.get("summary", "")).strip(),
        "content": str(record.get("content", "")).strip(),
        "tags": record.get("tags", []),
        "generatedAt": str(record.get("generatedAt", "")).strip(),
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
        "generatedAt": datetime.now(timezone.utc).isoformat(),
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

    if tech_stem:
        if not techs:
            raise ValueError(f"No technology found for stem '{tech_stem}'")
        prompt = _build_prompt(techs[0])
    else:
        if not techs:
            techs = _load_tech_context()  # load all
        prompt = _build_general_prompt(techs)

    raw = _call_gemini(prompt)

    parsed: dict
    try:
        parsed = _parse_gemini_json(raw)
    except RuntimeError:
        parsed = {}

    article_payload = _coerce_article_shape(parsed, raw, tech_stem)
    article = _save_article(article_payload)

    # Attach the technology reference if applicable
    if tech_stem:
        article["technologyStem"] = tech_stem
        # re-save with the extra field
        _write_article_record(article)

    return article


def list_articles() -> list[dict]:
    """Return all saved articles, newest first."""
    articles: list[dict] = []
    if not ARTICLES_DIR.exists():
        return articles

    for path in sorted(ARTICLES_DIR.glob("*.json"), reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            normalized = _normalize_article_record(raw)
            articles.append(normalized)

            if normalized != raw:
                path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            continue

    # Sort by generatedAt descending
    articles.sort(key=lambda a: a.get("generatedAt", ""), reverse=True)
    return articles


def get_article(article_id: str) -> Optional[dict]:
    """Load a single article by its ID."""
    filepath = ARTICLES_DIR / f"{article_id}.json"
    if not filepath.exists():
        return None
    try:
        raw = json.loads(filepath.read_text(encoding="utf-8"))
        normalized = _normalize_article_record(raw)
        if normalized != raw:
            filepath.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
        return normalized
    except (OSError, json.JSONDecodeError):
        return None


def update_article(article_id: str, updates: dict) -> Optional[dict]:
    """Update editable article fields and persist changes."""
    existing = get_article(article_id)
    if not existing:
        return None

    merged = {
        **existing,
        "title": str(updates.get("title", existing.get("title", ""))).strip(),
        "summary": str(updates.get("summary", existing.get("summary", ""))).strip(),
        "content": str(updates.get("content", existing.get("content", ""))).strip(),
        "tags": updates.get("tags", existing.get("tags", [])),
    }

    normalized = _normalize_article_record(merged)
    if not normalized.get("title"):
        normalized["title"] = "Untitled Article"
    if not normalized.get("summary"):
        normalized["summary"] = "No summary provided."
    if not normalized.get("content"):
        normalized["content"] = "No content provided."

    _write_article_record(normalized)
    return normalized


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
