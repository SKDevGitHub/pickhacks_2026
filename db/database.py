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
            DROP TABLE IF EXISTS city;
        """)
    conn.commit()
    sys.exit(0)

with conn.cursor() as cursor:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS 
        city (name TEXT NOT NULL, state TEXT NOT NULL, intersections INT, 
        jsondata JSONB,
        PRIMARY KEY (name, state));
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
