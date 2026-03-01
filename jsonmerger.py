import json
from datetime import datetime

CO2_KG_PER_KWH = 0.4  # adjust if needed

def format_time_series(city_data_file, air_file, city):
    with open(city_data_file) as f:
        city_data = json.load(f)

    with open(air_file) as f:
        air_data = json.load(f)

    water_years = set(city_data[city]["water"].keys())
    elec_years = set(city_data[city]["electricity"].keys())
    air_years = set(air_data[city].keys())

    years = water_years & elec_years & air_years
    current_year = datetime.now().year

    time_series = []

    for year in sorted(years):
        # ---- Water (yearly) ----
        water_obj = city_data[city]["water"][year]

        if "total_mgd" in water_obj:
            mgd = water_obj["total_mgd"]
            water_kgal = round(mgd * 365 * 1000, 2)
        elif "total_kgal_large_buildings" in water_obj:
            water_kgal = round(water_obj["total_kgal_large_buildings"], 2)
        else:
            raise KeyError(f"No water total found for {city} {year}")
        # ---- Electricity (sum months * 1000) ----
        monthly = city_data[city]["electricity"][year]
        total_gwh = sum(m["electricity_gwh"] for m in monthly.values())
        power_kwh = round(total_gwh * 1000)

        # ---- CO2 (derived) ----
        co2_kg = round(power_kwh * CO2_KG_PER_KWH)

        # ---- Metadata ----
        year_int = int(year)
        time_series.append({"year": year_int,"power_kwh": power_kwh,"water_kgal": water_kgal,"co2_kg": co2_kg,
        })

    return { "time_series": time_series }


# ---- Usage ----
if __name__ == "__main__":
    result = format_time_series(
        "data/timeseries_folder/New_York_energy_consumption.json",
        "openaq_city_monthly_avg.json",
        "New York, US"
    )

    with open("formatted_output.json", "w") as f:
        json.dump(result, f, indent=2)

    print("✅ formatted_output.json created")