"""
Technology data loader for Chartr AI.

Technology metadata comes from data/emergent_tech/*.json (source, learn info,
static resource values).  Time-series data comes from data/cities/*_timeseries.json
which contain yearly {year, power_kwh, water_kgal, co2_kg} rows.

Each technology is allocated a proportional share of a city's environmental
footprint based on its static resource values.  The Explorer view uses the
average across all cities; the Forecasts view uses a single city.
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

CURRENT_YEAR = datetime.now().year
HISTORICAL_CUTOFF = CURRENT_YEAR  # years <= this are "historical"


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


# ── City timeseries loader ───────────────────────────────────────────────

def _load_city_timeseries() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Load all *_timeseries.json city files.

    Returns:
        (city_timeseries, city_metadata)
        city_timeseries: {city_id: [{year, power_kwh, water_kgal, co2_kg}, ...]}
        city_metadata:   {city_id: {population: int, intersections: int}}
    """
    cities: dict[str, list[dict]] = {}
    meta: dict[str, dict] = {}
    if not CITIES_DIR.exists():
        return cities, meta

    for path in sorted(CITIES_DIR.glob("*_timeseries.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        raw_ts = payload.get("time_series", [])
        if not raw_ts:
            continue

        rows: list[dict] = []
        for r in raw_ts:
            try:
                rows.append({
                    "year": int(r["year"]),
                    "power_kwh": float(r.get("power_kwh", 0)),
                    "water_kgal": float(r.get("water_kgal", 0)),
                    "co2_kg": float(r.get("co2_kg", 0)),
                })
            except (KeyError, TypeError, ValueError):
                continue
        rows.sort(key=lambda x: x["year"])

        # Derive city id from filename: chicago_timeseries.json -> chicago
        stem = path.stem.replace("_timeseries", "")
        city_id = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
        cities[city_id] = rows
        meta[city_id] = {
            "population": int(payload.get("population", 0)),
            "intersections": int(payload.get("intersections", 0)),
            "city_funds": float(payload.get("city_funds", 0)),
        }

    return cities, meta


def _average_timeseries(all_city_ts: dict[str, list[dict]]) -> list[dict]:
    """Compute per-year average across all cities."""
    if not all_city_ts:
        return []

    year_sums: dict[int, dict] = {}
    year_counts: dict[int, int] = {}

    for rows in all_city_ts.values():
        for r in rows:
            y = r["year"]
            if y not in year_sums:
                year_sums[y] = {"power_kwh": 0.0, "water_kgal": 0.0, "co2_kg": 0.0}
                year_counts[y] = 0
            year_sums[y]["power_kwh"] += r["power_kwh"]
            year_sums[y]["water_kgal"] += r["water_kgal"]
            year_sums[y]["co2_kg"] += r["co2_kg"]
            year_counts[y] += 1

    averaged: list[dict] = []
    for y in sorted(year_sums.keys()):
        n = year_counts[y]
        averaged.append({
            "year": y,
            "power_kwh": round(year_sums[y]["power_kwh"] / n, 2),
            "water_kgal": round(year_sums[y]["water_kgal"] / n, 2),
            "co2_kg": round(year_sums[y]["co2_kg"] / n, 2),
        })
    return averaged


# ── Tech metadata loader ─────────────────────────────────────────────────

def _load_tech_metadata() -> list[dict]:
    """Load metadata + static resource values from each emergent tech JSON."""
    techs: list[dict] = []
    if not EMERGENT_TECH_DIR.exists():
        return techs

    for path in sorted(EMERGENT_TECH_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        techs.append({
            "stem": path.stem,
            "name": _title_from_stem(path.stem),
            "source": str(payload.get("source", TECH_CONFIG.get("defaults", {}).get("unknownSource", "Unknown source"))),
            "learn": payload.get("learn") if isinstance(payload.get("learn"), dict) else {},
            "power_usage": _safe_float(payload.get("power_usage"), 1.0),
            "water_usage": _safe_float(payload.get("water_usage"), 1.0),
            "co2_emissions": _safe_float(payload.get("co2_emissions"), 1.0),
            "cost_of_implementation": _safe_float(payload.get("cost of implementation", payload.get("cost_of_implementation")), 0.0),
            "units_per_million_pop": _safe_float(payload.get("units_per_million_pop"), 0.0),
            "scale_by": str(payload.get("scale_by", "population")),
        })
    return techs


# ── Timeseries → tech allocation helpers ──────────────────────────────────

def _compute_units(tech_meta: dict, city_meta: dict, scale: float = 1.0) -> float:
    """Compute the number of deployed units for a technology in a city.

    - AI Intersections (scale_by="intersections"): uses the city's intersection count.
    - All others: uses (population / 1_000_000) * units_per_million_pop.
    The result is multiplied by the user-provided *scale* factor.
    """
    if tech_meta.get("scale_by") == "intersections":
        units = float(city_meta.get("intersections", 0))
    else:
        pop = float(city_meta.get("population", 0))
        units = (pop / 1_000_000.0) * tech_meta.get("units_per_million_pop", 0.0)
    return units * scale


def _allocate_timeseries(
    city_ts: list[dict],
    tech_meta: dict,
    city_meta: dict,
    scale: float = 1.0,
) -> list[dict]:
    """
    Produce a per-technology timeseries by adding the technology's resource
    impact on top of the city's baseline values for each year.

    displayed_value = city_baseline[year] + (per_unit_cost × num_units)

    This way the graphs reflect the city's natural growth trend plus
    the constant overhead introduced by the technology deployment.
    """
    num_units = _compute_units(tech_meta, city_meta, scale)

    tech_power = tech_meta["power_usage"] * num_units
    tech_water = tech_meta["water_usage"] * num_units
    tech_co2 = tech_meta["co2_emissions"] * num_units

    allocated: list[dict] = []
    for row in city_ts:
        year = row["year"]
        is_forecast = year > HISTORICAL_CUTOFF

        allocated.append({
            "year": year,
            "power_kwh": round(row["power_kwh"] + tech_power, 2),
            "water_kgal": round(row["water_kgal"] + tech_water, 2),
            "co2_kg": round(row["co2_kg"] + tech_co2, 2),
            "data_type": "historical" if not is_forecast else "forecast",
        })
    return allocated


def _latest_historical_value(rows: list[dict], key: str) -> float:
    hist = [r for r in rows if r.get("data_type") == "historical"]
    if not hist:
        return rows[-1][key] if rows else 0.0
    return float(hist[-1][key])


def _yoy_delta(rows: list[dict], key: str) -> float:
    """Percentage change from the current (last historical) year to 10 years ahead."""
    hist = [r for r in rows if r.get("data_type") == "historical"]
    if not hist:
        return 0.0
    current_row = hist[-1]
    current_val = float(current_row[key])
    if current_val == 0:
        return 0.0

    target_year = current_row["year"] + 10
    # Find the forecast row closest to target_year
    forecast = [r for r in rows if r.get("data_type") == "forecast"]
    if not forecast:
        return 0.0
    future_row = min(forecast, key=lambda r: abs(r["year"] - target_year))
    future_val = float(future_row[key])
    return round(((future_val - current_val) / current_val) * 100.0, 1)


def _sparkline_from_rows(rows: list[dict], key: str) -> list[float]:
    return [round(float(r[key]), 2) for r in rows]


def _build_trajectory(rows: list[dict], value_key: str) -> dict:
    historical_rows = [r for r in rows if r.get("data_type") == "historical"]
    forecast_rows = [r for r in rows if r.get("data_type") == "forecast"]

    if not historical_rows:
        return {"historical": [], "projected": []}

    reference_year = max(r["year"] for r in historical_rows)

    historical = [
        {"month": (r["year"] - reference_year) * 12, "value": round(float(r[value_key]), 2)}
        for r in historical_rows
    ]

    projected = [
        {"month": (r["year"] - reference_year) * 12, "value": round(float(r[value_key]), 2)}
        for r in forecast_rows
    ]

    return {"historical": historical, "projected": projected}


# ── Regions ──────────────────────────────────────────────────────────────

def _load_regions() -> list[str]:
    regions = {TECH_CONFIG.get("defaults", {}).get("globalRegion", "Global")}
    for city_id in _ALL_CITY_TIMESERIES:
        regions.add(city_id.replace("-", " ").title().replace("St ", "St. "))
    return sorted(regions)


# ── Build catalog ────────────────────────────────────────────────────────

def _build_catalog(timeseries: list[dict], tech_metadata: list[dict], city_meta: dict | None = None, scale: float = 1.0):
    """
    Build the full catalog of categories & technologies from a given
    timeseries (either a specific city's or the cross-city average).

    Returns (categories, tech_index, trajectory_cache, engine_status, macro_summary).
    """
    defaults = TECH_CONFIG.get("defaults", {})
    labels = TECH_CONFIG.get("labels", {})
    thresholds = TECH_CONFIG.get("thresholds", {})

    if city_meta is None:
        city_meta = {"population": 0, "intersections": 0}

    if not tech_metadata or not timeseries:
        return [], {}, {}, {
            "technologiesModeled": 0,
            "regionsUnderStress": 0,
            "lastModelUpdate": datetime.now(timezone.utc).isoformat(),
        }, defaults.get("emptySummary", "No emergent technology data was found in the data folder.")

    # Allocate city timeseries to each tech
    tech_rows: list[dict] = []
    for meta in tech_metadata:
        ts = _allocate_timeseries(timeseries, meta, city_meta, scale)
        if not ts:
            continue
        num_units = _compute_units(meta, city_meta, scale)
        total_cost = meta["cost_of_implementation"] * num_units  # M$ total
        tech_rows.append({
            **meta,
            "timeseries": ts,
            "num_units": num_units,
            "total_cost": total_cost,
            "latest_power": _latest_historical_value(ts, "power_kwh"),
            "latest_water": _latest_historical_value(ts, "water_kgal"),
            "latest_co2": _latest_historical_value(ts, "co2_kg"),
            "power_delta": _yoy_delta(ts, "power_kwh"),
            "water_delta": _yoy_delta(ts, "water_kgal"),
            "co2_delta": _yoy_delta(ts, "co2_kg"),
        })

    if not tech_rows:
        return [], {}, {}, {
            "technologiesModeled": 0,
            "regionsUnderStress": 0,
            "lastModelUpdate": datetime.now(timezone.utc).isoformat(),
        }, defaults.get("emptySummary", "No emergent technology data was found in the data folder.")

    categories_index: dict[str, dict] = {}
    trajectory_cache: dict[str, dict] = {}
    flat: list[dict] = []

    for row in tech_rows:
        category_id, category_name, category_desc = _category_for_stem(row["stem"])

        ts = row["timeseries"]

        tech = {
            "id": _slug(row["stem"]),
            "name": row["name"],
            "description": f"Source dataset: {row['source']}",
            "source": row["source"],
            "power": {
                "forecastIndex": round(row["latest_power"], 1),
                "unit": "kWh",
                "delta": row["power_delta"],
                "sparkline": _sparkline_from_rows(ts, "power_kwh"),
            },
            "pollution": {
                "forecastIndex": round(row["latest_co2"], 1),
                "unit": "kg CO₂",
                "delta": row["co2_delta"],
                "sparkline": _sparkline_from_rows(ts, "co2_kg"),
            },
            "water": {
                "forecastIndex": round(row["latest_water"], 1),
                "unit": "kgal",
                "delta": row["water_delta"],
                "sparkline": _sparkline_from_rows(ts, "water_kgal"),
            },
            "region": defaults.get("globalRegion", "Global"),
            "category": category_name,
            "categoryId": category_id,
            "cost": {
                "perUnit": round(row["cost_of_implementation"], 4),
                "total": round(row["total_cost"], 2),
                "unit": "M$",
                "units": round(row["num_units"], 1),
            },
            "scaling": {
                "method": row.get("scale_by", "population"),
                "unitsPerMillionPop": row.get("units_per_million_pop", 0),
            },
            "learn": {
                "description": str(row.get("learn", {}).get("description", "")).strip(),
                "significance": str(row.get("learn", {}).get("significance", "")).strip(),
                "valueAdd": str(row.get("learn", {}).get("valueAdd", "")).strip(),
            },
        }

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

    return categories, {item["id"]: item for item in flat_sorted}, trajectory_cache, engine_status, macro_summary


# ── Module-level data ─────────────────────────────────────────────────────

_ALL_CITY_TIMESERIES, _ALL_CITY_META = _load_city_timeseries()
_AVG_TIMESERIES = _average_timeseries(_ALL_CITY_TIMESERIES)
_TECH_METADATA = _load_tech_metadata()

# Average city metadata (for Explorer cross-city view)
def _average_city_meta(all_meta: dict[str, dict]) -> dict:
    if not all_meta:
        return {"population": 0, "intersections": 0}
    n = len(all_meta)
    return {
        "population": int(sum(m["population"] for m in all_meta.values()) / n),
        "intersections": int(sum(m["intersections"] for m in all_meta.values()) / n),
    }

_AVG_CITY_META = _average_city_meta(_ALL_CITY_META)

# Pre-build catalogs: "average" for Explorer + one per city for Forecasts
_CATALOGS: dict[str, tuple] = {}

_avg_result = _build_catalog(_AVG_TIMESERIES, _TECH_METADATA, _AVG_CITY_META)
_CATALOGS["__average__"] = _avg_result

for _cid, _cts in _ALL_CITY_TIMESERIES.items():
    _CATALOGS[_cid] = _build_catalog(_cts, _TECH_METADATA, _ALL_CITY_META.get(_cid))

# Default (average) exports for backward compatibility
CATEGORIES = _avg_result[0]
ENGINE_STATUS = _avg_result[3]
MACRO_SUMMARY = _avg_result[4]
REGIONS = _load_regions()


# ── Public API ────────────────────────────────────────────────────────────

def _get_catalog(city: str | None = None, scale: float = 1.0) -> tuple:
    """Return the catalog tuple for a city, or the cross-city average.

    If *scale* != 1.0 the catalog is rebuilt on-the-fly with the
    user-provided unit multiplier.
    """
    # Resolve city id
    if not city:
        cid = "__average__"
    elif city in _CATALOGS:
        cid = city
    else:
        cid = re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")
        if cid not in _CATALOGS:
            cid = "__average__"

    # Default scale → use pre-built
    if scale == 1.0:
        return _CATALOGS.get(cid, _CATALOGS["__average__"])

    # Rebuild with custom scale
    if cid == "__average__":
        return _build_catalog(_AVG_TIMESERIES, _TECH_METADATA, _AVG_CITY_META, scale)
    ts = _ALL_CITY_TIMESERIES.get(cid, _AVG_TIMESERIES)
    cm = _ALL_CITY_META.get(cid, _AVG_CITY_META)
    return _build_catalog(ts, _TECH_METADATA, cm, scale)


def get_categories(city: str | None = None, scale: float = 1.0) -> list[dict]:
    """Return category list, optionally scoped to a city."""
    catalog = _get_catalog(city, scale)
    return catalog[0]


def get_all_technologies_flat(city: str | None = None, scale: float = 1.0) -> list[dict]:
    """Return a flat list of all technologies, optionally scoped to a city."""
    catalog = _get_catalog(city, scale)
    tech_index = catalog[1]
    return [
        {**tech, "category": tech["category"], "categoryId": tech["categoryId"]}
        for tech in tech_index.values()
    ]


def get_technology_by_id(tech_id: str, city: str | None = None, scale: float = 1.0):
    """Find a technology by ID and attach trajectory + metadata details."""
    catalog = _get_catalog(city, scale)
    tech_index = catalog[1]
    trajectory_cache = catalog[2]

    tech = tech_index.get(tech_id)
    if not tech:
        return None

    return {
        **tech,
        "trajectory": trajectory_cache.get(tech_id, {"power": {}, "pollution": {}, "water": {}}),
        "drivers": _build_drivers(tech),
        "regionSensitivity": [],
    }


def _build_drivers(tech: dict) -> list[dict]:
    driver_labels = TECH_CONFIG.get("labels", {}).get("driverLabels", {})
    return [
        {"label": driver_labels.get("source", "Source"), "value": tech.get("source", TECH_CONFIG.get("defaults", {}).get("unknownSource", "Unknown source"))},
        {"label": driver_labels.get("powerGrowth", "Power Growth"), "value": f"{tech['power']['delta']:+.1f}%"},
        {"label": driver_labels.get("waterGrowth", "Water Growth"), "value": f"{tech['water']['delta']:+.1f}%"},
        {"label": driver_labels.get("pollutionGrowth", "Pollution Growth"), "value": f"{tech['pollution']['delta']:+.1f}%"},
    ]


def get_city_meta(city: str | None = None) -> dict:
    """Return metadata (population, intersections, city_funds) for a city."""
    if not city:
        return _AVG_CITY_META
    cid = re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")
    return _ALL_CITY_META.get(cid, _AVG_CITY_META)


def get_budget_breakdown(city: str | None = None, scale: float = 1.0) -> dict:
    """Return city budget vs total tech deployment cost."""
    cm = get_city_meta(city)
    city_funds = cm.get("city_funds", 0)
    techs = get_all_technologies_flat(city, scale)
    items = []
    total_cost = 0.0
    for t in techs:
        cost = t.get("cost", {}).get("total", 0)
        total_cost += cost
        items.append({
            "id": t["id"],
            "name": t["name"],
            "cost": round(cost, 2),
        })
    items.sort(key=lambda x: x["cost"], reverse=True)
    return {
        "cityFunds": city_funds,
        "totalTechCost": round(total_cost, 2),
        "pctOfBudget": round((total_cost / city_funds) * 100, 1) if city_funds else 0,
        "technologies": items,
    }
