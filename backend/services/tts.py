import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb").strip() or "JBFqnCBsd6RMkjVDRZzb"
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip() or "eleven_multilingual_v2"
ELEVENLABS_OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128").strip() or "mp3_44100_128"

ROOT_DIR = Path(__file__).resolve().parents[2]
ARTICLES_AUDIO_DIR = ROOT_DIR / "data" / "articles_audio"
ARTICLES_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
TTS_STATE_PATH = ARTICLES_AUDIO_DIR / "_tts_state.json"


def clean_tts_text(text: str) -> str:
    cleaned = str(text or "")
    cleaned = cleaned.replace("#", " ").replace("*", " ").replace("`", " ")
    cleaned = " ".join(cleaned.split())
    return cleaned


def article_tts_text(article: dict) -> str:
    """Build TTS text from title + summary only (keeps credit usage low)."""
    title = clean_tts_text(article.get("title", ""))
    summary = clean_tts_text(article.get("summary", ""))

    combined = f"{title}. {summary}".strip()
    if len(combined) > 1000:
        combined = combined[:1000]
    return combined


def _load_tts_state() -> dict:
    if not TTS_STATE_PATH.exists():
        return {}
    try:
        return json.loads(TTS_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_tts_state(state: dict) -> None:
    try:
        TTS_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


def get_tts_blocked_message() -> Optional[str]:
    state = _load_tts_state()
    blocked_until_raw = state.get("blocked_until")
    if not blocked_until_raw:
        return None
    try:
        blocked_until = datetime.fromisoformat(str(blocked_until_raw))
    except ValueError:
        return None

    if blocked_until <= datetime.now(timezone.utc):
        return None

    reason = str(state.get("reason", "Temporary ElevenLabs cooldown in effect.")).strip()
    return f"{reason} Try again after {blocked_until.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}."


def set_tts_backoff(hours: int, reason: str) -> None:
    until = datetime.now(timezone.utc) + timedelta(hours=hours)
    _save_tts_state({
        "blocked_until": until.isoformat(),
        "reason": reason,
    })
