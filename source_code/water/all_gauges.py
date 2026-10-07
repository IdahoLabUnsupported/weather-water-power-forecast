"""Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED"""

import requests
import csv
from pathlib import Path
from datetime import datetime, timezone
import math

# --- Path setup (script in source_code/water, data in data/water/) ---
REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = REPO_ROOT / "source_code" / "water"
DATA_DIR = REPO_ROOT / "data" / "water"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GAUGE_LIST_FILE = BASE_DIR / "continuous_forecast_gauges.csv"
MAX_HOURS = 168  # 7 days

def parse_utc(ts_str):
    if ts_str is None:
        return None
    try:
        if ts_str.endswith("Z"):
            return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(ts_str).astimezone(timezone.utc)
    except Exception:
        return None

def to_float_or_nan(x):
    try:
        v = float(x)
        if math.isfinite(v):
            return v
        return float("nan")
    except Exception:
        return float("nan")

# load gauges and their states
gauges = []
with open(GAUGE_LIST_FILE, newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        lid = row.get("lid")
        state = row.get("state_id") or "Unknown"
        if lid:
            gauges.append({"lid": lid.strip(), "state": state.strip()})

for gauge in gauges:
    GAUGE_ID = gauge["lid"]
    STATE = gauge["state"]

    # create state-specific directory
    state_dir = DATA_DIR / STATE / GAUGE_ID
    state_dir.mkdir(parents=True, exist_ok=True)

    url = f"https://api.water.noaa.gov/nwps/v1/gauges/{GAUGE_ID}/stageflow/forecast"

    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        forecast_data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch {GAUGE_ID}: {e}")
        continue

    data_points = forecast_data.get("data", [])
    if not data_points:
        print(f"No forecast data for {GAUGE_ID}")
        continue

    # Parse all validTimes and build list of (valid_dt, secondary)
    parsed = []
    for p in data_points:
        vt = parse_utc(p.get("validTime"))
        val = to_float_or_nan(p.get("secondary"))
        if vt is None:
            continue
        parsed.append((vt, val))

    if not parsed:
        continue

    parsed.sort(key=lambda x: x[0])
    time_of_1h_dt = parsed[0][0]
    time_of_1h = time_of_1h_dt.isoformat().replace("+00:00", "Z")

    slots = [float("nan")] * MAX_HOURS
    for vt, val in parsed:
        delta_hours = int((vt - time_of_1h_dt).total_seconds() / 3600)
        if 0 <= delta_hours < MAX_HOURS:
            slots[delta_hours] = val

    non_nan_vals = [v for v in slots if not math.isnan(v)]
    if non_nan_vals and all(v == 0.0 or v == -999.0 for v in non_nan_vals):
        slots = [float("nan")] * MAX_HOURS

    # Convert NaNs to the string "NaN" for CSV readability
    csv_values = [("NaN" if math.isnan(v) else v) for v in slots]

    issued = forecast_data.get("issuedTime") or forecast_data.get("generatedTime")
    if not issued:
        issued = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Determine year
    year = issued[:4]  # e.g., "2025"

    header = ["forecast_day", "time_of_1h"] + [f"{i+1}h" for i in range(MAX_HOURS)]
    row = [issued, time_of_1h] + csv_values

    csv_file = state_dir / f"{GAUGE_ID}_{year}.csv"

    # append row
    write_header = not csv_file.exists()
    with open(csv_file, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow(row)
