"""
Technology data loader for Tech Signals.
All technology/category records are sourced from files in data/emergent_tech.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
EMERGENT_TECH_DIR = ROOT_DIR / "data" / "emergent_tech"
CITIES_DIR = ROOT_DIR / "data" / "cities"
NY_TIMESERIES_PATH = CITIES_DIR / "new_york_timeseries.json"
CSV_FALLBACK_PATH = ROOT_DIR / "data" / "forecast_per_intersection.csv"
TECH_CONFIG_PATH = ROOT_DIR / "data" / "technology_config.json"


def _default_config() -> dict:
    return {
        "defaults": {
            "unknownSource": "Unknown source",
            "globalRegion": "Global",
            "defaultForecastHorizon": "24m",
            "emptySummary": "No emergent technology data was found in the data folder.",
            "macroSummaryTemplate": "Technology forecasts are now sourced from data/emergent_tech. Highest current externality pressure appears in: {top_names}.",
        },
        "thresholds": {
            "highRiskAlert": 70,
            "loadConcentration": {"high": 70, "moderate": 40},
            "toxicityTier": {"tier1": 75, "tier2": 50},
            "wasteBurden": {"high": 70, "moderate": 40},
        },
        "labels": {
            "mwDemandSuffix": "MW-equivalent",
            "waterYearSuffix": "M units/yr",
            "pollutionPrefix": "PM2.5",
            "loadConcentration": {"high": "High", "moderate": "Moderate", "low": "Low"},
            "toxicityTier": {"tier1": "Tier 1", "tier2": "Tier 2", "tier3": "Tier 3"},
            "wasteBurden": {"high": "High", "moderate": "Moderate", "low": "Low"},
            "driverLabels": {
                "source": "Source",
                "powerGrowth": "Power Growth",
                "waterGrowth": "Water Growth",
                "pollutionGrowth": "Pollution Growth",
                "riskScore": "Risk Score",
            },
        },
        "categories": {
            "rules": [],
            "fallback": {
                "id": "emergent-tech",
                "name": "Emergent Tech",
                "description": "Emerging technology systems tracked from source datasets.",
            },
        },
    }


def _load_technology_config() -> dict:
    defaults = _default_config()
    if not TECH_CONFIG_PATH.exists():
        return defaults

    try:
        payload = json.loads(TECH_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults

    defaults.update({k: v for k, v in payload.items() if isinstance(v, dict)})
    return defaults


TECH_CONFIG = _load_technology_config()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _title_from_stem(stem: str) -> str:
    return stem.replace("_", " ").strip().title()


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _category_for_stem(stem: str) -> tuple[str, str, str]:
    key = stem.lower()
    category_rules = TECH_CONFIG.get("categories", {}).get("rules", [])

    def _rule_matches(rule: dict, value: str) -> bool:
        match_any = rule.get("matchAny", [])
        match_regex = rule.get("matchRegex", [])

        any_match = any(term in value for term in match_any)

        regex_match = False
        for pattern in match_regex:
            try:
                if re.search(str(pattern), value, flags=re.IGNORECASE):
                    regex_match = True
                    break
            except re.error:
                continue

        if not match_any and not match_regex:
            return False
        return any_match or regex_match

    for rule in category_rules:
        if _rule_matches(rule, key):
            return (
                str(rule.get("id", "emergent-tech")),
                str(rule.get("name", "Emergent Tech")),
                str(rule.get("description", "Emerging technology systems tracked from source datasets.")),
            )

    fallback = TECH_CONFIG.get("categories", {}).get("fallback", {})
    return (
        str(fallback.get("id", "emergent-tech")),
        str(fallback.get("name", "Emergent Tech")),
        str(fallback.get("description", "Emerging technology systems tracked from source datasets.")),
    )


def _build_sparkline(index: float, delta: float, n: int = 12) -> list[float]:
    start = _clamp(index - (delta * 4.0), 0, 100)
    step = 0 if n <= 1 else (index - start) / (n - 1)
    return [round(_clamp(start + step * i, 0, 100), 1) for i in range(n)]


def _load_emergent_rows() -> list[dict]:
    rows: list[dict] = []
    if not EMERGENT_TECH_DIR.exists():
        return rows

    for path in sorted(EMERGENT_TECH_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        power = payload.get("power") or payload.get("power_usage") or {}
        water = payload.get("water") or payload.get("water_usage") or {}
        pollution = payload.get("air_pollution") or payload.get("pollution") or {}

        rows.append(
            {
                "stem": path.stem,
                "name": _title_from_stem(path.stem),
                "source": str(payload.get("source", TECH_CONFIG.get("defaults", {}).get("unknownSource", "Unknown source"))),
                "learn": payload.get("learn") if isinstance(payload.get("learn"), dict) else {},
                "power_consumption": _safe_float(power.get("power_consumption", power.get("total_electricity_kwh", 0))),
                "power_growth": _safe_float(power.get("avg_growth_rate", power.get("avg_growth", 0))),
                "water_consumption": _safe_float(water.get("water_consumption", water.get("total_water_kgal", 0))),
                "water_growth": _safe_float(water.get("avg_growth_rate", water.get("avg_growth", 0))),
                "pollution_value": _safe_float(pollution.get("pm25_concentration", pollution.get("total_ghg_mt_co2e", 0))),
                "pollution_growth": _safe_float(pollution.get("avg_growth_rate", pollution.get("avg_growth", 0))),
            }
        )
    return rows


def _load_forecast_rows() -> list[dict]:
    rows: list[dict] = []

    if NY_TIMESERIES_PATH.exists():
        try:
            payload = json.loads(NY_TIMESERIES_PATH.read_text(encoding="utf-8"))
            for row in payload.get("time_series", []):
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
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            rows = []

    if rows:
        rows.sort(key=lambda item: item["year"])
        return rows

    if not CSV_FALLBACK_PATH.exists():
        return []

    with CSV_FALLBACK_PATH.open(newline="", encoding="utf-8") as file_handle:
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


def _build_series_from_rows(rows: list[dict], value_key: str) -> dict:
    historical_rows = [row for row in rows if row.get("data_type") == "historical"]
    forecast_rows = [row for row in rows if row.get("data_type") == "forecast"]

    if not historical_rows or not forecast_rows:
        return {"historical": [], "projected": []}

    reference_year = max(row["year"] for row in historical_rows)

    historical = [
        {
            "month": (row["year"] - reference_year) * 12,
            "value": round(float(row[value_key]), 2),
        }
        for row in historical_rows
    ]

    projected = []
    for row in forecast_rows:
        value = float(row[value_key])
        confidence = _clamp(float(row.get("confidence", 1.0)), 0.0, 1.0)
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


def _scale_series(series: dict, multiplier: float) -> dict:
    return {
        "historical": [
            {
                "month": point["month"],
                "value": round(point["value"] * multiplier, 2),
            }
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


def _load_regions() -> list[str]:
    regions = {TECH_CONFIG.get("defaults", {}).get("globalRegion", "Global")}
    if not CITIES_DIR.exists():
        return [TECH_CONFIG.get("defaults", {}).get("globalRegion", "Global")]

    for path in CITIES_DIR.glob("*.json"):
        if path.stem.endswith("_timeseries"):
            continue
        regions.add(_title_from_stem(path.stem))

    return sorted(regions)


def _build_catalog():
    emergent_rows = _load_emergent_rows()
    defaults = TECH_CONFIG.get("defaults", {})
    labels = TECH_CONFIG.get("labels", {})
    thresholds = TECH_CONFIG.get("thresholds", {})

    if not emergent_rows:
        return [], {}, {}, {
            "technologiesModeled": 0,
            "highRiskAlerts": 0,
            "regionsUnderStress": 0,
            "lastModelUpdate": datetime.now(timezone.utc).isoformat(),
        }, defaults.get("emptySummary", "No emergent technology data was found in the data folder."), [defaults.get("globalRegion", "Global")]

    max_power = max((row["power_consumption"] for row in emergent_rows), default=1.0) or 1.0
    max_water = max((row["water_consumption"] for row in emergent_rows), default=1.0) or 1.0
    max_pollution = max((row["pollution_value"] for row in emergent_rows), default=1.0) or 1.0

    forecast_rows = _load_forecast_rows()
    power_series = _build_series_from_rows(forecast_rows, "power_kwh")
    water_series = _build_series_from_rows(forecast_rows, "water_kgal")
    pollution_series = _build_series_from_rows(forecast_rows, "co2_kg")

    categories_index: dict[str, dict] = {}
    trajectory_cache: dict[str, dict] = {}
    flat: list[dict] = []

    for row in emergent_rows:
        category_id, category_name, category_desc = _category_for_stem(row["stem"])

        power_index = round(_clamp((row["power_consumption"] / max_power) * 100.0, 0, 100), 1)
        water_index = round(_clamp((row["water_consumption"] / max_water) * 100.0, 0, 100), 1)
        pollution_index = round(_clamp((row["pollution_value"] / max_pollution) * 100.0, 0, 100), 1)

        externality_risk = round(
            _clamp((power_index * 0.4) + (water_index * 0.35) + (pollution_index * 0.25), 0, 100),
            1,
        )

        tech = {
            "id": _slug(row["stem"]),
            "name": row["name"],
            "description": f"Source dataset: {row['source']}",
            "source": row["source"],
            "power": {
                "forecastIndex": power_index,
                "delta": round(row["power_growth"], 1),
                "mwDemand": f"{(row['power_consumption'] / 1_000_000):.1f} {labels.get('mwDemandSuffix', 'MW-equivalent')}",
                "gridCarbonIndex": round(_clamp(pollution_index, 0, 100), 1),
                "loadConcentrationRisk": (
                    labels.get("loadConcentration", {}).get("high", "High")
                    if power_index >= thresholds.get("loadConcentration", {}).get("high", 70)
                    else labels.get("loadConcentration", {}).get("moderate", "Moderate")
                    if power_index >= thresholds.get("loadConcentration", {}).get("moderate", 40)
                    else labels.get("loadConcentration", {}).get("low", "Low")
                ),
                "sparkline": _build_sparkline(power_index, row["power_growth"]),
            },
            "pollution": {
                "forecastIndex": pollution_index,
                "delta": round(row["pollution_growth"], 1),
                "emissionDelta": f"{labels.get('pollutionPrefix', 'PM2.5')} {row['pollution_value']:.2f}",
                "toxicityTier": (
                    labels.get("toxicityTier", {}).get("tier1", "Tier 1")
                    if pollution_index >= thresholds.get("toxicityTier", {}).get("tier1", 75)
                    else labels.get("toxicityTier", {}).get("tier2", "Tier 2")
                    if pollution_index >= thresholds.get("toxicityTier", {}).get("tier2", 50)
                    else labels.get("toxicityTier", {}).get("tier3", "Tier 3")
                ),
                "wasteBurden": (
                    labels.get("wasteBurden", {}).get("high", "High")
                    if pollution_index >= thresholds.get("wasteBurden", {}).get("high", 70)
                    else labels.get("wasteBurden", {}).get("moderate", "Moderate")
                    if pollution_index >= thresholds.get("wasteBurden", {}).get("moderate", 40)
                    else labels.get("wasteBurden", {}).get("low", "Low")
                ),
                "sparkline": _build_sparkline(pollution_index, row["pollution_growth"]),
            },
            "water": {
                "forecastIndex": water_index,
                "delta": round(row["water_growth"], 1),
                "cubicMetersYear": f"{(row['water_consumption'] / 1_000_000):.2f}{labels.get('waterYearSuffix', 'M units/yr')}",
                "scarcityExposure": round(_clamp(water_index, 0, 100), 1),
                "contaminationProb": round(_clamp(pollution_index / 100.0, 0.0, 1.0), 2),
                "sparkline": _build_sparkline(water_index, row["water_growth"]),
            },
            "externalityRisk": externality_risk,
            "region": defaults.get("globalRegion", "Global"),
            "forecastHorizon": defaults.get("defaultForecastHorizon", "24m"),
            "category": category_name,
            "categoryId": category_id,
            "learn": {
                "description": str(row.get("learn", {}).get("description", "")).strip(),
                "significance": str(row.get("learn", {}).get("significance", "")).strip(),
                "valueAdd": str(row.get("learn", {}).get("valueAdd", "")).strip(),
            },
        }

        scale_power = max(0.2, power_index / 65.0)
        scale_water = max(0.2, water_index / 65.0)
        scale_pollution = max(0.2, pollution_index / 65.0)
        trajectory_cache[tech["id"]] = {
            "power": _scale_series(power_series, scale_power),
            "pollution": _scale_series(pollution_series, scale_pollution),
            "water": _scale_series(water_series, scale_water),
        }

        category = categories_index.get(category_id)
        if not category:
            category = {
                "id": category_id,
                "name": category_name,
                "description": category_desc,
                "technologies": [],
            }
            categories_index[category_id] = category

        category["technologies"].append(tech)
        flat.append(tech)

    categories = sorted(categories_index.values(), key=lambda item: item["name"])
    flat_sorted = sorted(flat, key=lambda item: item["externalityRisk"], reverse=True)

    high_risk_alerts = sum(1 for item in flat_sorted if item["externalityRisk"] >= thresholds.get("highRiskAlert", 70))
    top_names = ", ".join(item["name"] for item in flat_sorted[:3])

    engine_status = {
        "technologiesModeled": len(flat_sorted),
        "highRiskAlerts": high_risk_alerts,
        "regionsUnderStress": len(_load_regions()) - 1,
        "lastModelUpdate": datetime.now(timezone.utc).isoformat(),
    }

    macro_template = defaults.get(
        "macroSummaryTemplate",
        "Technology forecasts are now sourced from data/emergent_tech. Highest current externality pressure appears in: {top_names}.",
    )
    macro_summary = macro_template.format(top_names=top_names or "N/A")

    return categories, {item["id"]: item for item in flat_sorted}, trajectory_cache, engine_status, macro_summary, _load_regions()


_CATEGORIES, _TECH_INDEX, TRAJECTORY_CACHE, ENGINE_STATUS, MACRO_SUMMARY, REGIONS = _build_catalog()
CATEGORIES = _CATEGORIES


def get_all_technologies_flat():
    """Return a flat list of all technologies with category metadata."""
    return [
        {
            **tech,
            "category": tech["category"],
            "categoryId": tech["categoryId"],
        }
        for tech in _TECH_INDEX.values()
    ]


def _build_drivers(tech: dict) -> list[dict]:
    driver_labels = TECH_CONFIG.get("labels", {}).get("driverLabels", {})
    return [
        {"label": driver_labels.get("source", "Source"), "value": tech.get("source", TECH_CONFIG.get("defaults", {}).get("unknownSource", "Unknown source"))},
        {"label": driver_labels.get("powerGrowth", "Power Growth"), "value": f"{tech['power']['delta']:+.1f}%"},
        {"label": driver_labels.get("waterGrowth", "Water Growth"), "value": f"{tech['water']['delta']:+.1f}%"},
        {"label": driver_labels.get("pollutionGrowth", "Pollution Growth"), "value": f"{tech['pollution']['delta']:+.1f}%"},
        {"label": driver_labels.get("riskScore", "Risk Score"), "value": f"{tech['externalityRisk']:.1f}"},
    ]


def get_technology_by_id(tech_id: str):
    """Find a technology by ID and attach trajectory + metadata details."""
    tech = _TECH_INDEX.get(tech_id)
    if not tech:
        return None

    return {
        **tech,
        "trajectory": TRAJECTORY_CACHE.get(tech_id, {"power": {}, "pollution": {}, "water": {}}),
        "drivers": _build_drivers(tech),
        "regionSensitivity": [],
    }
