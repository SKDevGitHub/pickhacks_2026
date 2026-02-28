import json
from pathlib import Path


def _city_name_from_filename(path: Path) -> str:
    stem = path.stem.replace("_timeseries", "").strip()
    return _normalize_city_name(stem)


def _normalize_city_name(value: str) -> str:
    cleaned = str(value or "").strip()
    cleaned = cleaned.replace("_", " ").replace(".", " ").replace("-", " ")
    cleaned = " ".join(part for part in cleaned.split() if part)
    if not cleaned:
        return ""

    title = cleaned.title()
    title = title.replace("St ", "St. ")
    return title


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_city_stats(city_name: str, payload: dict) -> dict:
    city_name = _normalize_city_name(city_name)

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


def load_cities() -> list[dict]:
    root_dir = Path(__file__).resolve().parents[2]
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
