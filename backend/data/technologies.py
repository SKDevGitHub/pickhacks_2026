"""
Technology data loader for Chartr AI.

Each technology JSON in data/emergent_tech/ MUST include a ``time_series``
array.  Every row has:

    { "year": 2023, "power_kwh": 82, "water_kgal": 0.85, "co2_kg": 32,
      "data_type": "historical"|"forecast", "scenario": "actual"|"baseline",
      "confidence": 1.0 }

Sparklines, index scores, deltas, and trajectory charts are all computed
directly from this real data — no synthetic generation.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
EMERGENT_TECH_DIR = ROOT_DIR / "data" / "emergent_tech"
CITIES_DIR = ROOT_DIR / "data" / "cities"
TECH_CONFIG_PATH = ROOT_DIR / "data" / "technology_config.json"


# ── Config ────────────────────────────────────────────────────────────────

def _default_config() -> dict:
    return {
        "defaults": {
            "unknownSource": "Unknown source",
            "globalRegion": "Global",
            "emptySummary": "No emergent technology data was found in the data folder.",
            "macroSummaryTemplate": "Highest current externality pressure appears in: {top_names}.",
        },
        "thresholds": {
            "loadConcentration": {"high": 70, "moderate": 40},
            "toxicityTier": {"tier1": 75, "tier2": 50},
            "wasteBurden": {"high": 70, "moderate": 40},
        },
        "labels": {
            "mwDemandSuffix": "MW-equivalent",
            "waterYearSuffix": "M units/yr",
            "pollutionPrefix": "CO₂",
            "loadConcentration": {"high": "High", "moderate": "Moderate", "low": "Low"},
            "toxicityTier": {"tier1": "Tier 1", "tier2": "Tier 2", "tier3": "Tier 3"},
            "wasteBurden": {"high": "High", "moderate": "Moderate", "low": "Low"},
            "driverLabels": {
                "source": "Source",
                "powerGrowth": "Power Growth",
                "waterGrowth": "Water Growth",
                "pollutionGrowth": "Pollution Growth",
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


# ── Helpers ───────────────────────────────────────────────────────────────

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


# ── Timeseries helpers ────────────────────────────────────────────────────

def _parse_timeseries(raw_rows: list[dict]) -> list[dict]:
    """Parse and sort a time_series array from a tech JSON."""
    rows: list[dict] = []
    for r in raw_rows:
        try:
            rows.append({
                "year": int(r["year"]),
                "power_kwh": float(r["power_kwh"]),
                "water_kgal": float(r["water_kgal"]),
                "co2_kg": float(r["co2_kg"]),
                "data_type": str(r.get("data_type", "historical")).strip().lower(),
                "scenario": str(r.get("scenario", "")).strip().lower(),
                "confidence": float(r.get("confidence", 1.0) or 1.0),
            })
        except (KeyError, TypeError, ValueError):
            continue
    rows.sort(key=lambda x: x["year"])
    return rows


def _latest_historical_value(rows: list[dict], key: str) -> float:
    """Return the most recent historical value for *key*, or 0."""
    hist = [r for r in rows if r["data_type"] == "historical"]
    if not hist:
        return 0.0
    return float(hist[-1][key])


def _yoy_delta(rows: list[dict], key: str) -> float:
    """Compute YoY % change between the last two historical points."""
    hist = [r for r in rows if r["data_type"] == "historical"]
    if len(hist) < 2:
        return 0.0
    prev = float(hist[-2][key])
    curr = float(hist[-1][key])
    if prev == 0:
        return 0.0
    return round(((curr - prev) / prev) * 100.0, 1)


def _sparkline_from_timeseries(rows: list[dict], key: str) -> list[float]:
    """Extract the raw yearly values as sparkline data (all points)."""
    return [round(float(r[key]), 2) for r in rows]


def _build_trajectory(rows: list[dict], value_key: str) -> dict:
    """Build historical + projected series for TrajectoryChart."""
    historical_rows = [r for r in rows if r["data_type"] == "historical"]
    forecast_rows = [r for r in rows if r["data_type"] == "forecast"]

    if not historical_rows:
        return {"historical": [], "projected": []}

    reference_year = max(r["year"] for r in historical_rows)

    historical = [
        {"month": (r["year"] - reference_year) * 12, "value": round(float(r[value_key]), 2)}
        for r in historical_rows
    ]

    projected = []
    for r in forecast_rows:
        value = float(r[value_key])
        confidence = _clamp(float(r.get("confidence", 1.0)), 0.0, 1.0)
        margin = max(1.0, value * (1.0 - confidence))
        projected.append({
            "month": (r["year"] - reference_year) * 12,
            "value": round(value, 2),
            "upper": round(value + margin, 2),
            "lower": round(max(0.0, value - margin), 2),
        })

    return {"historical": historical, "projected": projected}


# ── Load emergent tech rows ──────────────────────────────────────────────

def _load_emergent_rows() -> list[dict]:
    rows: list[dict] = []
    if not EMERGENT_TECH_DIR.exists():
        return rows

    for path in sorted(EMERGENT_TECH_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        ts_raw = payload.get("time_series", [])
        if not ts_raw:
            continue  # skip techs without timeseries data

        ts = _parse_timeseries(ts_raw)
        if not ts:
            continue

        rows.append({
            "stem": path.stem,
            "name": _title_from_stem(path.stem),
            "source": str(payload.get("source", TECH_CONFIG.get("defaults", {}).get("unknownSource", "Unknown source"))),
            "learn": payload.get("learn") if isinstance(payload.get("learn"), dict) else {},
            "research_frequency": payload.get("research_frequency", {}),
            "vc_frequency": payload.get("vc_frequency", {}),
            "timeseries": ts,
            "latest_power": _latest_historical_value(ts, "power_kwh"),
            "latest_water": _latest_historical_value(ts, "water_kgal"),
            "latest_co2": _latest_historical_value(ts, "co2_kg"),
            "power_delta": _yoy_delta(ts, "power_kwh"),
            "water_delta": _yoy_delta(ts, "water_kgal"),
            "co2_delta": _yoy_delta(ts, "co2_kg"),
        })
    return rows


# ── Regions ──────────────────────────────────────────────────────────────

def _load_regions() -> list[str]:
    regions = {TECH_CONFIG.get("defaults", {}).get("globalRegion", "Global")}
    if not CITIES_DIR.exists():
        return [TECH_CONFIG.get("defaults", {}).get("globalRegion", "Global")]
    for path in CITIES_DIR.glob("*.json"):
        if path.stem.endswith("_timeseries"):
            continue
        regions.add(_title_from_stem(path.stem))
    return sorted(regions)


# ── Build catalog ────────────────────────────────────────────────────────

def _build_catalog():
    emergent_rows = _load_emergent_rows()
    defaults = TECH_CONFIG.get("defaults", {})
    labels = TECH_CONFIG.get("labels", {})
    thresholds = TECH_CONFIG.get("thresholds", {})

    if not emergent_rows:
        return [], {}, {}, {
            "technologiesModeled": 0,
            "regionsUnderStress": 0,
            "lastModelUpdate": datetime.now(timezone.utc).isoformat(),
        }, defaults.get("emptySummary", "No emergent technology data was found in the data folder."), [defaults.get("globalRegion", "Global")]

    # Normalise to 0–100 relative to the max across all technologies
    max_power = max((r["latest_power"] for r in emergent_rows), default=1.0) or 1.0
    max_water = max((r["latest_water"] for r in emergent_rows), default=1.0) or 1.0
    max_co2 = max((r["latest_co2"] for r in emergent_rows), default=1.0) or 1.0

    categories_index: dict[str, dict] = {}
    trajectory_cache: dict[str, dict] = {}
    flat: list[dict] = []

    for row in emergent_rows:
        category_id, category_name, category_desc = _category_for_stem(row["stem"])

        power_index = round(_clamp((row["latest_power"] / max_power) * 100.0, 0, 100), 1)
        water_index = round(_clamp((row["latest_water"] / max_water) * 100.0, 0, 100), 1)
        pollution_index = round(_clamp((row["latest_co2"] / max_co2) * 100.0, 0, 100), 1)

        ts = row["timeseries"]

        tech = {
            "id": _slug(row["stem"]),
            "name": row["name"],
            "description": f"Source dataset: {row['source']}",
            "source": row["source"],
            "power": {
                "forecastIndex": power_index,
                "delta": row["power_delta"],
                "mwDemand": f"{row['latest_power']:.1f} kWh",
                "gridCarbonIndex": round(_clamp(pollution_index, 0, 100), 1),
                "loadConcentrationRisk": (
                    labels.get("loadConcentration", {}).get("high", "High")
                    if power_index >= thresholds.get("loadConcentration", {}).get("high", 70)
                    else labels.get("loadConcentration", {}).get("moderate", "Moderate")
                    if power_index >= thresholds.get("loadConcentration", {}).get("moderate", 40)
                    else labels.get("loadConcentration", {}).get("low", "Low")
                ),
                "sparkline": _sparkline_from_timeseries(ts, "power_kwh"),
            },
            "pollution": {
                "forecastIndex": pollution_index,
                "delta": row["co2_delta"],
                "emissionDelta": f"{labels.get('pollutionPrefix', 'CO₂')} {row['latest_co2']:.2f} kg",
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
                "sparkline": _sparkline_from_timeseries(ts, "co2_kg"),
            },
            "water": {
                "forecastIndex": water_index,
                "delta": row["water_delta"],
                "cubicMetersYear": f"{row['latest_water']:.2f} kgal",
                "scarcityExposure": round(_clamp(water_index, 0, 100), 1),
                "contaminationProb": round(_clamp(pollution_index / 100.0, 0.0, 1.0), 2),
                "sparkline": _sparkline_from_timeseries(ts, "water_kgal"),
            },
            "region": defaults.get("globalRegion", "Global"),
            "category": category_name,
            "categoryId": category_id,
            "learn": {
                "description": str(row.get("learn", {}).get("description", "")).strip(),
                "significance": str(row.get("learn", {}).get("significance", "")).strip(),
                "valueAdd": str(row.get("learn", {}).get("valueAdd", "")).strip(),
            },
        }

        # Per-tech trajectory from its own timeseries
        trajectory_cache[tech["id"]] = {
            "power": _build_trajectory(ts, "power_kwh"),
            "pollution": _build_trajectory(ts, "co2_kg"),
            "water": _build_trajectory(ts, "water_kgal"),
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
    flat_sorted = sorted(flat, key=lambda item: item["power"]["forecastIndex"], reverse=True)

    top_names = ", ".join(item["name"] for item in flat_sorted[:3])

    engine_status = {
        "technologiesModeled": len(flat_sorted),
        "regionsUnderStress": len(_load_regions()) - 1,
        "lastModelUpdate": datetime.now(timezone.utc).isoformat(),
    }

    macro_template = defaults.get(
        "macroSummaryTemplate",
        "Highest current externality pressure appears in: {top_names}.",
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
