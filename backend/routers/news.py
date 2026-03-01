from typing import Optional
import re
import json
import logging
import os

import httpx
import pathlib
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from fastapi.responses import StreamingResponse

from core.auth import require_article_admin
from data.article_generator import (
    delete_article,
    generate_article,
    get_article,
    list_articles,
    list_technology_stems,
    set_article_status,
    update_article,
)

# Directory where article JSON files live
ARTICLES_DIR = os.path.join(os.path.dirname(__file__), "data", "articles")

# Directory where cached article audio files live
ARTICLES_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "data", "articles_audio")

MAX_TTS_CHARS = 5_000

from services.tts import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_MODEL_ID,
    ELEVENLABS_OUTPUT_FORMAT,
    ELEVENLABS_VOICE_ID,
    ARTICLES_AUDIO_DIR,
    ELEVENLABS_TTS_URL,
    article_tts_text,
    get_tts_blocked_message,
    set_tts_backoff,
)
_TTS_INFLIGHT: set[str] = set()

router = APIRouter(prefix="/api", tags=["news"])
logger = logging.getLogger("tech-signals-api.news")


async def _generate_article_audio_bytes(article_id: str, article: dict) -> bytes:
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY is not configured")

    blocked_message = get_tts_blocked_message()
    if blocked_message:
        raise HTTPException(status_code=429, detail=blocked_message)

    cache_path = pathlib.Path(ARTICLES_AUDIO_DIR) / f"{article_id}.mp3"
    if cache_path.exists():
        return cache_path.read_bytes()

    if article_id in _TTS_INFLIGHT:
        raise HTTPException(status_code=429, detail="Audio generation already in progress for this article.")
    _TTS_INFLIGHT.add(article_id)

    tts_text = article_tts_text(article)
    if not tts_text:
        raise HTTPException(status_code=400, detail="Article has no readable text")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    params = {"output_format": ELEVENLABS_OUTPUT_FORMAT}
    payload = {
        "text": tts_text,
        "model_id": ELEVENLABS_MODEL_ID,
    }
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, params=params, json=payload, headers=headers)
            resp.raise_for_status()
            audio_bytes = resp.content
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        detail_lower = detail.lower()
        logger.warning("ElevenLabs API error %s: %s", exc.response.status_code if exc.response else '?', detail)
        if "detected_unusual_activity" in detail_lower or "unusual activity detected" in detail_lower:
            set_tts_backoff(
                hours=12,
                reason="ElevenLabs temporarily blocked free-tier TTS due unusual activity.",
            )
        raise HTTPException(status_code=502, detail=f"Text-to-speech provider error: {detail[:200]}")
    except httpx.HTTPError as exc:
        logger.warning("ElevenLabs request failure: %s", exc)
        raise HTTPException(status_code=502, detail="Text-to-speech provider unavailable")
    finally:
        _TTS_INFLIGHT.discard(article_id)

    if not audio_bytes:
        raise HTTPException(status_code=502, detail="ElevenLabs returned empty audio response")

    cache_path.write_bytes(audio_bytes)
    return audio_bytes


def _delete_article_audio(article_id: str) -> bool:
    cache_path = pathlib.Path(ARTICLES_AUDIO_DIR) / f"{article_id}.mp3"
    if not cache_path.exists():
        return False
    try:
        cache_path.unlink()
        return True
    except OSError:
        return False


class ArticleUpdatePayload(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    summary: str = Field(..., min_length=1, max_length=2000)
    content: str = Field(..., min_length=1, max_length=20000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: Optional[str] = Field(default=None, pattern='^(draft|published)$')

    @field_validator('tags')
    @classmethod
    def _validate_tags(cls, value: list[str]) -> list[str]:
        clean: list[str] = []
        for tag in value:
            normalized = str(tag).strip()
            if not normalized:
                continue
            if len(normalized) > 40:
                raise ValueError('Tag values must be 40 characters or fewer')
            clean.append(normalized)
        return clean


@router.get("/articles")
async def api_list_articles():
    """Public article feed (published only), newest first."""
    return list_articles(include_drafts=False)


@router.get("/admin/articles")
async def api_list_articles_admin(_admin: dict = Depends(require_article_admin)):
    """Admin article feed (includes drafts), newest first."""
    return list_articles(include_drafts=True)


@router.get("/articles/{article_id}")
async def api_get_article(article_id: str):
    """Public article detail (published only)."""
    article = get_article(article_id, include_drafts=False)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/article-stems")
async def api_article_stems(_admin: dict = Depends(require_article_admin)):
    """Return available technology stems for the generation UI."""
    return list_technology_stems()


@router.post("/articles/generate")
async def api_generate_article(
    tech: Optional[str] = Query(None, description="Technology stem (e.g. AI_Campus). Omit for roundup."),
    _admin: dict = Depends(require_article_admin),
):
    """Trigger Gemini to generate a new article. Returns the saved article."""
    try:
        article = generate_article(tech_stem=tech)
    except RuntimeError as exc:
        logger.warning("Article generation upstream error: %s", exc)
        raise HTTPException(status_code=502, detail="Article generation service unavailable")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Unexpected article generation error")
        raise HTTPException(status_code=500, detail="Article generation failed")
    return article


@router.put("/articles/{article_id}")
async def api_update_article(
    article_id: str,
    payload: ArticleUpdatePayload,
    _admin: dict = Depends(require_article_admin),
):
    """Update an existing generated article (title/summary/content/tags)."""
    updated = update_article(article_id, payload.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="Article not found")
    return updated


@router.post("/articles/{article_id}/status")
async def api_set_article_status(
    article_id: str,
    status: str = Query(..., pattern='^(draft|published)$'),
    _admin: dict = Depends(require_article_admin),
):
    """Set article publication status (draft/published)."""
    article = get_article(article_id, include_drafts=True)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    desired = str(status).strip().lower()

    # Attempt audio generation on publish, but don't block the status change
    audio_error = None
    if desired == "published":
        try:
            await _generate_article_audio_bytes(article_id, article)
        except HTTPException as exc:
            audio_error = exc.detail
            logger.warning("Audio generation failed during publish for %s: %s", article_id, audio_error)

    updated = set_article_status(article_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="Article not found")

    if desired == "draft":
        _delete_article_audio(article_id)

    if audio_error:
        updated["audioWarning"] = f"Published without audio: {audio_error}"

    return updated


@router.delete("/articles/{article_id}")
async def api_delete_article(
    article_id: str,
    _admin: dict = Depends(require_article_admin),
):
    """Delete an article permanently."""
    article = get_article(article_id, include_drafts=True)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if str(article.get("status", "draft")).strip().lower() == "published":
        raise HTTPException(status_code=400, detail="Only draft articles can be deleted. Move to draft first.")

    _delete_article_audio(article_id)
    deleted = delete_article(article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"ok": True, "id": article_id}

def load_article(article_id: str) -> dict:
    """Load an article JSON file by ID from data/articles/."""
    path = os.path.join(ARTICLES_DIR, f"{article_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Article '{article_id}' not found.")
    with open(path) as f:
        return json.load(f)

def markdown_to_plaintext(md: str) -> str:
    """Strip Markdown syntax so ElevenLabs doesn't read it aloud."""
    text = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def build_tts_text(article: dict) -> str:
    """Combine title, summary, and content into the text sent to ElevenLabs."""
    title   = article.get("title", "")
    summary = article.get("summary", "")
    content = markdown_to_plaintext(article.get("content", ""))
    full = f"{title}.\n\n{summary}.\n\n{content}"
    if len(full) > MAX_TTS_CHARS:
        full = full[:MAX_TTS_CHARS].rsplit(" ", 1)[0] + "…"
    return full

async def stream_elevenlabs(text: str):
    """Async generator that streams MP3 bytes from ElevenLabs."""
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY is not configured.")

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL_ID,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", ELEVENLABS_TTS_URL, headers=headers, json=payload) as resp:
            if resp.status_code == 429:
                body = await resp.aread()
                try:
                    detail = json.loads(body).get("detail", {})
                    msg = detail if isinstance(detail, str) else json.dumps(detail)
                except Exception:
                    msg = body.decode(errors="replace")
                raise HTTPException(status_code=429, detail=msg)

            if not resp.is_success:
                body = await resp.aread()
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"ElevenLabs error: {body.decode(errors='replace')[:300]}",
                )

            async for chunk in resp.aiter_bytes(chunk_size=4096):
                yield chunk

@router.get("/articles/{article_id}/audio")
async def api_get_article_audio(article_id: str):
    """
    Checks data/articles_audio/{article_id}.mp3 first — if it exists, serves it directly.
    Otherwise generates via ElevenLabs, saves to the cache folder, then serves it.

    Requires ELEVENLABS_KEY to be set in the environment.
    """
    os.makedirs(ARTICLES_AUDIO_DIR, exist_ok=True)
    cached_path = os.path.join(ARTICLES_AUDIO_DIR, f"{article_id}.mp3")

    # ── Serve from cache if available ─────────────────────────────────────────
    if os.path.exists(cached_path):
        def iter_cached():
            with open(cached_path, "rb") as f:
                while chunk := f.read(4096):
                    yield chunk
        return StreamingResponse(
            iter_cached(),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache"},
        )

    # ── Generate, cache, then stream ──────────────────────────────────────────
    article  = load_article(article_id)
    tts_text = build_tts_text(article)

    async def generate_and_cache():
        audio_bytes = b""
        async for chunk in stream_elevenlabs(tts_text):
            audio_bytes += chunk
            yield chunk
        with open(cached_path, "wb") as f:
            f.write(audio_bytes)

    return StreamingResponse(
        generate_and_cache(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache"},
    )
    # """Generate (and cache) TTS audio for an article via ElevenLabs."""
    # article = get_article(article_id)
    # if not article:
    #     raise HTTPException(status_code=404, detail="Article not found")
    #
    # audio_bytes = await _generate_article_audio_bytes(article_id, article)
    # return Response(content=audio_bytes, media_type="audio/mpeg")
