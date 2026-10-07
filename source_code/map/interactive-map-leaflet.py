"""Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED"""

import os
from pathlib import Path
import pandas as pd
import json
import gzip
import base64
from datetime import datetime

year = datetime.now().year

repo_root = Path(__file__).resolve().parents[2]
weather_csv = repo_root / "source_code" / "weather" / "uscities_with_hydro_countyweighted_allnonconus_preprocessed.csv"
gauges_csv = repo_root / "source_code" / "water" / "continuous_forecast_gauges.csv"
koppen_json_path = repo_root / "source_code" / "map" / "koppen_grid.json"
template_path = repo_root / "source_code" / "map" / "map-template-leaflet.html"

repo = os.environ.get("GITHUB_REPOSITORY")
if repo:
    base_tree_url = f"https://github.com/{repo}/tree/main/"
else:
    base_tree_url = ""

# Load cities
cities_df = pd.read_csv(weather_csv, encoding="utf-8")
cities = []
for idx, row in cities_df.iterrows():
    rel_weather_path = f"data/weather/{row['state_id']}/{row['city']}_{row['lat']}N_{row['lng']}W/"
    url1 = base_tree_url + rel_weather_path if base_tree_url else rel_weather_path
    cities.append({
        "name": f"{row['city']}, {row['state_id']}",
        "lat": row['lat'],
        "lon": row['lng'],
        "koppen": row['Koppen'],
        "url": rel_weather_path,
        "url1": url1,
    })

cities_json = json.dumps(cities)

# Load gauges
gauges_df = pd.read_csv(gauges_csv, encoding="utf-8")
gauges = []
for idx, row in gauges_df.iterrows():
    rel_water_path = f"data/water/{row['state_id']}/{row['lid']}/{row['lid']}_{year}.csv"
    data_url = base_tree_url + rel_water_path if base_tree_url else rel_water_path
    gauges.append({
        "name": f"{row['lid']}, {row['state_id']}",
        "lat": row['lat'],
        "lon": row['lng'],
        "url": f"https://water.noaa.gov/gauges/{row['lid']}",
        "data_url": data_url,
    })
gauges_json = json.dumps(gauges)

# Load and compress koppen
with open(koppen_json_path, "r", encoding="utf-8") as f:
    koppen_str = f.read()

compressed = gzip.compress(koppen_str.encode("utf-8"))
koppen_encoded = base64.b64encode(compressed).decode("ascii")

# Read template
with open(template_path, "r", encoding="utf-8") as f:
    template = f.read()

# Substitute data
html = template.replace('CITIES_DATA_PLACEHOLDER', cities_json)
html = html.replace('GAUGES_DATA_PLACEHOLDER', gauges_json)
html = html.replace('KOPPEN_COMPRESSED_PLACEHOLDER', koppen_encoded)

# Save final HTML
output_html = repo_root / "data_locations.html"
with open(output_html, "w", encoding="utf-8") as f:
    f.write(html)
