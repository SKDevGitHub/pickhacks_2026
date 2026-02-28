import google.generativeai as genai
import csv
import json
import io
import os
from dotenv import load_dotenv
load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv('GEMINI_KEY')
OUTPUT_FILE = "ai_campus_projections.csv"
START_YEAR = 2024
NUM_YEARS = 20  # How many years to project

# Base data from AI campus metrics
BASE_DATA = {
    "power": {
        "power_consumption": 600_000_000,  # Watts
        "avg_growth_rate": 3.5             # % per year
    },
    "water": {
        "water_consumption": 140_000_000,  # Liters per day
        "avg_growth_rate": 2.0             # % per year
    },
    "air_pollution": {
        "pm25_concentration": 2.0,         # µg/m³
        "avg_growth_rate": 1.6             # % per year
    }
}

# ─── Prompt ───────────────────────────────────────────────────────────────────
PROMPT = f"""
You are a data analyst specializing in AI infrastructure environmental impact.

Given the following base metrics for a typical AI campus in {START_YEAR}:

{json.dumps(BASE_DATA, indent=2)}

Generate a CSV dataset projecting these values from {START_YEAR} to {START_YEAR + NUM_YEARS - 1}.

Rules:
- Apply the avg_growth_rate (%) compounding year over year for each metric.
- Add realistic variation: ±0.5% random noise to each year's growth rate to make it feel real.
- Round power_consumption_W to the nearest 1,000.
- Round water_consumption_L to the nearest 1,000.
- Round pm25_concentration to 3 decimal places.
- Include a "notes" column with brief contextual commentary for notable years (e.g., major scaling events, efficiency improvements, regulations). Leave blank for ordinary years.

Output ONLY a raw CSV with these exact columns (no markdown, no explanation):
year,power_consumption_W,water_consumption_L,pm25_concentration_ugm3

Start immediately with the header row.
"""

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("Configuring Gemini...")
    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel("gemini-1.5-flash")

    print(f"Requesting {NUM_YEARS}-year projection from Gemini...")
    response = model.generate_content(PROMPT)
    raw_text = response.text.strip()

    # Strip markdown code fences if Gemini wraps in them
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(
            line for line in lines
            if not line.startswith("```")
        ).strip()

    # Validate it looks like CSV
    reader = csv.DictReader(io.StringIO(raw_text))
    rows = list(reader)

    if not rows:
        print("ERROR: Gemini returned no data rows. Raw response:\n")
        print(raw_text)
        return

    print(f"✓ Received {len(rows)} rows of data.")

    # Write to file
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✓ CSV saved to: {OUTPUT_FILE}")

    # Preview first 5 rows
    print("\nPreview (first 5 rows):")
    print(",".join(reader.fieldnames))
    for row in rows[:5]:
        print(",".join(str(row[k]) for k in reader.fieldnames))


if __name__ == "__main__":
    main()