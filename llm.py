from dotenv import load_dotenv
load_dotenv()
# from google import genai
# from google.genai import types
import os
import re
import db.database as db
from ollama import chat
import requests
import pandas

# gemini = genai.Client(api_key=os.getenv('GEMINI_KEY'))
census_api_key = os.getenv('CENSUS_API_KEY')

state_abbrev_to_fips = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
    "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
    "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
    "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
    "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
    "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56"
}

def intersections(city: str, state: str) -> int:
    if db.get_intersections(city, state) != -1:
        print(f"cached data for {city}, {state} found")
        return db.get_intersections(city, state)

    population = (
        "https://api.census.gov/data/2022/acs/acs5"
        "?get=NAME,B01003_001E"
        "&for=place:*"
        f"&in=state:{state_abbrev_to_fips[state.upper()]}"
        f"&key={census_api_key}"
    )

    popdata = requests.get(population)
    popdata = popdata.json()
    c = None
    for row in popdata[1:]:
        if f"{city} city" in row[0]:
            c = row
            break

    if not c:
        raise Exception(f"City {c} not fonud")

    pop = int(c[1])

    gaz_df = pandas.read_csv("./gaz/Gaz_places_national.txt", sep="\t", encoding="latin-1")
    gaz_df.columns = gaz_df.columns.str.strip()
    gaz_df["USPS"] = gaz_df["USPS"].str.strip()
    gaz_df["NAME"] = gaz_df["NAME"].str.strip()

    print(gaz_df[gaz_df["NAME"].str.contains(f"{city}", case=False)])
    city_row = gaz_df[
        (gaz_df["USPS"] == state.upper()) &
        (gaz_df["NAME"].str.lower().str.startswith(city.lower()))
    ]

    if city_row.empty:
        raise Exception(f"City {city} not found in GAZ")

    land_area = float(city_row.iloc[0]["ALAND"]) / 2589988

    print(f"No cache for {city}, {state} -> calling LLM")
    query = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": "You are a quantitative urban infrastructure estimation assistant. Perform explicit arithmetic reasoning. Do not invent placeholder values"
            },
            {
                "role": "user",
                "content": f"""
City: {city}
State: {state}
Population: {pop}
Land area: {land_area} sq mi

We know:
New York City has:
- Population: 8,622,467
- Land area: 302.64 sq mi
- 13,543 signalized intersections

Steps:

1) Compute NYC population density.
2) Compute target city population density.
3) Compute NYC signal density:
   nyc_signal_density = 13,543 / 302.64

4) Assume signal density scales proportionally with population density:
   city_signal_density =
   (city_density / nyc_density) × nyc_signal_density

5) Compute:
   total_intersections =
   city_signal_density × land_area

6) Round to nearest integer.

Show calculations clearly.

End with:
FINAL_ANSWER: <integer>
                """
            }
        ],
        options={"temperature": 0.15}
    )
    # query = gemini.models.generate_content(
    #     model="gemini-2.5-flash",
    #     # contents=f"Based on urban planning data for {city}, {state}, {country}, what is the approximate total number of street intersections within the city limits? Provide your best statistical estimate as a single integer. Do not return a range or text. If unknown, return -1.",
    #     contents=f"Please estimate the total number of street intersections within the city limits of {city}, {state}. Please provide your best statistical estimate as a single integer. If the Google Maps API is not sufficient, please just give a best guess from what you know.",
    #     config=types.GenerateContentConfig(
    #         tools=[types.Tool(google_maps=types.GoogleMaps())],
    #         temperature=0.0
    #     )
    # )

    query_text = query["message"]["content"]
    if not query_text:
        print(f"err (prompt fail): {query}")
        return -1

    # print(f"\n\033[38;2;180;180;180m\n\n{query_text}\n\033[0m")

    query2 = chat(
        model="llama3.1:8b",
        messages=[
            {
                "role": "system",
                "content": "Extract only the integer that appears after \'FINAL_ANSWER:\' in the previous message. Output only digits. If there is nothing, output -1."
            },
            {
                "role": "user",
                "content": query_text
            }
        ],
        options={"temperature": 0.0}
    )
    query_text = query2["message"]["content"]
    if not query_text:
        print(f"err (extract fail): {query2}")
        return -1

    x = re.search(r'\d+', query_text.replace(',', ''))
    if x and int(x.group()) > 10:
        db.cache_intersections(city, state, int(x.group()))
        return int(x.group())
    else:
        print(f"err: {query}")
        return -1

if __name__ == '__main__':
    print("running tests:")
    print(f"new york intersections: {intersections('New York', 'NY')}")
    print(f"phoenix intersections: {intersections('Phoenix', 'AZ')}")
    print(f"rolla intersections: {intersections('Rolla', 'MO')}")
    print(f"chicago intersections: {intersections('Chicago', 'IL')}")
    print(f" intersections: {intersections('Los Angeles', 'CA')}")
