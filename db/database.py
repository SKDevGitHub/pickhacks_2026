import psycopg
from dotenv import load_dotenv
import os
import atexit
import sys
import json
load_dotenv()

conn = psycopg.connect(
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    host=os.getenv('DB_HOST'),
    port=5432
)

if len(sys.argv) > 1 and sys.argv[1] == "wipe":
    print("wiping db")
    with conn.cursor() as cursor:
        cursor.execute("""
            DROP TABLE IF EXISTS green;
        """)
        cursor.execute("""
            DROP TABLE IF EXISTS city;
        """)
    conn.commit()
    sys.exit(0)

with conn.cursor() as cursor:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS city (
        name TEXT NOT NULL, state TEXT NOT NULL, intersections INT, 
        jsondata JSONB,

        PRIMARY KEY (name, state));
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS green (
            year INT NOT NULL,
            power_kwh DOUBLE PRECISION NOT NULL,
            water_kgal DOUBLE PRECISION NOT NULL,
            co2_kg DOUBLE PRECISION NOT NULL,

            PRIMARY KEY (year)
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

def set_green(year: int, power_kwh: float, water_kgal: float, co2_kg: float):
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO green (year, power_kwh, water_kgal, co2_kg)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (year)
            DO UPDATE SET power_kwh = %s, water_kgal = %s, co2_kg = %s
        """, (year, power_kwh, water_kgal, co2_kg, power_kwh, water_kgal, co2_kg))
    conn.commit()
    
def get_green() -> list:
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT
                year, power_kwh, water_kgal, co2_kg
                FROM green
            ORDER BY year;
        """)
        result = [list(row) for row in cursor.fetchall()]
        if result:
            return result
        else:
            return []

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
