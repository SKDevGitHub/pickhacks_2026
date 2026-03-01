import requests
import json
import random
import math
from datetime import datetime

# ── helpers ──────────────────────────────────────────────────────────────────

def _float(val):
    try:
        return float(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None

def _int(val):
    try:
        return int(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None

def socrata_get(domain, dataset_id, params=None, limit=50000):
    url = f"https://{domain}/resource/{dataset_id}.json"
    p = {"$limit": limit}
    if params:
        p.update(params)
    resp = requests.get(url, params=p, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ── city metadata ─────────────────────────────────────────────────────────────
# populations by year (approximate, used for synthetic scaling)
CITY_POP = {
    "New York":   {y: int(8_200_000 + (y - 2016) * 15_000)  for y in range(2016, 2027)},
    "Los Angeles":{y: int(3_980_000 + (y - 2016) * 5_000)   for y in range(2016, 2027)},
    "Chicago":    {y: int(2_690_000 - (y - 2016) * 8_000)   for y in range(2016, 2027)},
    "Phoenix":    {y: int(1_570_000 + (y - 2016) * 22_000)  for y in range(2016, 2027)},
    "St. Louis":  {y: int(302_000   - (y - 2016) * 1_200)   for y in range(2016, 2027)},
}

START_YEAR = datetime.utcnow().year - 9
END_YEAR   = datetime.utcnow().year

# ════════════════════════════════════════════════════════════════════
#  WATER  —  real sources
# ════════════════════════════════════════════════════════════════════

def fetch_water_nyc_real():
    """NYC DEP annual water consumption, dataset ia2d-e54m."""
    print("  [NYC water] fetching real data...")
    rows = socrata_get("data.cityofnewyork.us", "ia2d-e54m")
    out = {}
    for r in rows:
        yr = str(r.get("year", "")).strip()
        if not yr:
            continue
        out[yr] = {
            "total_mgd":      _float(r.get("nyc_consumption_million_gallons_per_day")),
            "per_capita_gpd": _float(r.get("per_capita_gallons_per_person_per_day")),
            "population":     _int(r.get("new_york_city_population")),
            "source":         "real — NYC DEP Open Data"
        }
    return out


def fetch_water_la_real():
    """
    CA Water Board — Per-Supplier monthly CSV, filtered to LADWP.
    Direct CSV download (no API key needed).
    Aggregates monthly acre-feet to annual totals.
    """
    print("  [LA water] fetching CA Water Board CSV...")
    url = (
        "https://data.ca.gov/dataset/c69ac02b-adfb-459a-bc58-bf69a8b572d2"
        "/resource/f4d50112-5fb5-4066-b45c-44696b10a49e"
        "/download/monthly_combined_dataset.csv"
    )
    try:
        import csv, io
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        annual = {}

        for row in reader:
            # Supplier name column — filter to LADWP rows only
            supplier = (row.get("Supplier Name") or row.get("supplier_name") or "").strip()
            if "Los Angeles" not in supplier and "LADWP" not in supplier:
                continue

            # Reporting month column — format is typically "YYYY-MM-DD" or "MM/YYYY"
            date_str = (row.get("Reporting Month") or row.get("reporting_month") or "").strip()
            year = date_str[:4] if "-" in date_str else date_str[-4:]
            if not year.isdigit():
                continue

            # Total potable water production in acre-feet
            val = _float(
                row.get("Total Potable Water Production") or
                row.get("total_potable_water_production_af") or
                row.get("Potable Water Production (AF)")
            )
            if val is not None:
                annual.setdefault(year, 0.0)
                annual[year] += val

        if annual:
            return {
                yr: {"total_acre_feet": round(v, 2), "source": "real — CA Water Board per-supplier CSV"}
                for yr, v in annual.items()
            }
        else:
            print("    No LADWP rows matched — falling back to synthetic")
            return {}

    except Exception as e:
        print(f"    CA Water Board CSV failed: {e} — falling back to synthetic")
        return {}
    
def fetch_water_chicago_real():
    """Chicago Energy Benchmarking — water_use_kgal summed per year."""
    print("  [Chicago water] fetching benchmarking data...")
    try:
        rows = socrata_get(
            "data.cityofchicago.org", "xq83-jr8c",
            params={"$select": "data_year,water_use_kgal",
                    "$where": "water_use_kgal IS NOT NULL"}
        )
        annual = {}
        for r in rows:
            yr  = str(r.get("data_year", "")).strip()
            val = _float(r.get("water_use_kgal"))
            if yr and val is not None:
                annual.setdefault(yr, 0.0)
                annual[yr] += val
        if annual:
            return {yr: {"total_kgal_large_buildings": round(v, 2),
                         "source": "real — Chicago Energy Benchmarking (buildings >50k sqft)"}
                    for yr, v in annual.items()}
    except Exception as e:
        print(f"    Chicago benchmarking failed: {e}")
    return {}

# ════════════════════════════════════════════════════════════════════
#  WATER  —  synthetic generators
# ════════════════════════════════════════════════════════════════════

# Anchor GPCD (gallons per capita per day) — all-sector (residential + commercial + industrial)
# Sources: Phoenix published data, peer-city utility reports, USGS estimates
WATER_GPCD_2020 = {
    # Phoenix: published 102 GPCD in 2020, declining ~1 GPCD/yr
    "Phoenix":   102,
    # St. Louis: Midwest average, Missouri American Water reports ~95 GPCD total
    "St. Louis": 95,
    # Fallback anchors if real data missing
    "New York":   99,   # NYC DEP ~99 GPCD in 2020
    "Los Angeles": 107, # LADWP ~107 GPCD 2020 (includes commercial)
    "Chicago":    86,   # ComEd / MWRD estimates
}
# Annual GPCD trend (negative = conservation gains)
WATER_GPCD_TREND = {
    "Phoenix":    -1.2,
    "St. Louis":  -0.5,
    "New York":   -0.4,
    "Los Angeles":-0.8,
    "Chicago":    -0.3,
}

def synthetic_water_annual(city, start_yr, end_yr, seed=42):
    """
    Generate synthetic annual water consumption (million gallons/day) using:
      total_MGD = population * GPCD / 1,000,000
    GPCD trends downward per conservation trajectory. ±2% noise added.
    """
    rng = random.Random(seed)
    gpcd_2020  = WATER_GPCD_2020[city]
    gpcd_trend = WATER_GPCD_TREND[city]
    out = {}
    for yr in range(start_yr, end_yr + 1):
        pop  = CITY_POP[city][yr]
        gpcd = gpcd_2020 + gpcd_trend * (yr - 2020)
        gpcd = max(gpcd, 60)  # floor — no city goes below 60 GPCD
        noise = 1 + rng.uniform(-0.02, 0.02)
        total_mgd = round(pop * gpcd / 1_000_000 * noise, 3)
        out[str(yr)] = {
            "total_mgd":      total_mgd,
            "per_capita_gpd": round(gpcd * noise, 1),
            "population":     pop,
            "source":         "synthetic — modelled from population × GPCD trend"
        }
    return out

# ════════════════════════════════════════════════════════════════════
#  ELECTRICITY  —  synthetic (monthly breakdown)
# ════════════════════════════════════════════════════════════════════

# Anchor: known annual total electricity consumption (billion kWh)
# Sources: Insider Monkey / utility reports cited above
ELEC_ANNUAL_GWH_2022 = {
    "New York":    55_000,   # NYC ~ 55 TWh (residential + commercial + industrial)
    "Los Angeles": 46_300,   # LADWP service area ~46.3 TWh
    "Chicago":     41_000,   # ComEd Chicago territory ~41 TWh
    "Phoenix":     24_800,   # APS + SRP ~24.8 TWh
    "St. Louis":    9_800,   # Ameren MO St. Louis territory ~9.8 TWh
}
# Annual growth rate (fraction)  — slight increases from data centers / EVs offsetting efficiency
ELEC_GROWTH = {
    "New York":     0.003,
    "Los Angeles":  0.005,
    "Chicago":      0.002,
    "Phoenix":      0.018,   # fast-growing city
    "St. Louis":    0.001,
}
# Monthly seasonal index (summer peak for hot cities, winter peak for cold cities)
# Values sum to 12.0 so annual / 12 * index = monthly share
MONTHLY_SEASONAL = {
    # Phoenix: extreme summer AC load
    "Phoenix":    [0.75, 0.77, 0.88, 1.00, 1.15, 1.30, 1.45, 1.42, 1.25, 1.05, 0.82, 0.76],
    # LA: mild year-round, slight summer peak
    "Los Angeles":[0.90, 0.87, 0.88, 0.90, 0.96, 1.05, 1.15, 1.18, 1.10, 1.00, 0.95, 0.96],
    # Chicago: dual summer/winter peaks
    "Chicago":    [1.10, 1.05, 0.90, 0.83, 0.88, 1.00, 1.15, 1.12, 0.97, 0.90, 0.98, 1.12],
    # NYC: similar to Chicago
    "New York":   [1.08, 1.02, 0.90, 0.85, 0.90, 1.02, 1.18, 1.15, 0.98, 0.90, 0.97, 1.05],
    # St. Louis: hot summers, cold winters
    "St. Louis":  [1.05, 1.00, 0.88, 0.83, 0.92, 1.05, 1.20, 1.18, 1.00, 0.88, 0.96, 1.05],
}

def synthetic_electricity_monthly(city, start_yr, end_yr, seed=7):
    """
    Generate monthly electricity consumption (GWh) anchored to known annual totals.
    Seasonal shape applied per city climate profile. ±1.5% noise per month.
    """
    rng     = random.Random(seed)
    anchor  = ELEC_ANNUAL_GWH_2022[city]
    growth  = ELEC_GROWTH[city]
    shape   = MONTHLY_SEASONAL[city]
    # Normalise shape so it sums to exactly 12
    shape_sum = sum(shape)
    shape = [s / shape_sum * 12 for s in shape]

    out = {}
    for yr in range(start_yr, end_yr + 1):
        annual_gwh = anchor * ((1 + growth) ** (yr - 2022))
        monthly_base = annual_gwh / 12
        out[str(yr)] = {}
        for m_idx in range(12):
            mo = f"{m_idx + 1:02d}"
            gwh = monthly_base * shape[m_idx] * (1 + rng.uniform(-0.015, 0.015))
            out[str(yr)][mo] = {
                "electricity_gwh": round(gwh, 2),
                "source": "synthetic — anchored to utility territory annual totals w/ seasonal profile"
            }
    return out

# ════════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════════

def build_all_data(start_yr, end_yr):
    result = {}

    # ── Water ────────────────────────────────────────────────────────
    print("\n=== WATER CONSUMPTION ===")

    nyc_real = fetch_water_nyc_real()
    # Filter to our year range and fill gaps with synthetic
    nyc_water = {}
    for yr in range(start_yr, end_yr + 1):
        key = str(yr)
        nyc_water[key] = nyc_real.get(key) or synthetic_water_annual("New York", yr, yr, seed=1)[key]
    result["New York"] = {"water": nyc_water}

    la_real = fetch_water_la_real()
    la_water = {}
    for yr in range(start_yr, end_yr + 1):
        key = str(yr)
        la_water[key] = la_real.get(key) or synthetic_water_annual("Los Angeles", yr, yr, seed=2)[key]
    result["Los Angeles"] = {"water": la_water}

    chi_real = fetch_water_chicago_real()
    chi_water = {}
    for yr in range(start_yr, end_yr + 1):
        key = str(yr)
        chi_water[key] = chi_real.get(key) or synthetic_water_annual("Chicago", yr, yr, seed=3)[key]
    result["Chicago"] = {"water": chi_water}

    # Phoenix & St. Louis — fully synthetic
    print("  [Phoenix water] generating synthetic data...")
    result["Phoenix"]   = {"water": synthetic_water_annual("Phoenix",   start_yr, end_yr, seed=4)}
    print("  [St. Louis water] generating synthetic data...")
    result["St. Louis"] = {"water": synthetic_water_annual("St. Louis", start_yr, end_yr, seed=5)}

    # ── Electricity ──────────────────────────────────────────────────
    print("\n=== ELECTRICITY CONSUMPTION ===")
    for city in ["New York", "Los Angeles", "Chicago", "Phoenix", "St. Louis"]:
        print(f"  [{city} electricity] generating synthetic monthly data...")
        result[city]["electricity"] = synthetic_electricity_monthly(city, start_yr, end_yr)

    return result


if __name__ == "__main__":
    print(f"Building city resource data {START_YEAR}–{END_YEAR}...")
    data = build_all_data(START_YEAR, END_YEAR)

    output_file = "city_resource_consumption.json"
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    # Print summary
    print(f"\n{'─'*55}")
    print(f"{'City':<15} {'Water years':>12} {'Elec months':>12}")
    print(f"{'─'*55}")
    for city, d in data.items():
        w_count = len(d.get("water", {}))
        e_count = sum(len(v) for v in d.get("electricity", {}).values())
        print(f"{city:<15} {w_count:>12} {e_count:>12}")
    print(f"{'─'*55}")
    print(f"\n✅ Saved {output_file}")