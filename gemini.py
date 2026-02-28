from dotenv import load_dotenv
load_dotenv()
from google import genai
from google.genai import types
import os
import re
import db.database as db

gemini = genai.Client(api_key=os.getenv('GEMINI_KEY'))

def intersections(city: str, state: str) -> int:
    if db.get_intersections(city, state) != -1:
        print(f"cached data for {city}, {state} found")
        return db.get_intersections(city, state)
    print(f"No cache for {city}, {state} -> calling gemini")
    query = gemini.models.generate_content(
        model="gemini-2.5-flash",
        # contents=f"Based on urban planning data for {city}, {state}, {country}, what is the approximate total number of street intersections within the city limits? Provide your best statistical estimate as a single integer. Do not return a range or text. If unknown, return -1.",
        contents=f"Please estimate the total number of street intersections within the city limits of {city}, {state}. Please provide your best statistical estimate as a single integer. If the Google Maps API is not sufficient, please just give a best guess from what you know.",
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_maps=types.GoogleMaps())],
            temperature=0.0
        )
    )

    if not query or not query.text:
        print(f"err (prompt fail): {query}")
        return -1

    x = re.search(r'\d+', query.text.replace(',', ''))
    if x and int(x.group()) > 10:
        db.cache_intersections(city, state, int(x.group()))
        return int(x.group())
    else:
        print(f"err: {query.text}")
        return -1

if __name__ == '__main__':
    print("running tests:")
    print(f"new york intersections: {intersections('New York', 'NY')}")
    print(f"phoenix intersections: {intersections('Phoenix', 'AZ')}")
    print(f"rolla intersections: {intersections('Rolla', 'MO')}")
