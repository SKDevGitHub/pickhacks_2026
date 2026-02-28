"""
Docs:
    http://localhost:8000/docs
"""

import csv
import json
import os
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="City Energy & Water API",
    description="Serves power, water, and pollution data for one or more cities.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Data loading ───────────────────────────────────────────────────────────────

# Directory where city JSON files live (same folder as main.py by default) they are in data/cities
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "cities")

# Directory where article JSON files live
ARTICLES_DIR = os.path.join(os.path.dirname(__file__), "data", "articles")

# Directory where cached article audio files live
ARTICLES_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "data", "articles_audio")

# Forecast CSV (per-intersection baseline, 2023-2050)
FORECAST_CSV = os.path.join(os.path.dirname(__file__), "data", "forecast_per_intersection.csv")

# ElevenLabs config (set these in your environment or a .env file)
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRTNY")  # George
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
ELEVENLABS_TTS_URL  = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"

MAX_TTS_CHARS = 5_000


def load_city(city: str) -> dict:
    """Load a city JSON file by name (e.g. 'new_york' loads data/new_york.json)."""
    path = os.path.join(DATA_DIR, f"{city}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"No data file found for city '{city}'.")
    with open(path) as f:
        return json.load(f)


def list_cities() -> list[str]:
    """Return all available city names based on JSON files in the data directory."""
    if not os.path.exists(DATA_DIR):
        return []
    return [
        f.replace(".json", "")
        for f in os.listdir(DATA_DIR)
        if f.endswith(".json")
    ]


def load_forecast_csv() -> list[dict]:
    """Load the per-intersection forecast CSV into a list of row dicts."""
    if not os.path.exists(FORECAST_CSV):
        raise HTTPException(
            status_code=500,
            detail="Forecast CSV not found. Expected at data/forecast_per_intersection.csv"
        )
    rows = []
    with open(FORECAST_CSV, newline="") as f:
        for row in csv.DictReader(f):
            rows.append({
                "year":       int(row["year"]),
                "power_kwh":  float(row["power_kwh"]),
                "water_kgal": float(row["water_kgal"]),
                "co2_kg":     float(row["co2_kg"]),
                "data_type":  row["data_type"],
                "scenario":   row["scenario"],
                "confidence": float(row["confidence"]),
            })
    return rows


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


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/cities", summary="List all available cities")
def get_cities():
    """Returns a list of all cities that have data files loaded."""
    cities = list_cities()
    return {"cities": cities, "count": len(cities)}


@app.get("/cities/{city}", summary="Get full data for a city")
def get_city(city: str):
    """Returns all metrics (power, water, pollution) for the given city."""
    return load_city(city)


@app.get("/cities/{city}/power", summary="Get power usage for a city")
def get_city_power(city: str):
    """Returns electricity usage totals for the given city."""
    data = load_city(city)
    return {"city": city, "power_usage": data["power_usage"]}


@app.get("/cities/{city}/water", summary="Get water usage for a city")
def get_city_water(city: str):
    """Returns water usage totals for the given city."""
    data = load_city(city)
    return {"city": city, "water_usage": data["water_usage"]}


@app.get("/cities/{city}/pollution", summary="Get pollution data for a city")
def get_city_pollution(city: str):
    """Returns GHG emissions totals for the given city."""
    data = load_city(city)
    return {"city": city, "pollution": data["pollution"]}


# ── Forecast routes ────────────────────────────────────────────────────────────

@app.get(
    "/forecast",
    summary="Get per-intersection forecast (2023–2050)",
)
def get_forecast_per_intersection(
    data_type: str = Query(None, description="Filter by 'historical' or 'forecast'"),
    year_from: int = Query(2023, description="Start year (inclusive)"),
    year_to:   int = Query(2050, description="End year (inclusive)"),
):
    """
    Returns the raw per-intersection AI forecast data loaded from the CSV.
    Optionally filter by data_type ('historical' | 'forecast') and year range.
    """
    rows = load_forecast_csv()

    if data_type:
        rows = [r for r in rows if r["data_type"] == data_type]
    rows = [r for r in rows if year_from <= r["year"] <= year_to]

    return {
        "description": "Per-intersection baseline forecast (multiply by city intersections for city totals)",
        "year_range":  [year_from, year_to],
        "data_type":   data_type or "all",
        "rows":        rows,
    }


@app.get(
    "/cities/{city}/forecast",
    summary="Get city-scaled AI forecast (2023–2050)",
)
def get_city_forecast(
    city: str,
    data_type: str = Query(None, description="Filter by 'historical' or 'forecast'"),
    year_from: int = Query(2023, description="Start year (inclusive)"),
    year_to:   int = Query(2050, description="End year (inclusive)"),
):
    """
    Returns the AI forecast scaled to this city's intersection count.
    Each per-intersection value is multiplied by `intersections` from the city's JSON.

    Example: /cities/new_york/forecast?data_type=forecast&year_from=2035&year_to=2050
    """
    city_data    = load_city(city)
    intersections = city_data.get("intersections")

    if intersections is None:
        raise HTTPException(
            status_code=422,
            detail=f"City file for '{city}' is missing an 'intersections' field."
        )

    rows = load_forecast_csv()

    if data_type:
        rows = [r for r in rows if r["data_type"] == data_type]
    rows = [r for r in rows if year_from <= r["year"] <= year_to]

    scaled = []
    for r in rows:
        scaled.append({
            "year":             r["year"],
            "power_kwh":        round(r["power_kwh"]  * intersections, 2),
            "water_kgal":       round(r["water_kgal"] * intersections, 2),
            "co2_kg":           round(r["co2_kg"]     * intersections, 2),
            "data_type":        r["data_type"],
            "scenario":         r["scenario"],
            "confidence":       r["confidence"],
        })

    return {
        "city":          city,
        "intersections": intersections,
        "year_range":    [year_from, year_to],
        "data_type":     data_type or "all",
        "rows":          scaled,
    }


# ── Article audio route ────────────────────────────────────────────────────────

@app.get(
    "/api/articles/{article_id}/audio",
    summary="Stream ElevenLabs TTS narration for a news article",
)
async def get_article_audio(article_id: str):
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