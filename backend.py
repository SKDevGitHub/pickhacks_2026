"""
City Energy & Water Data API
FastAPI backend that serves power, water, and pollution data from city JSON files.

Setup:
    pip install fastapi uvicorn

Run:
    uvicorn main:app --reload

Docs:
    http://localhost:8000/docs
"""

import json
import os
from fastapi import FastAPI, HTTPException
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
