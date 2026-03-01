import json
import re
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


def _compute_avg_growth(series: list[dict], key: str) -> float:
    """Compute average year-over-year growth rate from timeseries."""
    if len(series) < 2:
        return 0.0
    rates = []
    for i in range(1, len(series)):
        prev = _safe_float(series[i - 1].get(key))
        curr = _safe_float(series[i].get(key))
        if prev != 0:
            rates.append(((curr - prev) / prev) * 100.0)
    return round(sum(rates) / len(rates), 2) if rates else 0.0


def _normalize_city_stats(city_name: str, payload: dict) -> dict:
    """Build city stats from timeseries data."""
    city_name = _normalize_city_name(city_name)
    city_id = re.sub(r"[^a-z0-9]+", "-", city_name.lower()).strip("-")

    ts = payload.get("time_series", [])

    # Latest values from the most recent row
    latest = ts[-1] if ts else {}
    power_value = _safe_float(latest.get("power_kwh"))
    water_value = _safe_float(latest.get("water_kgal"))
    co2_value = _safe_float(latest.get("co2_kg"))

    power_growth = _compute_avg_growth(ts, "power_kwh")
    water_growth = _compute_avg_growth(ts, "water_kgal")
    co2_growth = _compute_avg_growth(ts, "co2_kg")

    return {
        "id": city_id,
        "name": city_name,
        "source": payload.get("source", "Unknown source"),
        "intersections": int(payload.get("intersections", 0) or 0),
        "cityFunds": _safe_float(payload.get("city_funds", 0)),
        "stats": {
            "power": {
                "value": power_value,
                "unit": "kWh",
                "avgGrowth": power_growth,
            },
            "water": {
                "value": water_value,
                "unit": "kgal",
                "avgGrowth": water_growth,
            },
            "pollution": {
                "value": co2_value,
                "unit": "kg CO₂",
                "avgGrowth": co2_growth,
            },
        },
        "timeSeries": ts,
    }


def load_cities() -> list[dict]:
    root_dir = Path(__file__).resolve().parents[2]
    cities_dir = root_dir / "data" / "cities"

    if not cities_dir.exists():
        return []

    cities_by_id = {}
    for path in sorted(cities_dir.glob("*_timeseries.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        city_name = str(payload.get("city", "")).strip() or _city_name_from_filename(path)
        normalized = _normalize_city_stats(city_name, payload)

        if normalized["id"] not in cities_by_id:
            cities_by_id[normalized["id"]] = normalized

    return sorted(cities_by_id.values(), key=lambda city: city["name"])
