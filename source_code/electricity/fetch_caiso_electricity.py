"""Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED"""

from datetime import date, timedelta
import os
import pandas as pd
import zipfile
import io
import xml.etree.ElementTree as ET
import requests
from pathlib import Path


QUERY_LIMIT = 10_000  # kept for parity with original script, not used directly


def normalize_to_168(values):
    """Ensure the time series has exactly 168 hourly values."""
    values = list(values)

    if len(values) > 168:
        return values[:168]

    if len(values) < 168:
        values += ["NaN"] * (168 - len(values))

    return values


def fetch_caiso_7day():
    """Fetch CAISO 7-day load forecast and write per-zone CSVs.

    This is the CAISO-specific branch from the original electricity script,
    refactored to avoid any dependency on gridstatus.
    """

    today = date.today()
    year = today.strftime("%Y")

    today_date_caiso = today.strftime("%Y%m%d")
    seven_days_date_caiso = (today + timedelta(days=7)).strftime("%Y%m%d")

    repo_root = Path(__file__).resolve().parents[2]
    base_dir = repo_root / "data" / "electricity"
    iso_name = "CAISO"

    base_dir.mkdir(parents=True, exist_ok=True)

    url = (
        "http://oasis.caiso.com/oasisapi/SingleZip?"
        f"queryname=SLD_FCST&market_run_id=7DA&startdatetime={today_date_caiso}T00:00-0000"
        f"&enddatetime={seven_days_date_caiso}T00:00-0000&version=1"
    )

    resp = requests.get(url)
    resp.raise_for_status()

    # Read the zip file from the response content
    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
        # Assuming there's only one file in the zip and it's an XML file
        xml_file_name = z.namelist()[0]
        with z.open(xml_file_name) as f:
            xml_data = f.read()

    # Parse the XML data
    root = ET.fromstring(xml_data)

    # Define the namespace
    namespace = {"o": "http://www.caiso.com/soa/OASISReport_v1.xsd"}

    # Extract data
    records = []
    for rpt in root.findall(".//o:REPORT_DATA", namespace):
        row = {}
        for item in rpt.findall(".//o:DATA_ITEM", namespace):
            row[item.get("name")] = item.get("value")
        # Include other relevant keys
        for child in rpt:
            tag = child.tag.replace(f'{{{namespace["o"]}}}', "")
            if tag in ["INTERVAL_START_GMT", "RESOURCE_NAME", "VALUE"]:
                row[tag] = child.text
        records.append(row)

    df = pd.DataFrame(records)

    # Convert 'INTERVAL_START_GMT' to datetime objects
    df["INTERVAL_START_GMT"] = pd.to_datetime(
        df["INTERVAL_START_GMT"], utc=True, errors="coerce"
    )

    # Split the DataFrame by 'RESOURCE_NAME' and save to separate CSVs
    if "RESOURCE_NAME" not in df.columns:
        print("No RESOURCE_NAME column found in CAISO response; nothing to write.")
        return

    for resource_name, resource_df in df.groupby("RESOURCE_NAME"):
        # Clean up resource_name for filename
        safe_resource_name = resource_name.replace("/", "_").replace("\\", "_")

        folder_path = base_dir / iso_name / safe_resource_name
        folder_path.mkdir(parents=True, exist_ok=True)

        file_path = folder_path / f"{safe_resource_name}_{year}.csv"

        values = normalize_to_168(resource_df["VALUE"])

        row = [
            today.strftime("%Y-%m-%d"),
            resource_df["INTERVAL_START_GMT"].iloc[0].strftime("%Y-%m-%d %H:%M:%S%z"),
        ] + values

        header = ["forecast_day", "time_of_1h"] + [f"{h}h" for h in range(1, 169)]

        if file_path.exists():
            # Append without writing header
            pd.DataFrame([row]).to_csv(file_path, mode="a", header=False, index=False)
        else:
            # Create new file with header row
            pd.DataFrame([row], columns=header).to_csv(file_path, index=False)

        print(f"Saved CAISO data for resource '{resource_name}' to: {file_path}")


if __name__ == "__main__":
    fetch_caiso_7day()
