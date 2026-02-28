import psycopg
from dotenv import load_dotenv
import os
import atexit
import sys
import json
import pandas
load_dotenv()

conn = psycopg.connect(
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST'),
    port=5432
)

def wipe():
    with conn.cursor() as cursor:
        cursor.execute("""
            DROP TABLE IF EXISTS greenness;
        """)
        # old name
        cursor.execute("""
            DROP TABLE IF EXISTS green;
        """)
        cursor.execute("""
            DROP TABLE IF EXISTS city;
        """)
    conn.commit()


if len(sys.argv) > 1 and sys.argv[1] == "wipe":
    print("wiping db")
    wipe()
    sys.exit(0)

with conn.cursor() as cursor:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS city (
        name TEXT NOT NULL, state TEXT NOT NULL, intersections INT, 
        jsondata JSONB,

        PRIMARY KEY (name, state));
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS greenness (
            technology TEXT NOT NULL,
            year INT NOT NULL,

            power_kwh DOUBLE PRECISION NOT NULL,
            water_kgal DOUBLE PRECISION NOT NULL,
            co2_kg DOUBLE PRECISION NOT NULL,

            PRIMARY KEY (technology, year)
        );
    """)
conn.commit()

def set_json(city: str, state: str, path: str):
    if os.path.exists(path):
        with open(path, 'r') as f:
            data = json.load(f)
    else:
        print(f"file {path} not found")
        return

    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE city SET jsondata = %s WHERE name = %s AND state = %s
        """, (data, city, state))
    conn.commit()

def get_json(city: str, state: str) -> dict:
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT jsondata FROM city WHERE name = %s AND state = %s
        """, (city, state))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return {}

def set_greenness(technology: str, year: int, power_kwh: float, water_kgal: float, co2_kg: float):
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO greenness (technology, year, power_kwh, water_kgal, co2_kg)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (technology, year)
            DO UPDATE SET power_kwh = %s, water_kgal = %s, co2_kg = %s
        """, (technology, year, power_kwh, water_kgal, co2_kg, power_kwh, water_kgal, co2_kg))
    conn.commit()
    
# Returns [[year, power, water, co2], ...]
def get_greenness_all_years(technology: str) -> list[list]:
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                year, power_kwh, water_kgal, co2_kg
                FROM greenness WHERE technology = %s
            ORDER BY year;
        """, (technology,))
        result = [list(row) for row in cursor.fetchall()]
        if result:
            return result
        else:
            return []

def transfer_csv(technology: str, path: str):
    csv = pandas.read_csv(path)
    for _, row in csv.iterrows():
        set_greenness(technology, int(row["year"]), int(row["power_kwh"]), int(row["water_kgal"]), int(row["co2_kg"]))
    #     print(row["year"], row["power_kwh"], row["water_kgal"], row["co2_kg"])

def get_intersections(city: str, state: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT intersections FROM city WHERE name = %s AND state = %s
        """, (city, state))
        result = cursor.fetchone()
        if result:
            return result[0]
        else:
            return -1

def cache_intersections(city: str, state: str, intersections: int):
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO city (name, state, intersections)
            VALUES (%s, %s, %s)
            ON CONFLICT (name, state)
            DO UPDATE SET intersections = %s
        """, (city, state, intersections, intersections))
    conn.commit()

atexit.register(conn.close)

if __name__ == '__main__':
    transfer_csv("intersections", "./data/forecast_per_intersection.csv")
    print("... Intersections")
    for i in get_greenness_all_years("intersections"):
        for v in i:
            print(v, end="\t")
        print()
