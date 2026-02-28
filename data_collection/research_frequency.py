from collections import defaultdict
import re
import requests
import time

BASE_URL = "https://api.openalex.org/works"

def contains_kw(title, kw):
    return re.search(rf"\b{re.escape(kw.lower())}\b", title) is not None

def keyword_frequency_by_tech(query, keywords, tech_groups, pages=20, per_page=200):
    checked = 0
    freq_by_tech = defaultdict(lambda: defaultdict(int))
    cursor = "*"

    # Flatten all keywords for quick checking
    all_keywords = [kw for kws in tech_groups.values() for kw in kws]

    for _ in range(pages):
        resp = requests.get(
            BASE_URL,
            params={
                "search": query,
                "per-page": per_page,
                "cursor": cursor,
                "filter": "publication_year:2010-2025"
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
            # Check which keywords appear in this title
            matched_keywords = [kw for kw in all_keywords if contains_kw(title, kw)]
            # Increment frequency for each tech group that contains the keyword
            for tech, kws in tech_groups.items():
                if any(kw in kws for kw in matched_keywords):
                    freq_by_tech[year][tech] += 1
            checked += 1

        cursor = data["meta"].get("next_cursor")
        if not cursor:
            break
        time.sleep(0.3)

    return freq_by_tech, checked

technology_groups = {
    "AI-Campus": ["ai", "big data", "smart campus", "machine learning", "deep learning"],
    "AI intersections": ["intersection", "smart city", "urban iot", "traffic ai"],
    "Autonomous vehicles": ["autonomous vehicle", "self-driving", "robotic car", "driverless"],
    "Data_Centers": ["data center", "cloud", "high performance computing"],
    "Robotics": ["robotics", "robotic", "automation", "drone","humanoid","robotic arm"],
    "Semiconductor plants": ["semiconductor", "chip", "fabrication", "wafer","TSMC","GlobalFoundries","Intel","Samsung"]
}

freq, checked = keyword_frequency_by_tech("city OR urban", keywords=None, tech_groups=technology_groups, pages=50)

for year in sorted(freq):
    print(year, dict(freq[year]))
print(f"Checked {checked} papers")