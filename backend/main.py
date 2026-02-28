"""
Tech Signals — FastAPI Backend
Predictive Environmental Externality Engine
"""

import os
import json
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from data.technologies import (
    CATEGORIES,
    ENGINE_STATUS,
    MACRO_SUMMARY,
    get_all_technologies_flat,
    get_technology_by_id,
    REGIONS,
)

load_dotenv()

app = FastAPI(
    title="Tech Signals API",
    description="Predictive Environmental Externality Engine — forecasts the environmental consequences of emerging technology adoption.",
    version="1.0.0",
)


def _city_name_from_filename(path: Path) -> str:
    stem = path.stem.replace("_timeseries", "").replace("_", " ").strip()
    parts = [p.capitalize() for p in stem.split() if p]
    return " ".join(parts)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_city_stats(city_name: str, payload: dict) -> dict:
    power_block = payload.get("power_usage") or payload.get("power") or {}
    water_block = payload.get("water_usage") or payload.get("water") or {}
    pollution_block = payload.get("pollution") or payload.get("air_pollution") or {}

    power_value = power_block.get("total_electricity_kwh", power_block.get("power_consumption", 0))
    water_value = water_block.get("total_water_kgal", water_block.get("water_consumption", 0))
    pollution_value = pollution_block.get("total_ghg_mt_co2e", pollution_block.get("pm25_concentration", 0))

    power_growth = power_block.get("avg_growth", power_block.get("avg_growth_rate", 0))
    water_growth = water_block.get("avg_growth", water_block.get("avg_growth_rate", 0))
    pollution_growth = pollution_block.get("avg_growth", pollution_block.get("avg_growth_rate", 0))

    pollution_unit = "MtCO₂e" if "total_ghg_mt_co2e" in pollution_block else "PM2.5"

    city_id = city_name.lower().replace(".", "").replace(" ", "-")

    return {
        "id": city_id,
        "name": city_name,
        "source": payload.get("source", "Unknown source"),
        "intersections": int(payload.get("intersections", 0) or 0),
        "stats": {
            "power": {
                "value": _safe_float(power_value),
                "unit": "kWh",
                "avgGrowth": _safe_float(power_growth),
            },
            "water": {
                "value": _safe_float(water_value),
                "unit": "kgal",
                "avgGrowth": _safe_float(water_growth),
            },
            "pollution": {
                "value": _safe_float(pollution_value),
                "unit": pollution_unit,
                "avgGrowth": _safe_float(pollution_growth),
            },
        },
        "timeSeries": payload.get("time_series", []),
    }


def _load_cities() -> list[dict]:
    root_dir = Path(__file__).resolve().parents[1]
    cities_dir = root_dir / "data" / "cities"

    if not cities_dir.exists():
        return []

    cities_by_id = {}
    for path in sorted(cities_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        city_name = str(payload.get("city", "")).strip() or _city_name_from_filename(path)
        normalized = _normalize_city_stats(city_name, payload)

        existing = cities_by_id.get(normalized["id"])
        if not existing:
            cities_by_id[normalized["id"]] = normalized
            continue

        existing_has_series = bool(existing.get("timeSeries"))
        normalized_has_series = bool(normalized.get("timeSeries"))
        if normalized_has_series and not existing_has_series:
            cities_by_id[normalized["id"]] = normalized

    return sorted(cities_by_id.values(), key=lambda city: city["name"])

# CORS — allow the React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
#  Public endpoints (no auth required)
# ──────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "tech-signals-api"}


@app.get("/api/engine-status")
async def engine_status():
    """Engine Status metrics for the Home dashboard."""
    return ENGINE_STATUS


@app.get("/api/macro-summary")
async def macro_summary():
    """AI-generated macro summary of environmental shifts."""
    return {"summary": MACRO_SUMMARY}


@app.get("/api/categories")
async def list_categories():
    """List all technology categories with aggregate metrics."""
    result = []
    for cat in CATEGORIES:
        techs = cat["technologies"]
        n = len(techs)
        avg_power = round(sum(t["power"]["forecastIndex"] for t in techs) / n, 1)
        avg_pollution = round(sum(t["pollution"]["forecastIndex"] for t in techs) / n, 1)
        avg_water = round(sum(t["water"]["forecastIndex"] for t in techs) / n, 1)
        result.append({
            "id": cat["id"],
            "name": cat["name"],
            "description": cat["description"],
            "technologyCount": n,
            "averages": {
                "power": avg_power,
                "pollution": avg_pollution,
                "water": avg_water,
            },
            "technologies": cat["technologies"],
        })
    return result


@app.get("/api/technologies")
async def list_technologies(
    category: Optional[str] = Query(None),
    power_min: Optional[int] = Query(None, alias="powerMin"),
    power_max: Optional[int] = Query(None, alias="powerMax"),
    pollution_min: Optional[int] = Query(None, alias="pollutionMin"),
    pollution_max: Optional[int] = Query(None, alias="pollutionMax"),
    water_min: Optional[int] = Query(None, alias="waterMin"),
    water_max: Optional[int] = Query(None, alias="waterMax"),
    horizon: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, alias="sortBy"),
):
    """
    Filterable, searchable list of all technologies.
    Supports filters for power, pollution, water ranges, category, and horizon.
    """
    techs = get_all_technologies_flat()

    if category:
        techs = [t for t in techs if t["categoryId"] == category]
    if horizon:
        techs = [t for t in techs if t["forecastHorizon"] == horizon]
    if search:
        q = search.lower()
        techs = [t for t in techs if q in t["name"].lower() or q in t["description"].lower()]

    if power_min is not None:
        techs = [t for t in techs if t["power"]["forecastIndex"] >= power_min]
    if power_max is not None:
        techs = [t for t in techs if t["power"]["forecastIndex"] <= power_max]
    if pollution_min is not None:
        techs = [t for t in techs if t["pollution"]["forecastIndex"] >= pollution_min]
    if pollution_max is not None:
        techs = [t for t in techs if t["pollution"]["forecastIndex"] <= pollution_max]
    if water_min is not None:
        techs = [t for t in techs if t["water"]["forecastIndex"] >= water_min]
    if water_max is not None:
        techs = [t for t in techs if t["water"]["forecastIndex"] <= water_max]

    if sort_by == "power":
        techs.sort(key=lambda t: t["power"]["forecastIndex"], reverse=True)
    elif sort_by == "pollution":
        techs.sort(key=lambda t: t["pollution"]["forecastIndex"], reverse=True)
    elif sort_by == "water":
        techs.sort(key=lambda t: t["water"]["forecastIndex"], reverse=True)
    elif sort_by == "risk":
        techs.sort(key=lambda t: t["externalityRisk"], reverse=True)
    else:
        techs.sort(key=lambda t: t["externalityRisk"], reverse=True)

    return techs


@app.get("/api/technologies/{tech_id}")
async def get_technology(tech_id: str):
    """Get detailed technology data including trajectory and drivers."""
    tech = get_technology_by_id(tech_id)
    if not tech:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Technology not found")
    return tech


@app.get("/api/alerts")
async def alerts():
    """Top technologies ranked by projected environmental strain (12–36m)."""
    techs = get_all_technologies_flat()
    techs.sort(key=lambda t: t["externalityRisk"], reverse=True)
    return techs[:6]


@app.get("/api/regions")
async def list_regions():
    return REGIONS


@app.get("/api/cities")
async def list_cities():
    """List pre-loaded city stats for Forecasts city selector."""
    return _load_cities()


@app.get("/api/scenarios/simulate")
async def simulate_scenario(
    tech_id: str = Query(..., alias="techId"),
    region: str = Query("Global"),
    scale: float = Query(1.0, ge=0.1, le=10.0),
):
    """
    Run a basic scaling simulation.
    Returns projected Power/Pollution/Water at the given deployment scale.
    """
    tech = get_technology_by_id(tech_id)
    if not tech:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Technology not found")

    trajectory = tech.get("trajectory", {})

    def _scale_series(series, multiplier):
        return {
            "historical": series.get("historical", []),
            "projected": [
                {
                    "month": p["month"],
                    "value": round(p["value"] * multiplier, 1),
                    "upper": round(p["upper"] * multiplier, 1),
                    "lower": round(max(0, p["lower"] * multiplier), 1),
                }
                for p in series.get("projected", [])
            ],
        }

    return {
        "technology": tech["name"],
        "region": region,
        "scale": scale,
        "power": _scale_series(trajectory.get("power", {}), scale),
        "pollution": _scale_series(trajectory.get("pollution", {}), scale),
        "water": _scale_series(trajectory.get("water", {}), scale),
        "metrics": {
            "power": {
                "forecastIndex": min(100, round(tech["power"]["forecastIndex"] * scale)),
                "mwDemand": tech["power"]["mwDemand"],
            },
            "pollution": {
                "forecastIndex": min(100, round(tech["pollution"]["forecastIndex"] * scale)),
                "emissionDelta": tech["pollution"]["emissionDelta"],
            },
            "water": {
                "forecastIndex": min(100, round(tech["water"]["forecastIndex"] * scale)),
                "cubicMetersYear": tech["water"]["cubicMetersYear"],
            },
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
