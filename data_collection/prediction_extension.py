import os
import json
import numpy as np
from sklearn.linear_model import LinearRegression

INPUT_DIR = "data/cities"
OUTPUT_DIR = "output"
END_YEAR = 2050

os.makedirs(OUTPUT_DIR, exist_ok=True)

def extend_timeseries_to_2050(data, end_year=2050):
    ts = data["time_series"]

    years = np.array([row["year"] for row in ts]).reshape(-1, 1)
    power = np.array([row["power_kwh"] for row in ts])
    water = np.array([row["water_kgal"] for row in ts])
    co2 = np.array([row["co2_kg"] for row in ts])

    power_model = LinearRegression().fit(years, power)
    water_model = LinearRegression().fit(years, water)
    co2_model = LinearRegression().fit(years, co2)

    last_year = max(row["year"] for row in ts)
    future_years = np.arange(last_year + 1, end_year + 1).reshape(-1, 1)

    power_pred = power_model.predict(future_years)
    water_pred = water_model.predict(future_years)
    co2_pred = co2_model.predict(future_years)

    for i, year in enumerate(future_years.flatten()):
        ts.append({
            "year": int(year),
            "power_kwh": int(power_pred[i]),
            "water_kgal": float(round(water_pred[i], 1)),
            "co2_kg": int(co2_pred[i])
        })

    return data


def process_folder(input_dir, output_dir):
    for filename in os.listdir(input_dir):
        if not filename.endswith(".json"):
            continue
        if not filename.endswith("_timeseries.json"):  
            continue

        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        with open(input_path, "r") as f:
            data = json.load(f)

        extended_data = extend_timeseries_to_2050(data)

        with open(output_path, "w") as f:
            json.dump(extended_data, f, indent=4)

        print(f"Processed: {filename} → {output_path}")


if __name__ == "__main__":
    process_folder(INPUT_DIR, OUTPUT_DIR)