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
    "AI-Campus": [
        "ai", "artificial intelligence", "machine learning", "deep learning", "neural network",
        "campus digital twin", "smart campus", "intelligent campus", "campus automation",
        "ai-enabled classrooms", "adaptive learning systems", "learning analytics",
        "student success analytics", "predictive enrollment modeling",
        "campus surveillance ai", "facial recognition campus", "computer vision campus",
        "ai security monitoring", "smart building ai", "building energy optimization ai",
        "campus iot platform", "edge ai campus", "campus data lake",
        "ai research lab", "university ai center", "campus hpc cluster",
        "ai-powered scheduling", "ai facilities management",
        "smart lecture hall", "ai-driven timetabling",
        "digital campus infrastructure", "campus network ai",
        "ai-powered tutoring", "intelligent tutoring system",
        "campus robotics integration", "ai-powered campus safety",
        "campus analytics platform", "ai-enabled campus planning",
        "smart dormitory systems", "campus smart grid",
        "ai-powered student services", "campus automation software",
        "ai-powered asset tracking", "campus ai governance"
    ],

    "AI intersections": [
        "smart intersection", "ai traffic signal control", "adaptive traffic signal",
        "intelligent traffic management", "traffic light optimization ai",
        "computer vision traffic monitoring", "intersection camera ai",
        "vehicle detection ai", "pedestrian detection ai",
        "real-time traffic analytics", "traffic flow prediction",
        "ai-powered signal timing", "reinforcement learning traffic control",
        "urban traffic ai", "smart city traffic ai",
        "connected intersection", "v2i intersection",
        "vehicle-to-infrastructure ai", "edge ai traffic control",
        "ai congestion management", "traffic incident detection ai",
        "ai-enabled traffic cameras", "intersection safety analytics",
        "crash prediction ai", "near-miss detection ai",
        "smart crosswalk ai", "pedestrian safety ai",
        "bicycle detection ai", "multimodal traffic ai",
        "intersection digital twin", "urban mobility ai",
        "ai-powered traffic modeling", "signal coordination ai",
        "traffic demand forecasting", "urban intersection optimization",
        "ai-powered traffic simulation", "city traffic ai platform",
        "autonomous signal control", "ai-powered traffic enforcement",
        "urban sensing ai", "smart corridor ai",
        "intersection edge computing", "traffic analytics dashboard",
        "ai-powered road safety", "urban ai infrastructure",
        "connected traffic systems", "smart mobility ai"
    ],

    "Autonomous vehicles": [
        "autonomous vehicle", "self-driving car", "driverless vehicle",
        "robotaxi", "autonomous shuttle", "autonomous bus",
        "level 4 autonomy", "level 5 autonomy",
        "lidar perception", "radar perception", "sensor fusion",
        "computer vision driving", "autonomous navigation system",
        "self-driving software stack", "av perception system",
        "av planning module", "av control system",
        "hd mapping for av", "simultaneous localization and mapping",
        "slam for autonomous vehicles", "av safety validation",
        "av simulation platform", "virtual driving simulation",
        "autonomous fleet management", "robotaxi fleet operations",
        "av test track", "autonomous vehicle testing",
        "on-road av deployment", "urban autonomous vehicles",
        "av edge computing", "av onboard compute",
        "ai driving model", "end-to-end driving neural network",
        "av fail-safe system", "av redundancy system",
        "vehicle autonomy stack", "autonomous trucking",
        "self-driving delivery vehicle", "autonomous last-mile delivery",
        "connected autonomous vehicle",
        "v2v communication for av",
        "av cybersecurity", "av safety assurance",
        "av regulatory framework", "av pilot program"
    ],

    "Data_Centers": [
        "data center", "hyperscale data center", "colocation data center",
        "edge data center", "cloud data center",
        "high performance computing center", "hpc cluster",
        "ai data center", "gpu data center",
        "liquid cooling data center", "direct-to-chip liquid cooling",
        "immersion cooling", "data center cooling infrastructure",
        "data center power substation", "redundant power supply",
        "data center backup generators", "ups systems data center",
        "data center energy efficiency", "pue optimization",
        "carbon neutral data center", "green data center",
        "renewable-powered data center", "data center water usage",
        "data center water cooling", "data center thermal management",
        "modular data center", "prefabricated data center",
        "containerized data center", "edge compute facility",
        "cloud computing facility", "server farm",
        "ai training cluster", "gpu compute cluster",
        "inference data center", "high density server racks",
        "rack-scale computing", "data center network fabric",
        "software defined networking data center",
        "data center interconnect", "fiber backhaul to data center",
        "data center expansion project", "hyperscale campus",
        "ai workload hosting", "cloud infrastructure facility",
        "colocation campus", "data center zoning approval"
    ],

    "Robotics": [
        "robotics", "industrial robotics", "collaborative robot",
        "cobot", "robotic arm", "articulated robot",
        "humanoid robot", "bipedal robot",
        "warehouse automation robot", "autonomous mobile robot",
        "amr robot", "agv robot",
        "service robot", "delivery robot",
        "surgical robot", "medical robotics",
        "robotic surgery system", "surgical assistance robot",
        "inspection robot", "infrastructure inspection robot",
        "drone robotics", "uav robotics",
        "swarm robotics", "multi-robot coordination",
        "robot fleet management", "robot operating system",
        "ros2 robotics platform", "robot perception system",
        "robotic manipulation system", "grasping robot ai",
        "vision-guided robotics", "computer vision robotics",
        "robot path planning", "motion planning robotics",
        "robot safety system", "human-robot interaction",
        "hri robotics research", "robot learning from demonstration",
        "reinforcement learning robotics",
        "warehouse picking robot", "automated fulfillment robot",
        "logistics robotics system", "factory automation robot",
        "robotic welding system", "robotic assembly line",
        "smart factory robotics", "autonomous inspection robot"
    ],

    "Semiconductor plants": [
        "semiconductor fab", "chip fabrication plant",
        "wafer fabrication facility", "semiconductor manufacturing",
        "logic chip fab", "memory chip fab",
        "advanced node fabrication", "3nm fab", "5nm fab", "7nm fab",
        "semiconductor foundry", "contract chip manufacturing",
        "tsmc fab", "samsung foundry", "intel foundry services",
        "globalfoundries fab", "chip manufacturing plant",
        "photolithography facility", "euv lithography",
        "cleanroom manufacturing", "semiconductor cleanroom",
        "wafer processing line", "etching facility semiconductor",
        "ion implantation facility", "chip packaging plant",
        "advanced packaging facility", "chip assembly and test",
        "backend semiconductor plant", "frontend semiconductor fab",
        "fab construction project", "semiconductor plant expansion",
        "onshore semiconductor fab", "domestic chip manufacturing",
        "semiconductor supply chain facility",
        "chip fabrication campus", "fab utility infrastructure",
        "ultra pure water semiconductor plant",
        "semiconductor wastewater treatment",
        "fab power substation", "fab gas supply system",
        "fab chemical supply", "fab safety systems",
        "chip yield optimization facility",
        "process control fab", "metrology semiconductor plant",
        "semiconductor equipment installation",
        "fab commissioning project", "semiconductor industrial park"
    ]
}

vc_signal = vc_funding_signal_by_tech(technology_groups, max_pages=50)

for year in sorted(vc_signal):
    print(year, dict(vc_signal[year]))