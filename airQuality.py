import requests
import time
import json
import os
from datetime import datetime

BASE_URL = "https://api.openaq.org/v3"

HEADERS = {
    "X-API-Key": os.getenv("OPENAQ_API_KEY")
}

if not HEADERS["X-API-Key"]:
    raise RuntimeError("OPENAQ_API_KEY not set. Run: export OPENAQ_API_KEY=your_key")

CITY_BBOX = {
    ("Los Angeles", "US"): (-118.6682, 33.7037, -118.1554, 34.3373),
    ("New York",     "US"): (-74.2591,  40.4774, -73.7002,  40.9176),
    ("Chicago",      "US"): (-87.9401,  41.6445, -87.5241,  42.0230),
    ("Phoenix",      "US"): (-112.3241, 33.2948, -111.9253, 33.9207),
    ("St. Louis",    "US"): (-90.3202,  38.5328, -90.1650,  38.7741),
    ("London",       "GB"): (-0.5104,   51.2868,  0.3340,   51.6919),
    ("Delhi",        "IN"): (76.8389,   28.4041,  77.3490,  28.8831),
}

# param name -> (parameter_id, list of alternate name strings from API)
PARAM_VARIANTS = {
    "pm25": (2,  ["pm25", "pm2.5", "PM2.5", "PM25"]),
    "pm10": (1,  ["pm10", "PM10"]),
    "no2":  (5,  ["no2",  "NO2"]),
    "o3":   (10, ["o3",   "O3", "ozone"]),
}

_rate_state = {"remaining": 60, "reset_in": 1}


def _smart_request(url, params=None):
    if _rate_state["remaining"] <= 2:
        wait = max(_rate_state["reset_in"], 1)
        print(f"\n  [rate limit] quota low — waiting {wait}s...")
        time.sleep(wait)

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f"\n  [network error] {e}, retrying...")
            time.sleep(2)
            continue

        try:
            _rate_state["remaining"] = int(resp.headers.get("x-ratelimit-remaining", 60))
            _rate_state["reset_in"]  = int(resp.headers.get("x-ratelimit-reset", 1))
        except (ValueError, TypeError):
            pass

        if resp.status_code == 429:
            wait = _rate_state["reset_in"] + 2
            print(f"\n  [429] rate limited — sleeping {wait}s...")
            time.sleep(wait)
            continue

        if resp.status_code == 422:
            raise RuntimeError(f"422 Unprocessable: {url}\nparams={params}\n{resp.text}")

        if not resp.ok:
            print(f"\n  [warn] {resp.status_code} for {url}")
            return None

        return resp.json()

    return None


def get_sensors_for_city(city, country, target_params, start_year):
    bbox = CITY_BBOX.get((city, country))
    if bbox is None:
        raise RuntimeError(f"No bounding box for ({city}, {country}).")

    min_lon, min_lat, max_lon, max_lat = bbox

    data = _smart_request(
        f"{BASE_URL}/locations",
        {"bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}", "limit": 100}
    )
    if data is None:
        raise RuntimeError(f"Could not fetch locations for {city}, {country}")

    locations = data.get("results", [])
    print(f"  Found {len(locations)} stations in bbox")

    # Build lookup structures from PARAM_VARIANTS
    id_to_param   = {v[0]: k for k, v in PARAM_VARIANTS.items()}   # int id  -> "pm25"
    name_to_param = {}                                               # str name -> "pm25"
    for canonical, (pid, variants) in PARAM_VARIANTS.items():
        for v in variants:
            name_to_param[v.lower()] = canonical

    # param -> (sensor_id, datetimeFirst) — keep sensor with most history
    best = {}

    for loc in locations:
        for sensor in loc.get("sensors", []):
            try:
                sid        = sensor["id"]
                param_blk  = sensor.get("parameter") or {}
                param_id   = param_blk.get("id")       # int e.g. 2
                param_name = param_blk.get("name", "")  # str e.g. "pm25"

                # Resolve to canonical name via ID first, name as fallback
                canonical = id_to_param.get(param_id) or name_to_param.get(param_name.lower())

                if canonical is None or canonical not in target_params:
                    continue

                dt_first = (sensor.get("datetimeFirst") or
                            loc.get("datetimeFirst") or {}).get("utc", "9999")

                prev_sid, prev_dt = best.get(canonical, (None, "9999"))
                if dt_first < prev_dt:
                    best[canonical] = (sid, dt_first)

            except Exception as e:
                print(f"\n  [warn] error parsing sensor {sensor}: {e}")
                continue

    result = {}
    for p in target_params:
        if p in best:
            sid, dt_first = best[p]
            result[p] = sid
            print(f"  ✓ {p}: sensor {sid}  (data from {dt_first[:10]})")
        else:
            print(f"  ✗ {p}: no sensor found")

    if not result:
        # Print ALL unique parameter ids/names seen across all stations to help diagnose
        seen_params = set()
        for loc in locations:
            for s in loc.get("sensors", []):
                pb = s.get("parameter") or {}
                seen_params.add((pb.get("id"), pb.get("name")))
        print(f"\n  All parameter (id, name) pairs seen across {len(locations)} stations:")
        for pair in sorted(seen_params):
            print(f"    {pair}")
        raise RuntimeError(f"No sensors matched {target_params} for {city}, {country}.")

    return result


def fetch_sensor_monthly(sensor_id, year, month):
    last_day = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    if month == 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        last_day = 29

    data = _smart_request(
        f"{BASE_URL}/sensors/{sensor_id}/days",
        {
            "date_from": f"{year}-{month:02d}-01",
            "date_to":   f"{year}-{month:02d}-{last_day}",
            "limit": 31
        }
    )

    if data is None:
        return None

    values = [
        r["value"] for r in data.get("results", [])
        if r.get("value") is not None and r["value"] >= 0
    ]
    return round(sum(values) / len(values), 4) if values else None


def fetch_monthly_avg_for_city(city, country, parameters, start_year, end_year):
    param_sensors = get_sensors_for_city(city, country, set(parameters), start_year)

    city_results = {}
    total_months = (end_year - start_year + 1) * 12
    done = 0

    for year in range(start_year, end_year + 1):
        city_results[str(year)] = {}

        for month in range(1, 13):
            city_results[str(year)][f"{month:02d}"] = {}

            for param in parameters:
                sid = param_sensors.get(param)
                val = fetch_sensor_monthly(sid, year, month) if sid else None
                city_results[str(year)][f"{month:02d}"][param] = val

            done += 1
            print(
                f"  {year}-{month:02d}  {done/total_months*100:.0f}%  "
                f"[quota: {_rate_state['remaining']}]   ",
                end="\r", flush=True
            )

        print(f"\n  ✓ {year} complete")

    return city_results


if __name__ == "__main__":
    cities = [
        ("Los Angeles", "US"),
        ("New York",    "US"),
        ("Chicago",     "US"),
        ("Phoenix",     "US"),
        ("St. Louis",   "US"),
    ]

    pollutants = ["pm25", "pm10", "no2", "o3"]

    end_year   = datetime.utcnow().year
    start_year = end_year - 9

    all_data = {}

    for city, country in cities:
        print(f"\n--- Fetching data for {city}, {country} ({start_year}–{end_year}) ---")
        try:
            all_data[f"{city}, {country}"] = fetch_monthly_avg_for_city(
                city=city,
                country=country,
                parameters=pollutants,
                start_year=start_year,
                end_year=end_year
            )
        except Exception as e:
            print(f"\n⚠️  Failed for {city}, {country}: {e}")
            all_data[f"{city}, {country}"] = {}

    output_file = "openaq_city_monthly_avg.json"
    with open(output_file, "w") as f:
        json.dump(all_data, f, indent=2)

    print(f"\n✅ Saved {output_file}")