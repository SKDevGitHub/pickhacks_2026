"""
generate_robot_forecast.py
--------------------------
Calls the Anthropic API to forecast humanoid robot resource consumption
(2031-2050) based on historical data (2025-2030), then writes the full
2025-2050 dataset to robot_forecast_per_100k.csv.

Usage:
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."
    python generate_robot_forecast.py

    # Optional: custom output path
    python generate_robot_forecast.py --output data/robot_forecast_per_100k.csv
"""

import argparse
import csv
import json
import os
import sys

import anthropic

# ── Historical data ────────────────────────────────────────────────────────────

HISTORICAL = [
    # (year, adoption_per_100k, power_kwh, water_gal, co2_kg, use_case)
    (2025, 5,   4380, 65, 1950, "Pilot Logistics/Warehousing"),
    (2026, 12,  4820, 72, 2100, "Street Maintenance (Current)"),
    (2027, 45,  5200, 80, 2350, "Retail & Hospitality"),
    (2028, 110, 4100, 62, 1850, "Home Assistance (Efficiency Leap)"),
    (2029, 280, 3900, 58, 1720, "Elderly Care & Health"),
    (2030, 650, 3700, 55, 1600, "General City Service"),
]

# ── Prompt ─────────────────────────────────────────────────────────────────────

PROMPT = """You are an AI forecasting model for humanoid robotics adoption in urban environments.

Historical data per 100k people (2025-2030):
{historical}

Forecast all five metrics for every year from 2031 to 2050. Consider:

ADOPTION (units per 100k people):
- S-curve dynamics: rapid growth through mid-2030s, then saturation as market matures
- Manufacturing scale-up and cost reductions driving mass deployment
- Regulatory frameworks potentially throttling or accelerating adoption
- Competition between robot platforms converging on dominant designs

POWER (kWh per robot per year):
- 2027 peak was an architectural detour; 2028 efficiency leap continues
- Battery energy density improvements (solid-state ~2032, next-gen ~2038)
- Locomotion efficiency gains as gaits are optimised via RL
- Diminishing returns post-2040 as physics limits are approached

WATER (gallons per robot per year):
- Cooling and hydraulic fluid needs decline with dry-actuator designs
- Maintenance wash-down cycles reduce as self-cleaning surfaces emerge
- Manufacturing water footprint amortised over longer robot lifespans

CO2 (kg per robot per year):
- Tied to grid decarbonisation trajectory (significant drops post-2035)
- Embodied carbon in manufacturing reduces with recycled material supply chains
- Operational CO2 approaches near-zero as renewable grid dominates post-2042

PRIMARY USE CASE:
- Name the dominant deployment category for each year plausibly
- Should evolve from current city service toward more complex cognitive/social roles

Respond ONLY with a valid JSON object. No markdown fences, no explanation outside the JSON:
{{
  "reasoning": "3-4 sentence methodology explanation covering all five metrics",
  "confidence_note": "one sentence on forecast uncertainty",
  "forecasts": [
    {{
      "year": 2031,
      "adoption_per_100k": <number>,
      "power_kwh": <number>,
      "water_gal": <number>,
      "co2_kg": <number>,
      "use_case": "<primary use case label>",
      "confidence": <0.0-1.0>
    }}
  ]
}}"""


def build_prompt() -> str:
    hist_lines = "\n".join(
        f"  {year}: Adoption={adoption}/100k, Power={power} kWh, "
        f"Water={water} gal, CO2={co2} kg, Use='{use}'"
        for year, adoption, power, water, co2, use in HISTORICAL
    )
    return PROMPT.format(historical=hist_lines)


# ── API call ───────────────────────────────────────────────────────────────────

def fetch_forecast(api_key: str) -> tuple[list[dict], str, str]:
    """Call Claude and return (forecasts, reasoning, confidence_note)."""
    client = anthropic.Anthropic(api_key=api_key)

    print("Calling Anthropic API (claude-opus-4-6)...", flush=True)
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": build_prompt()}],
    )

    raw = message.content[0].text.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)
    return parsed["forecasts"], parsed.get("reasoning", ""), parsed.get("confidence_note", "")


# ── CSV writer ─────────────────────────────────────────────────────────────────

FIELDNAMES = [
    "Year",
    "Adoption_Units_Per_100k_People",
    "Power_kWh_Per_Robot_Year",
    "Water_Gallons_Per_Robot_Year",
    "CO2_kg_Per_Robot_Year",
    "Primary_Use_Case",
    "Data_Type",
    "Confidence",
]


def write_csv(output_path: str, forecasts: list[dict]):
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

        # Historical rows
        for year, adoption, power, water, co2, use in HISTORICAL:
            writer.writerow({
                "Year":                        year,
                "Adoption_Units_Per_100k_People": adoption,
                "Power_kWh_Per_Robot_Year":    power,
                "Water_Gallons_Per_Robot_Year": water,
                "CO2_kg_Per_Robot_Year":       co2,
                "Primary_Use_Case":            use,
                "Data_Type":                   "historical",
                "Confidence":                  "1.000",
            })

        # AI forecast rows
        for row in forecasts:
            writer.writerow({
                "Year":                        row["year"],
                "Adoption_Units_Per_100k_People": round(row["adoption_per_100k"], 1),
                "Power_kWh_Per_Robot_Year":    round(row["power_kwh"], 1),
                "Water_Gallons_Per_Robot_Year": round(row["water_gal"], 1),
                "CO2_kg_Per_Robot_Year":       round(row["co2_kg"], 1),
                "Primary_Use_Case":            row["use_case"],
                "Data_Type":                   "forecast",
                "Confidence":                  f"{row['confidence']:.3f}",
            })


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate AI-powered humanoid robot resource forecast CSV.")
    parser.add_argument("--output", "-o", default="robot_forecast_per_100k.csv",
                        help="Output CSV path (default: robot_forecast_per_100k.csv)")
    parser.add_argument("--api-key", default=os.environ.get("ANTHROPIC_API_KEY"),
                        help="Anthropic API key (defaults to ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    if not args.api_key:
        print("Error: Anthropic API key required.\n"
              "  Set ANTHROPIC_API_KEY env var or pass --api-key", file=sys.stderr)
        sys.exit(1)

    forecasts, reasoning, confidence_note = fetch_forecast(args.api_key)

    if len(forecasts) != 20:
        print(f"Warning: expected 20 forecast rows (2031-2050), got {len(forecasts)}", file=sys.stderr)

    write_csv(args.output, forecasts)

    print(f"\n✓ Written {len(HISTORICAL) + len(forecasts)} rows -> {args.output}")
    print(f"\n  Historical : 2025-2030  ({len(HISTORICAL)} rows)")
    print(f"  Forecast   : {forecasts[0]['year']}-{forecasts[-1]['year']}  ({len(forecasts)} rows)")
    print(f"\n  AI Reasoning:\n  {reasoning}")
    print(f"\n  Confidence note:\n  {confidence_note}")
    print(f"\n  Sample forecast values (per robot):")
    for row in forecasts:
        if row["year"] in (2031, 2035, 2040, 2045, 2050):
            print(
                f"    {row['year']}  "
                f"adoption={row['adoption_per_100k']:>7}/100k  "
                f"power={row['power_kwh']:>6} kWh  "
                f"water={row['water_gal']:>5} gal  "
                f"co2={row['co2_kg']:>6} kg  "
                f"conf={row['confidence']:.3f}  "
                f"use='{row['use_case']}'"
            )


if __name__ == "__main__":
    main()