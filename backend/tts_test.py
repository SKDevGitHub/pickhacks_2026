"""
Standalone ElevenLabs TTS test script.

Usage:
    python test_tts.py <path_to_article_json>

Example:
    python test_tts.py data/articles/ai-s-invisible-footprint-navigating-the-cleantech-challenge-of-hyperscale-ai-cam-1772297262.json

Output:
    Saves audio to output.mp3 in the current directory and plays it.
"""

import json
import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
ELEVENLABS_TTS_URL  = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
MAX_TTS_CHARS       = 5_000
OUTPUT_FILE         = "output.mp3"


def markdown_to_plaintext(md: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)
    text = re.sub(r"^[\-\*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_tts_text(article: dict) -> str:
    title   = article.get("title", "")
    summary = article.get("summary", "")
    content = markdown_to_plaintext(article.get("content", ""))
    full = f"{title}.\n\n{summary}.\n\n{content}"
    if len(full) > MAX_TTS_CHARS:
        full = full[:MAX_TTS_CHARS].rsplit(" ", 1)[0] + "…"
    return full


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_tts.py <path_to_article_json>")
        sys.exit(1)

    article_path = Path(sys.argv[1])
    if not article_path.exists():
        print(f"Error: file not found: {article_path}")
        sys.exit(1)

    if not ELEVENLABS_API_KEY:
        print("Error: ELEVENLABS_KEY not set in environment / .env")
        sys.exit(1)

    print(f"Loading article: {article_path}")
    article = json.loads(article_path.read_text())
    tts_text = build_tts_text(article)

    print(f"Sending {len(tts_text)} chars to ElevenLabs...")
    print(f"Preview: {tts_text[:200]}\n...")

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": tts_text,
        "model_id": ELEVENLABS_MODEL_ID,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(ELEVENLABS_TTS_URL, headers=headers, json=payload)

    if resp.status_code == 429:
        print(f"Rate limited: {resp.text}")
        sys.exit(1)

    if not resp.is_success:
        print(f"ElevenLabs error {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)

    Path(OUTPUT_FILE).write_bytes(resp.content)
    print(f"✓ Audio saved to {OUTPUT_FILE} ({len(resp.content) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()