"""
Docs:
    http://localhost:8000/docs
"""

import csv
import json
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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

# Directory where city JSON files live (same folder as main.py by default)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Forecast CSV (per-intersection baseline, 2023-2050)
FORECAST_CSV = os.path.join(os.path.dirname(__file__), "data", "forecast_per_intersection.csv")


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