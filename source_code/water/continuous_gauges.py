"""Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED"""

import requests
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

GAUGES_URL = "https://api.water.noaa.gov/nwps/v1/gauges"
METADATA_URL_TEMPLATE = "https://api.water.noaa.gov/nwps/v1/gauges/{}"
MAX_WORKERS = 8

# Store the gauge metadata CSV under source_code/water so it lives
# alongside the scripts that use it.
BASE_DIR = "source_code/water"
os.makedirs(BASE_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(BASE_DIR, "continuous_forecast_gauges.csv")

# fetch all gauges
def fetch_with_retry(url, attempts=5, delay=5):
    for i in range(attempts):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            print(f"Attempt {i+1} failed: {e}")
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch after {attempts} attempts: {url}")

try:
    response = fetch_with_retry(GAUGES_URL)
except RuntimeError as e:
    # If we can't reach the NWPS API after several attempts, don't
    # cause the entire workflow to fail if an existing gauge list
    # is already present. This allows the water pipeline to keep
    # using the last known set of gauges during temporary outages.
    print(str(e))
    if os.path.exists(OUTPUT_CSV):
        print(f"Warning: using existing gauge list at {OUTPUT_CSV} because NWPS API is unreachable.")
        sys.exit(0)
    else:
        print("Error: no existing gauge list is available; exiting with failure.")
        sys.exit(1)

all_gauges_list = response.json().get("gauges", [])
print(f"Total gauges returned: {len(all_gauges_list)}")

# fetch metadata
def fetch_metadata(gauge):
    lid = gauge.get("lid")
    if not lid:
        return None
    try:
        metadata_resp = requests.get(METADATA_URL_TEMPLATE.format(lid), timeout=10)
        metadata_resp.raise_for_status()
        metadata = metadata_resp.json()
        if "issued routinely" in metadata.get("forecastReliability", "").lower():
            state_info = metadata.get("state", {})
            lat = metadata.get("latitude")
            lng = metadata.get("longitude")
            
            # skip if coordinates are invalid (1,1 or None)
            if not lat or not lng or (abs(lat - 1.0) < 1e-6 and abs(lng - 1.0) < 1e-6):
                return None
                
            return {
                "lid": metadata.get("lid"),
                "state_id": state_info.get("abbreviation"),
                "lat": lat,
                "lng": lng,
            }

    except requests.exceptions.RequestException:
        return None

continuous_forecast_gauges = []
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(fetch_metadata, g) for g in all_gauges_list]
    for future in as_completed(futures):
        result = future.result()
        if result:
            continuous_forecast_gauges.append(result)

print(f"\nTotal gauges with continuous forecasts: {len(continuous_forecast_gauges)}")

# write results to csv
with open(OUTPUT_CSV, mode="w", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=["lid", "state_id", "lat", "lng"])
    writer.writeheader()
    writer.writerows(continuous_forecast_gauges)

print(f"CSV written to: {OUTPUT_CSV}")
