from typing import Optional
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from fastapi.responses import Response

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
from services.tts import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_MODEL_ID,
    ELEVENLABS_OUTPUT_FORMAT,
    ELEVENLABS_VOICE_ID,
    ARTICLES_AUDIO_DIR,
    article_tts_text,
    get_tts_blocked_message,
    set_tts_backoff,
)
_TTS_INFLIGHT: set[str] = set()

router = APIRouter(prefix="/api", tags=["news"])
logger = logging.getLogger("tech-signals-api.news")


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
    updated = set_article_status(article_id, status)
    if not updated:
        raise HTTPException(status_code=404, detail="Article not found")
    return updated


@router.delete("/articles/{article_id}")
async def api_delete_article(
    article_id: str,
    _admin: dict = Depends(require_article_admin),
):
    """Delete an article permanently."""
    deleted = delete_article(article_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"ok": True, "id": article_id}


@router.get("/articles/{article_id}/audio")
async def api_get_article_audio(article_id: str):
    """Generate (and cache) TTS audio for an article via ElevenLabs."""
    if not ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY is not configured")

    blocked_message = get_tts_blocked_message()
    if blocked_message:
        raise HTTPException(status_code=429, detail=blocked_message)

    article = get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    cache_path = ARTICLES_AUDIO_DIR / f"{article_id}.mp3"
    if cache_path.exists():
        return Response(content=cache_path.read_bytes(), media_type="audio/mpeg")

    if article_id in _TTS_INFLIGHT:
        raise HTTPException(status_code=429, detail="Audio generation already in progress for this article.")
    _TTS_INFLIGHT.add(article_id)

    tts_text = article_tts_text(article)
    if not tts_text:
        raise HTTPException(status_code=400, detail="Article has no readable text")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    payload = {
        "text": tts_text,
        "model_id": ELEVENLABS_MODEL_ID,
        "output_format": ELEVENLABS_OUTPUT_FORMAT,
    }
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            audio_bytes = resp.content
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else str(exc)
        detail_lower = detail.lower()
        if "detected_unusual_activity" in detail_lower or "unusual activity detected" in detail_lower:
            set_tts_backoff(
                hours=12,
                reason="ElevenLabs temporarily blocked free-tier TTS due unusual activity.",
            )
        logger.warning("ElevenLabs API status error")
        raise HTTPException(status_code=502, detail="Text-to-speech provider error")
    except httpx.HTTPError as exc:
        logger.warning("ElevenLabs request failure: %s", exc)
        raise HTTPException(status_code=502, detail="Text-to-speech provider unavailable")
    finally:
        _TTS_INFLIGHT.discard(article_id)

    if not audio_bytes:
        raise HTTPException(status_code=502, detail="ElevenLabs returned empty audio response")

    cache_path.write_bytes(audio_bytes)
    return Response(content=audio_bytes, media_type="audio/mpeg")
