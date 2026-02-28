"""
Comprehensive mock technology data for the Tech Signals platform.
Each technology includes Power, Pollution, and Water forecast dimensions.
"""

import csv
import json
import os
import random
import math

def _spark(base, volatility=5, n=12):
    """Generate a sparkline array of n points."""
    pts = []
    v = base
    for i in range(n):
        v += random.uniform(-volatility, volatility)
        v = max(0, min(100, v))
        pts.append(round(v, 1))
    return pts


def _trajectory(base, trend=0.5, n_hist=24, n_proj=36):
    """Generate historical + projected data with confidence bands."""
    historical = []
    v = base
    for i in range(n_hist):
        v += random.uniform(-2, 2) + trend * 0.3
        historical.append({"month": i - n_hist, "value": round(max(0, v), 1)})

    projected = []
    for i in range(n_proj):
        v += trend + random.uniform(-1, 1)
        upper = round(v + 3 + i * 0.4, 1)
        lower = round(max(0, v - 3 - i * 0.4), 1)
        projected.append({
            "month": i + 1,
            "value": round(max(0, v), 1),
            "upper": upper,
            "lower": max(0, lower),
        })

    return {"historical": historical, "projected": projected}


def _csv_forecast_path():
    """Resolve CSV path from repo root and provide a backend-local fallback."""
    current_dir = os.path.dirname(__file__)
    repo_root = os.path.dirname(os.path.dirname(current_dir))
    primary = os.path.join(repo_root, "data", "forecast_per_intersection.csv")
    fallback = os.path.join(os.path.dirname(current_dir), "data", "forecast_per_intersection.csv")
    return primary if os.path.exists(primary) else fallback


def _new_york_timeseries_path():
    """Resolve merged New York city + timeseries JSON path."""
    current_dir = os.path.dirname(__file__)
    repo_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(repo_root, "data", "cities", "new_york_timeseries.json")


def _load_forecast_rows_from_new_york_json():
    """Load normalized forecast rows from merged New York time-series JSON."""
    path = _new_york_timeseries_path()
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return []

    series = payload.get("time_series", [])
    rows = []
    for row in series:
        try:
            rows.append(
                {
                    "year": int(row["year"]),
                    "power_kwh": float(row["power_kwh"]),
                    "water_kgal": float(row["water_kgal"]),
                    "co2_kg": float(row["co2_kg"]),
                    "data_type": str(row["data_type"]).strip().lower(),
                    "scenario": str(row.get("scenario", "")).strip().lower(),
                    "confidence": float(row.get("confidence", 1.0) or 1.0),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue

    rows.sort(key=lambda item: item["year"])
    return rows


def _load_forecast_rows():
    """Load forecast rows from merged New York JSON, falling back to CSV."""
    json_rows = _load_forecast_rows_from_new_york_json()
    if json_rows:
        return json_rows

    path = _csv_forecast_path()
    if not os.path.exists(path):
        return []

    rows = []
    with open(path, newline="", encoding="utf-8") as file_handle:
        reader = csv.DictReader(file_handle)
        for row in reader:
            try:
                rows.append(
                    {
                        "year": int(row["year"]),
                        "power_kwh": float(row["power_kwh"]),
                        "water_kgal": float(row["water_kgal"]),
                        "co2_kg": float(row["co2_kg"]),
                        "data_type": row["data_type"].strip().lower(),
                        "scenario": row.get("scenario", "").strip().lower(),
                        "confidence": float(row.get("confidence", 1.0) or 1.0),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue

    rows.sort(key=lambda item: item["year"])
    return rows


def _build_series_from_csv(value_key):
    """
    Build trajectory series from CSV values.
    - historical: observed values up to last historical year
    - projected: forecast values with confidence-derived bands
    """
    rows = _load_forecast_rows()
    if not rows:
        return None

    historical_rows = [row for row in rows if row["data_type"] == "historical"]
    forecast_rows = [row for row in rows if row["data_type"] == "forecast"]

    if not historical_rows or not forecast_rows:
        return None

    reference_year = max(row["year"] for row in historical_rows)

    historical = [
        {
            "month": (row["year"] - reference_year) * 12,
            "value": round(row[value_key], 2),
        }
        for row in historical_rows
    ]

    projected = []
    for row in forecast_rows:
        value = row[value_key]
        confidence = max(0.0, min(1.0, row["confidence"]))
        margin = max(1.0, value * (1.0 - confidence))
        projected.append(
            {
                "month": (row["year"] - reference_year) * 12,
                "value": round(value, 2),
                "upper": round(value + margin, 2),
                "lower": round(max(0.0, value - margin), 2),
            }
        )

    return {"historical": historical, "projected": projected}


def _scale_csv_series(series, multiplier):
    """Scale baseline CSV trajectory per technology while preserving shape."""
    return {
        "historical": [
            {"month": point["month"], "value": round(point["value"] * multiplier, 2)}
            for point in series.get("historical", [])
        ],
        "projected": [
            {
                "month": point["month"],
                "value": round(point["value"] * multiplier, 2),
                "upper": round(point["upper"] * multiplier, 2),
                "lower": round(point["lower"] * multiplier, 2),
            }
            for point in series.get("projected", [])
        ],
    }


CATEGORIES = [
    {
        "id": "ai-infrastructure",
        "name": "AI Infrastructure",
        "description": "Large-scale AI training clusters, inference farms, and edge compute driving exponential energy demand growth.",
        "technologies": [
            {
                "id": "llm-training-clusters",
                "name": "LLM Training Clusters",
                "description": "Next-generation large language model training facilities consuming megawatt-scale power.",
                "power": {
                    "forecastIndex": 92,
                    "delta": 14.2,
                    "mwDemand": "340 MW",
                    "gridCarbonIndex": 78,
                    "loadConcentrationRisk": "Critical",
                    "sparkline": [62, 65, 68, 72, 74, 78, 81, 84, 87, 89, 91, 92],
                },
                "pollution": {
                    "forecastIndex": 71,
                    "delta": 8.4,
                    "emissionDelta": "+18.2 MtCO₂e/yr",
                    "toxicityTier": "Tier 2",
                    "wasteBurden": "Moderate",
                    "sparkline": [55, 57, 59, 61, 63, 64, 66, 67, 69, 70, 71, 71],
                },
                "water": {
                    "forecastIndex": 84,
                    "delta": 11.6,
                    "cubicMetersYear": "2.1B m³/yr",
                    "scarcityExposure": 81,
                    "contaminationProb": 0.12,
                    "sparkline": [60, 63, 66, 69, 72, 74, 76, 78, 80, 82, 83, 84],
                },
                "externalityRisk": 88,
                "region": "Global",
                "forecastHorizon": "36m",
            },
            {
                "id": "gpu-data-centers",
                "name": "GPU Data Centers",
                "description": "Hyperscale GPU-accelerated data centers optimized for inference and fine-tuning workloads.",
                "power": {
                    "forecastIndex": 87,
                    "delta": 12.1,
                    "mwDemand": "220 MW",
                    "gridCarbonIndex": 72,
                    "loadConcentrationRisk": "High",
                    "sparkline": [58, 62, 65, 68, 71, 74, 77, 80, 83, 85, 86, 87],
                },
                "pollution": {
                    "forecastIndex": 64,
                    "delta": 6.3,
                    "emissionDelta": "+12.4 MtCO₂e/yr",
                    "toxicityTier": "Tier 2",
                    "wasteBurden": "Moderate",
                    "sparkline": [48, 50, 52, 54, 56, 57, 59, 60, 62, 63, 64, 64],
                },
                "water": {
                    "forecastIndex": 79,
                    "delta": 9.8,
                    "cubicMetersYear": "1.6B m³/yr",
                    "scarcityExposure": 74,
                    "contaminationProb": 0.09,
                    "sparkline": [55, 58, 61, 64, 67, 69, 71, 73, 75, 77, 78, 79],
                },
                "externalityRisk": 82,
                "region": "North America",
                "forecastHorizon": "24m",
            },
            {
                "id": "edge-ai-processors",
                "name": "Edge AI Processors",
                "description": "Distributed edge inference hardware deployed across IoT and mobile networks at massive scale.",
                "power": {
                    "forecastIndex": 54,
                    "delta": 4.8,
                    "mwDemand": "45 MW",
                    "gridCarbonIndex": 42,
                    "loadConcentrationRisk": "Low",
                    "sparkline": [40, 42, 44, 45, 47, 48, 49, 50, 51, 52, 53, 54],
                },
                "pollution": {
                    "forecastIndex": 58,
                    "delta": 5.2,
                    "emissionDelta": "+4.1 MtCO₂e/yr",
                    "toxicityTier": "Tier 3",
                    "wasteBurden": "Low–Moderate",
                    "sparkline": [42, 44, 46, 48, 49, 51, 52, 54, 55, 56, 57, 58],
                },
                "water": {
                    "forecastIndex": 38,
                    "delta": 2.1,
                    "cubicMetersYear": "0.3B m³/yr",
                    "scarcityExposure": 31,
                    "contaminationProb": 0.04,
                    "sparkline": [30, 31, 32, 33, 34, 34, 35, 36, 36, 37, 37, 38],
                },
                "externalityRisk": 51,
                "region": "Global",
                "forecastHorizon": "24m",
            },
        ],
    },
    {
        "id": "battery-storage",
        "name": "Battery & Storage",
        "description": "Lithium-ion gigafactories, solid-state batteries, and grid-scale storage systems transforming energy infrastructure.",
        "technologies": [
            {
                "id": "lithium-ion-gigafactories",
                "name": "Lithium-Ion Gigafactories",
                "description": "Mega-scale battery manufacturing facilities with intensive mineral supply chains.",
                "power": {
                    "forecastIndex": 68,
                    "delta": 7.2,
                    "mwDemand": "180 MW",
                    "gridCarbonIndex": 58,
                    "loadConcentrationRisk": "Moderate",
                    "sparkline": [48, 50, 53, 55, 58, 60, 62, 64, 65, 66, 67, 68],
                },
                "pollution": {
                    "forecastIndex": 82,
                    "delta": 10.6,
                    "emissionDelta": "+9.8 MtCO₂e/yr",
                    "toxicityTier": "Tier 1",
                    "wasteBurden": "High",
                    "sparkline": [60, 63, 66, 69, 72, 74, 76, 78, 79, 80, 81, 82],
                },
                "water": {
                    "forecastIndex": 76,
                    "delta": 8.9,
                    "cubicMetersYear": "1.2B m³/yr",
                    "scarcityExposure": 72,
                    "contaminationProb": 0.18,
                    "sparkline": [52, 55, 58, 61, 64, 66, 68, 70, 72, 74, 75, 76],
                },
                "externalityRisk": 79,
                "region": "Asia Pacific",
                "forecastHorizon": "36m",
            },
            {
                "id": "solid-state-batteries",
                "name": "Solid-State Batteries",
                "description": "Next-generation solid electrolyte batteries promising higher density with different environmental profiles.",
                "power": {
                    "forecastIndex": 45,
                    "delta": 3.8,
                    "mwDemand": "60 MW",
                    "gridCarbonIndex": 38,
                    "loadConcentrationRisk": "Low",
                    "sparkline": [34, 35, 37, 38, 39, 40, 41, 42, 43, 44, 44, 45],
                },
                "pollution": {
                    "forecastIndex": 52,
                    "delta": 4.6,
                    "emissionDelta": "+3.2 MtCO₂e/yr",
                    "toxicityTier": "Tier 2",
                    "wasteBurden": "Moderate",
                    "sparkline": [38, 40, 42, 43, 45, 46, 47, 48, 49, 50, 51, 52],
                },
                "water": {
                    "forecastIndex": 41,
                    "delta": 2.4,
                    "cubicMetersYear": "0.4B m³/yr",
                    "scarcityExposure": 35,
                    "contaminationProb": 0.06,
                    "sparkline": [32, 33, 34, 35, 36, 37, 38, 38, 39, 40, 40, 41],
                },
                "externalityRisk": 47,
                "region": "East Asia",
                "forecastHorizon": "36m",
            },
            {
                "id": "grid-scale-storage",
                "name": "Grid-Scale Storage",
                "description": "Utility-grade energy storage systems including flow batteries and compressed air installations.",
                "power": {
                    "forecastIndex": 56,
                    "delta": 5.1,
                    "mwDemand": "95 MW",
                    "gridCarbonIndex": 32,
                    "loadConcentrationRisk": "Low",
                    "sparkline": [40, 42, 44, 46, 47, 49, 50, 52, 53, 54, 55, 56],
                },
                "pollution": {
                    "forecastIndex": 48,
                    "delta": 3.2,
                    "emissionDelta": "+2.8 MtCO₂e/yr",
                    "toxicityTier": "Tier 3",
                    "wasteBurden": "Low",
                    "sparkline": [38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 47, 48],
                },
                "water": {
                    "forecastIndex": 34,
                    "delta": 1.8,
                    "cubicMetersYear": "0.18B m³/yr",
                    "scarcityExposure": 28,
                    "contaminationProb": 0.03,
                    "sparkline": [28, 29, 29, 30, 30, 31, 31, 32, 32, 33, 33, 34],
                },
                "externalityRisk": 44,
                "region": "Global",
                "forecastHorizon": "24m",
            },
        ],
    },
    {
        "id": "hydrogen-systems",
        "name": "Hydrogen Systems",
        "description": "Green and blue hydrogen production, fuel cell deployment, and hydrogen transport infrastructure.",
        "technologies": [
            {
                "id": "green-hydrogen-electrolysis",
                "name": "Green Hydrogen Electrolysis",
                "description": "Renewable-powered water electrolysis for clean hydrogen production at industrial scale.",
                "power": {
                    "forecastIndex": 78,
                    "delta": 9.4,
                    "mwDemand": "280 MW",
                    "gridCarbonIndex": 22,
                    "loadConcentrationRisk": "High",
                    "sparkline": [52, 55, 58, 61, 64, 66, 69, 71, 73, 75, 77, 78],
                },
                "pollution": {
                    "forecastIndex": 28,
                    "delta": -2.1,
                    "emissionDelta": "-1.4 MtCO₂e/yr",
                    "toxicityTier": "Tier 4",
                    "wasteBurden": "Very Low",
                    "sparkline": [35, 34, 33, 32, 31, 31, 30, 30, 29, 29, 28, 28],
                },
                "water": {
                    "forecastIndex": 86,
                    "delta": 12.8,
                    "cubicMetersYear": "3.4B m³/yr",
                    "scarcityExposure": 88,
                    "contaminationProb": 0.05,
                    "sparkline": [58, 62, 66, 69, 72, 75, 78, 80, 82, 84, 85, 86],
                },
                "externalityRisk": 72,
                "region": "Middle East / N. Africa",
                "forecastHorizon": "36m",
            },
            {
                "id": "blue-hydrogen-ccs",
                "name": "Blue Hydrogen w/ CCS",
                "description": "Natural gas-derived hydrogen with carbon capture and storage, debated lifecycle benefits.",
                "power": {
                    "forecastIndex": 62,
                    "delta": 5.6,
                    "mwDemand": "150 MW",
                    "gridCarbonIndex": 55,
                    "loadConcentrationRisk": "Moderate",
                    "sparkline": [44, 46, 48, 50, 52, 54, 56, 57, 59, 60, 61, 62],
                },
                "pollution": {
                    "forecastIndex": 59,
                    "delta": 4.8,
                    "emissionDelta": "+5.6 MtCO₂e/yr",
                    "toxicityTier": "Tier 2",
                    "wasteBurden": "Moderate",
                    "sparkline": [42, 44, 46, 48, 50, 51, 53, 54, 56, 57, 58, 59],
                },
                "water": {
                    "forecastIndex": 58,
                    "delta": 6.2,
                    "cubicMetersYear": "1.1B m³/yr",
                    "scarcityExposure": 52,
                    "contaminationProb": 0.14,
                    "sparkline": [38, 40, 42, 44, 46, 48, 50, 52, 54, 55, 57, 58],
                },
                "externalityRisk": 61,
                "region": "North America",
                "forecastHorizon": "24m",
            },
        ],
    },
    {
        "id": "advanced-manufacturing",
        "name": "Advanced Manufacturing",
        "description": "Semiconductor fabrication, additive manufacturing, and carbon fiber production scaling rapidly.",
        "technologies": [
            {
                "id": "semiconductor-fabs",
                "name": "Semiconductor Fabs (3nm+)",
                "description": "Advanced node semiconductor fabrication with extreme UV lithography and ultrapure water demands.",
                "power": {
                    "forecastIndex": 74,
                    "delta": 8.2,
                    "mwDemand": "200 MW",
                    "gridCarbonIndex": 61,
                    "loadConcentrationRisk": "High",
                    "sparkline": [50, 53, 56, 58, 61, 63, 66, 68, 70, 72, 73, 74],
                },
                "pollution": {
                    "forecastIndex": 69,
                    "delta": 7.1,
                    "emissionDelta": "+7.2 MtCO₂e/yr",
                    "toxicityTier": "Tier 1",
                    "wasteBurden": "High",
                    "sparkline": [48, 50, 52, 55, 57, 59, 61, 63, 65, 67, 68, 69],
                },
                "water": {
                    "forecastIndex": 88,
                    "delta": 13.4,
                    "cubicMetersYear": "4.1B m³/yr",
                    "scarcityExposure": 85,
                    "contaminationProb": 0.22,
                    "sparkline": [60, 64, 67, 70, 73, 76, 79, 81, 83, 85, 87, 88],
                },
                "externalityRisk": 81,
                "region": "East Asia",
                "forecastHorizon": "24m",
            },
            {
                "id": "3d-printing-scale",
                "name": "3D Printing at Scale",
                "description": "Industrial additive manufacturing for aerospace, automotive, and construction applications.",
                "power": {
                    "forecastIndex": 48,
                    "delta": 3.4,
                    "mwDemand": "35 MW",
                    "gridCarbonIndex": 40,
                    "loadConcentrationRisk": "Low",
                    "sparkline": [36, 37, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48],
                },
                "pollution": {
                    "forecastIndex": 55,
                    "delta": 4.2,
                    "emissionDelta": "+2.4 MtCO₂e/yr",
                    "toxicityTier": "Tier 2",
                    "wasteBurden": "Moderate",
                    "sparkline": [40, 42, 43, 45, 46, 48, 49, 50, 52, 53, 54, 55],
                },
                "water": {
                    "forecastIndex": 32,
                    "delta": 1.4,
                    "cubicMetersYear": "0.12B m³/yr",
                    "scarcityExposure": 22,
                    "contaminationProb": 0.08,
                    "sparkline": [26, 27, 27, 28, 28, 29, 29, 30, 30, 31, 31, 32],
                },
                "externalityRisk": 46,
                "region": "Global",
                "forecastHorizon": "12m",
            },
            {
                "id": "carbon-fiber-production",
                "name": "Carbon Fiber Production",
                "description": "High-performance carbon fiber manufacturing for lightweight vehicles and wind turbines.",
                "power": {
                    "forecastIndex": 61,
                    "delta": 5.8,
                    "mwDemand": "110 MW",
                    "gridCarbonIndex": 54,
                    "loadConcentrationRisk": "Moderate",
                    "sparkline": [42, 44, 46, 48, 50, 52, 54, 55, 57, 58, 60, 61],
                },
                "pollution": {
                    "forecastIndex": 72,
                    "delta": 8.0,
                    "emissionDelta": "+6.8 MtCO₂e/yr",
                    "toxicityTier": "Tier 1",
                    "wasteBurden": "High",
                    "sparkline": [50, 53, 55, 58, 60, 62, 64, 66, 68, 70, 71, 72],
                },
                "water": {
                    "forecastIndex": 44,
                    "delta": 2.8,
                    "cubicMetersYear": "0.52B m³/yr",
                    "scarcityExposure": 38,
                    "contaminationProb": 0.15,
                    "sparkline": [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 43, 44],
                },
                "externalityRisk": 62,
                "region": "Global",
                "forecastHorizon": "24m",
            },
        ],
    },
    {
        "id": "quantum-computing",
        "name": "Quantum Computing",
        "description": "Superconducting and photonic quantum processors requiring cryogenic cooling and specialized infrastructure.",
        "technologies": [
            {
                "id": "superconducting-quantum",
                "name": "Superconducting Quantum",
                "description": "Dilution refrigerator–based quantum processors at millikelvin temperatures.",
                "power": {
                    "forecastIndex": 58,
                    "delta": 6.2,
                    "mwDemand": "25 MW",
                    "gridCarbonIndex": 48,
                    "loadConcentrationRisk": "Moderate",
                    "sparkline": [38, 40, 42, 44, 46, 48, 50, 52, 53, 55, 57, 58],
                },
                "pollution": {
                    "forecastIndex": 42,
                    "delta": 2.8,
                    "emissionDelta": "+1.2 MtCO₂e/yr",
                    "toxicityTier": "Tier 3",
                    "wasteBurden": "Low",
                    "sparkline": [34, 35, 36, 36, 37, 38, 38, 39, 40, 40, 41, 42],
                },
                "water": {
                    "forecastIndex": 62,
                    "delta": 7.4,
                    "cubicMetersYear": "0.8B m³/yr",
                    "scarcityExposure": 55,
                    "contaminationProb": 0.07,
                    "sparkline": [40, 43, 45, 48, 50, 52, 54, 56, 58, 59, 61, 62],
                },
                "externalityRisk": 55,
                "region": "North America",
                "forecastHorizon": "36m",
            },
            {
                "id": "photonic-quantum",
                "name": "Photonic Quantum",
                "description": "Room-temperature photonic quantum computing with lower cooling overhead.",
                "power": {
                    "forecastIndex": 36,
                    "delta": 2.1,
                    "mwDemand": "12 MW",
                    "gridCarbonIndex": 30,
                    "loadConcentrationRisk": "Low",
                    "sparkline": [28, 29, 30, 30, 31, 32, 32, 33, 34, 34, 35, 36],
                },
                "pollution": {
                    "forecastIndex": 34,
                    "delta": 1.6,
                    "emissionDelta": "+0.6 MtCO₂e/yr",
                    "toxicityTier": "Tier 4",
                    "wasteBurden": "Very Low",
                    "sparkline": [28, 29, 29, 30, 30, 31, 31, 32, 32, 33, 33, 34],
                },
                "water": {
                    "forecastIndex": 28,
                    "delta": 1.2,
                    "cubicMetersYear": "0.08B m³/yr",
                    "scarcityExposure": 18,
                    "contaminationProb": 0.02,
                    "sparkline": [22, 23, 23, 24, 24, 25, 25, 26, 26, 27, 27, 28],
                },
                "externalityRisk": 33,
                "region": "Europe",
                "forecastHorizon": "36m",
            },
        ],
    },
]


# Pre-generate trajectory data for each technology
def _build_trajectory_cache():
    csv_power = _build_series_from_csv("power_kwh")
    csv_pollution = _build_series_from_csv("co2_kg")
    csv_water = _build_series_from_csv("water_kgal")

    use_csv = csv_power and csv_pollution and csv_water
    cache = {}
    for cat in CATEGORIES:
        for tech in cat["technologies"]:
            tid = tech["id"]
            p_base = tech["power"]["forecastIndex"]
            pol_base = tech["pollution"]["forecastIndex"]
            w_base = tech["water"]["forecastIndex"]

            if use_csv:
                power_scale = max(0.25, p_base / 70)
                pollution_scale = max(0.25, pol_base / 70)
                water_scale = max(0.25, w_base / 70)
                cache[tid] = {
                    "power": _scale_csv_series(csv_power, power_scale),
                    "pollution": _scale_csv_series(csv_pollution, pollution_scale),
                    "water": _scale_csv_series(csv_water, water_scale),
                }
            else:
                cache[tid] = {
                    "power": _trajectory(p_base * 0.6, trend=tech["power"]["delta"] / 12),
                    "pollution": _trajectory(pol_base * 0.6, trend=tech["pollution"]["delta"] / 12),
                    "water": _trajectory(w_base * 0.6, trend=tech["water"]["delta"] / 12),
                }
    return cache


TRAJECTORY_CACHE = _build_trajectory_cache()


REGIONS = [
    "Global",
    "North America",
    "Europe",
    "East Asia",
    "Asia Pacific",
    "Middle East / N. Africa",
    "Sub-Saharan Africa",
    "Latin America",
]


ENGINE_STATUS = {
    "technologiesModeled": 14,
    "highRiskAlerts": 5,
    "regionsUnderStress": 3,
    "lastModelUpdate": "2026-02-26T08:00:00Z",
}


MACRO_SUMMARY = (
    "Data center expansion driven by LLM training demand is projected to increase "
    "regional water stress in the U.S. Southwest within 18 months. Simultaneously, "
    "lithium-ion gigafactory scaling in East Asia is raising lifecycle toxicity risk "
    "scores to Tier 1 levels. Green hydrogen electrolysis shows favorable emission "
    "profiles but introduces significant water consumption pressure in arid deployment "
    "regions. Semiconductor fab expansion at advanced nodes (3nm+) continues to drive "
    "ultrapure water demand beyond sustainable thresholds in water-stressed basins."
)


def get_all_technologies_flat():
    """Return a flat list of all technologies with their category info."""
    result = []
    for cat in CATEGORIES:
        for tech in cat["technologies"]:
            result.append({**tech, "category": cat["name"], "categoryId": cat["id"]})
    return result


def get_technology_by_id(tech_id: str):
    """Find a technology by its ID."""
    for cat in CATEGORIES:
        for tech in cat["technologies"]:
            if tech["id"] == tech_id:
                return {
                    **tech,
                    "category": cat["name"],
                    "categoryId": cat["id"],
                    "trajectory": TRAJECTORY_CACHE.get(tech_id, {}),
                    "drivers": _get_drivers(tech),
                    "regionSensitivity": _get_region_sensitivity(tech),
                }
    return None


def _get_drivers(tech):
    return [
        {"label": "Energy Intensity Benchmark", "value": f"{tech['power']['gridCarbonIndex']} gCO₂/kWh weighted"},
        {"label": "Mining Intensity Factor", "value": "High" if tech["pollution"]["forecastIndex"] > 65 else "Moderate"},
        {"label": "Cooling Demand Assumption", "value": f"{tech['water']['scarcityExposure']}% regional stress"},
        {"label": "Deployment Growth Rate", "value": f"+{tech['power']['delta']}% projected annually"},
        {"label": "Lifecycle Assessment Basis", "value": "ISO 14040/44 compliant aggregation"},
        {"label": "Grid Mix Assumption", "value": "Regional marginal emission factors (2025 baseline)"},
    ]


def _get_region_sensitivity(tech):
    return [
        {"region": "U.S. Southwest", "waterStress": 0.82, "gridCarbon": 410},
        {"region": "East Asia (Taiwan/Korea)", "waterStress": 0.68, "gridCarbon": 520},
        {"region": "Northern Europe", "waterStress": 0.22, "gridCarbon": 180},
        {"region": "Middle East", "waterStress": 0.91, "gridCarbon": 620},
        {"region": "Southeast Asia", "waterStress": 0.56, "gridCarbon": 480},
    ]
