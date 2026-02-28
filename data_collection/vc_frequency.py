from collections import defaultdict
import requests
import re
import time

BASE_URL = "https://api.openalex.org/works"

def contains_kw(title, kw):
    return re.search(rf"\b{re.escape(kw.lower())}\b", title.lower()) is not None

def vc_funding_signal_by_tech(tech_groups, max_pages=10):
    freq_by_tech = defaultdict(lambda: defaultdict(int))
    cursor = "*"
    pages = 0

    # Flatten all keywords for quick checking
    all_keywords = [kw for kws in tech_groups.values() for kw in kws]

    while cursor and pages < max_pages:
        resp = requests.get(
            BASE_URL,
            params={
                "filter": "title.search:venture capital OR funding OR investment,publication_year:2010-2025",
                "per-page": 200,
                "cursor": cursor
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        for paper in data.get("results", []):
            title = (paper.get("title") or "").lower()
            year = paper.get("publication_year")
            if not year:
                continue

            matched_keywords = [kw for kw in all_keywords if contains_kw(title, kw)]
            for tech, kws in tech_groups.items():
                if any(kw in kws for kw in matched_keywords):
                    freq_by_tech[year][tech] += 1

        cursor = data["meta"].get("next_cursor")
        pages += 1
        time.sleep(0.3)

    return freq_by_tech

technology_groups = {
    "AI-Campus": ["ai", "big data", "smart campus", "machine learning", "deep learning"],
    "AI intersections": ["intersection", "smart city", "urban iot", "traffic ai"],
    "Autonomous vehicles": ["autonomous vehicle", "self-driving", "robotic car", "driverless"],
    "Data_Centers": ["data center", "cloud", "high performance computing"],
    "Robotics": ["robotics", "robotic", "automation", "drone","humanoid","robotic arm"],
    "Semiconductor plants": ["semiconductor", "chip", "fabrication", "wafer","TSMC","GlobalFoundries","Intel","Samsung"]
}

vc_signal = vc_funding_signal_by_tech(technology_groups, max_pages=50)

for year in sorted(vc_signal):
    print(year, dict(vc_signal[year]))