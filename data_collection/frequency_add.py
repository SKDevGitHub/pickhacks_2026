import json
import os

# Folder containing your technology JSON files
data_folder = "./data/emergent_tech"

# Example frequency outputs from the two scripts
# Replace these with the actual outputs from your previous functions
research_frequency = {
    2011: {'AI intersections': 4, 'Data_Centers': 1},
    2012: {'AI intersections': 8, 'Data_Centers': 1},
    2013: {'AI-Campus': 5, 'AI intersections': 12, 'Robotics': 2, 'Data_Centers': 1},
    2014: {'AI intersections': 20, 'AI-Campus': 3, 'Data_Centers': 1}, 
    2015: {'AI intersections': 25, 'AI-Campus': 9, 'Data_Centers': 3, 'Autonomous vehicles': 1},
    2016: {'AI-Campus': 13, 'AI intersections': 25, 'Autonomous vehicles': 2},
    2017: {'AI intersections': 48, 'AI-Campus': 16, 'Data_Centers': 3, 'Autonomous vehicles': 1},
    2018: {'AI intersections': 51, 'AI-Campus': 19, 'Robotics': 3, 'Data_Centers': 1, 'Autonomous vehicles': 1},
    2019: {'AI-Campus': 24, 'AI intersections': 34, 'Robotics': 3, 'Data_Centers': 1},
    2020: {'AI intersections': 42, 'Robotics': 2, 'AI-Campus': 22, 'Data_Centers': 1, 'Autonomous vehicles': 1},
    2021: {'AI-Campus': 23, 'AI intersections': 40, 'Data_Centers': 3},
    2022: {'AI intersections': 19, 'AI-Campus': 11, 'Data_Centers': 2},
    2023: {'AI-Campus': 13, 'AI intersections': 15},
    2024: {'AI intersections': 6, 'AI-Campus': 3}
}
vc_frequency = {
    2010: {'Semiconductor plants': 1},
    2011: {'Data_Centers': 1, 'Semiconductor plants': 1},
    2012: {'Data_Centers': 2, 'AI intersections': 1},
    2013: {'Semiconductor plants': 1, 'Data_Centers': 2, 'Robotics': 1},
    2015: {'Data_Centers': 2},
    2017 :{'Semiconductor plants': 1},
    2018: {'AI-Campus': 3},
    2019: {'AI-Campus': 5, 'AI intersections': 1},
    2020: {'AI-Campus': 3},
    2021: {'AI-Campus': 6, 'Data_Centers': 2},
    2022: {'AI-Campus': 11, 'AI intersections': 1},
    2023: {'AI-Campus': 5, 'Data_Centers': 2, 'Semiconductor plants': 1},
    2024: {'AI-Campus': 11, 'AI intersections': 1},
    2025: {'AI-Campus': 6}
}

# Map the JSON filenames to technology groups

technology_files = {
    "AI-Campus": "AI_Campus.json",
    "AI intersections": "AI_Intersections.json",
    "Autonomous vehicles": "Autonomous_Vehicles.json",
    "Data_Centers": "data_center.json",
    "Robotics": "robotics.json",
    "Semiconductor plants": "SemiConductor_Plants.json"
}

for tech, filename in technology_files.items():
    path = os.path.join(data_folder, filename)
    
    # Load existing JSON
    if os.path.exists(path):
        with open(path, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Add research and VC frequency for this technology
    data["research_frequency"] = {str(year): research_frequency.get(year, {}).get(tech, 0)
                                  for year in range(2010, 2026)}
    data["vc_frequency"] = {str(year): vc_frequency.get(year, {}).get(tech, 0)
                            for year in range(2010, 2026)}

    # Save JSON back
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

print("JSON files updated with research_frequency and vc_frequency!")