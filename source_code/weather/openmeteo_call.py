"""Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED"""

import openmeteo_requests  # type: ignore
# install this library first
import numpy as np
import pandas as pd  # type: ignore
import requests_cache  # type: ignore
from retry_requests import retry  # type: ignore
from datetime import datetime, timezone
from pathlib import Path
import os
import time

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)
url = "https://api.open-meteo.com/v1/forecast"



def openmeteo_7_day_call(url, lat, lon, cityname="", statename="", block_csv=True, top_folder="locations"):
    """
    requests 7DA weather data from OpenMeteo and writes to csv.
    url: located below, meant to be OpenMeteo forecast api url
    lat: latitude of desired point
    lon: longitude of desired point
    path: full path of saved block csv file - if block_csv = False, path is not used
    block_csv: if True, the program outputs one csv, containing all weather variables for the 7DA forecast for the specific lat/lon point.
    if False, the program outputs one csv for each variable. Each csv contains the 7DA forecast for one variable for specific lat/lon point.
    top_folder: specifies the created folder into which the created csv(s) go. By default, creates a folder named locations.
    """
    url = url
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")
    today = today[:-2] + ":" + today[-2:]
    #getting the date of request in the same format as times returned by OpenMeteo

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m",
            "wind_speed_10m",
            "relative_humidity_2m",
            "dew_point_2m",
            "precipitation",
            "surface_pressure",
            "cloud_cover",
            "shortwave_radiation",
        ],
        "models": "ecmwf_ifs",  # gfs_global
        "wind_speed_unit": "ms"
    }
    responses = openmeteo.weather_api(url, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_wind_speed_10m = hourly.Variables(1).ValuesAsNumpy()
    hourly_relative_humidity_2m = hourly.Variables(2).ValuesAsNumpy()
    hourly_dew_point_2m = hourly.Variables(3).ValuesAsNumpy()
    # hourly_precipitation_probability = hourly.Variables(4).ValuesAsNumpy()
    hourly_precipitation = hourly.Variables(4).ValuesAsNumpy()
    hourly_surface_pressure = hourly.Variables(5).ValuesAsNumpy()
    hourly_cloud_cover = hourly.Variables(6).ValuesAsNumpy()
    # hourly_wind_direction_10m = hourly.Variables(8).ValuesAsNumpy()
    hourly_shortwave_radiation = hourly.Variables(7).ValuesAsNumpy()

    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        )
    }

    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_data["wind_speed_10m"] = hourly_wind_speed_10m
    hourly_data["relative_humidity_2m"] = hourly_relative_humidity_2m
    hourly_data["dew_point_2m"] = hourly_dew_point_2m
    # hourly_data["precipitation_probability"] = hourly_precipitation_probability
    hourly_data["precipitation"] = hourly_precipitation
    hourly_data["surface_pressure"] = hourly_surface_pressure
    hourly_data["cloud_cover"] = hourly_cloud_cover
    hourly_data["shortwave_radiation"] = hourly_shortwave_radiation
    # hourly_data["wind_direction_10m"] = hourly_wind_direction_10m

    hourly_dataframe = pd.DataFrame(data = hourly_data)
    #print("\nHourly data\n", hourly_dataframe)

    if cityname == '':
        # Directory to save files
        outdir = "{}/{}N_{}W/{}".format(top_folder, lat, lon, datetime.now().year)
        os.makedirs(outdir, exist_ok=True)
    else:
        outdir = "{}/{}/{}_{}N_{}W/{}".format(top_folder, statename, cityname, lat, lon, datetime.now().year)
        #outdir = "{}/{}/{}/{}".format(top_folder, statename, cityname, datetime.now().year) # no need for lat/long
        os.makedirs(outdir, exist_ok=True)


    if block_csv:
        csv_file = os.path.join(outdir, "{}_7DA_{}N_{}W.csv".format(today, lat, lon))
        hourly_dataframe.to_csv(csv_file, index=False)

    else:
    # Dictionary mapping variable names -> their hourly arrays
        variables = {
            "temperature_2m": hourly_temperature_2m,
            "wind_speed_10m": hourly_wind_speed_10m,
            "relative_humidity_2m": hourly_relative_humidity_2m,
            "dew_point_2m": hourly_dew_point_2m,
            # "precipitation_probability": hourly_precipitation_probability,
            "precipitation": hourly_precipitation,
            "surface_pressure": hourly_surface_pressure,
            "cloud_cover": hourly_cloud_cover,
            "shortwave_radiation": hourly_shortwave_radiation,
            # "wind_direction_10m": hourly_wind_direction_10m,
        }

        # Loop over variables, one CSV per variable
        for var, values in variables.items():
            # Build a row: [today, val1, val2, ..., val168]
            row = [today, hourly_data["date"][0]] + list(values)

            if cityname == '':
                # Path for this variable's CSV
                csv_file = os.path.join(outdir, "{}N_{}W_{}_{}.csv".format(lat, lon, var, datetime.now().year))
            else:
                csv_file = os.path.join(outdir, "{}_{}_{}.csv".format(cityname, var, datetime.now().year))

            if os.path.exists(csv_file):
                # Append without writing header
                pd.DataFrame([row]).to_csv(csv_file, mode="a", header=False, index=False)
            else:
                # Create new file with header row
                header = ["forecast_day", "time_of_1h"] + [f"{h}h" for h in range(1, len(values) + 1)]
                pd.DataFrame([row], columns=header).to_csv(csv_file, index=False)

    #print("Daily forecasts appended to per-variable CSVs")


def full_grid_call(url, n, block_csv=True, top_folder="locations"):
    """
    loops the 7DA OpenMeteo request calls over an nxn lat/lon grid of the contiguous US.
    n: the size of the grid. A total of n^2 points will be requested.
    block_csv: input to the 7DA call method. Determines whether output will be one csv per location or one csv per variable.
    top_folder: input to the 7DA call method. Specifies the created folder into which the created csv(s) go.
    """
    lats = np.linspace(25, 49, n)
    lons = np.linspace(67, 125, n)
    lat_lon_pairs = [(round(float(x), 2), round(float(y), 2)) for x in lats for y in lons]
    #making array for nxn grid of lat/lon points across contiguous US

    index = 0
    for i in range(0, n):
        for j in range(0, n):
            active_lat = lat_lon_pairs[index][0]
            active_lon = lat_lon_pairs[index][1]

            if block_csv:
                openmeteo_7_day_call(url, active_lat, active_lon, top_folder=top_folder)
            else:
                openmeteo_7_day_call(url, active_lat, active_lon, False, top_folder=top_folder)
            index += 1

#full_grid_call(url, 5, False) #testing with a 5x5 grid!

# def city_call(url, city_df, top_folder = 'locations'):

#     for i in range(0, len(city_df)):
#         active_lat = city_df['lat'][i]
#         active_lon = city_df['lng'][i]
#         cityname = city_df['city'][i]
#         statename = city_df['state_id'][i]
#         if i%599 == 0 and i != 0:
#             time.sleep(60)  #abide by 600 per minute openmeteo limit
#         if i%4999 == 0 and i != 0:
#             time.sleep(3600) #abide by 5000 per hour openmeteo limit
#         openmeteo_7_day_call(url, active_lat, active_lon, block_csv = False, cityname = cityname, statename = statename, top_folder = top_folder)
#     print("Daily forecast data retrieved")

def city_call(url, city_df, top_folder="locations"):

    for i in range(0, len(city_df)):
        active_lat = city_df.iloc[i]["lat"]
        active_lon = city_df.iloc[i]["lng"]
        cityname = city_df.iloc[i]["city"]
        statename = city_df.iloc[i]["state_id"]
        if i % 10 == 0 and i != 0:
            print(f"{i}/{len(city_df)} forecasts saved")
        if i % 599 == 0 and i != 0:
            time.sleep(60)  # abide by 600 per minute openmeteo limit
        if i % 4999 == 0 and i != 0:
            time.sleep(3600)  # abide by 5000 per hour openmeteo limit
        openmeteo_7_day_call(
            url,
            active_lat,
            active_lon,
            block_csv=False,
            cityname=cityname,
            statename=statename,
            top_folder=top_folder,
        )
    print("Daily forecast data retrieved")


if __name__ == "__main__":
    # Run only for non-CONUS for now, matching prior behavior
    repo_root = Path(__file__).resolve().parents[2]
    cities_csv = repo_root / "source_code" / "weather" / "uscities_with_hydro_countyweighted_allnonconus_preprocessed.csv"

    # df_cities = pd.read_csv("uscities_with_hydro.csv")
    df_cities = pd.read_csv(cities_csv)
    states = ["AK", "HI", "PR"]
    df_cities_nonconus = df_cities.query("state_id in @states")

    # Write into repo-root/data/weather
    weather_top_folder = repo_root / "data" / "weather"
    city_call(url, df_cities_nonconus, top_folder=str(weather_top_folder))


