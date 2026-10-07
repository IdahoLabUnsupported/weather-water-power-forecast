"""Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED"""

from herbie import FastHerbie
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CITIES_FILE = REPO_ROOT / "source_code" / "weather" / "uscities_with_hydro_countyweighted_allnonconus_preprocessed.csv"
OUTPUT_ROOT = REPO_ROOT / "data" / "weather"

VARIABLES = {
    "temperature_2m": {
        "hrrr": "TMP:2 m above ground",
        "nbm": "TMP:2 m above ground",
        "convert": lambda x: x - 273.15
    },
    "dew_point_2m": {
        "hrrr": "DPT:2 m above ground",
        "nbm": "DPT:2 m above ground",
        "convert": lambda x: x - 273.15
    },
    "relative_humidity_2m": {
        "hrrr": "RH:2 m above ground",
        "nbm": "RH:2 m above ground",
        "convert": None
    },
    "wind_speed_10m": {
        "hrrr": "WIND:10 m above ground",
        "nbm": "WIND:10 m above ground",
        "convert": None
    },
    # "wind_gust_10m": {
    #     "hrrr": "GUST:surface",
    #     "nbm": "GUST:10 m above ground",
    #     "convert": None
    # },
    "precip_total_1h": {
        "hrrr": "APCP:surface",
        "nbm": "APCP:surface",
        "convert": None
    },
    # "snow_accum_1h": {
    #     "hrrr": "ASNOW:surface",
    #     "nbm": "ASNOW:surface",
    #     "convert": None
    # },
    "cloud_cover_total": {
        "hrrr": "TCDC:entire atmosphere",
        "nbm": "TCDC:surface",
        "convert": None
    },
    "surface_pressure": {
        "hrrr": "PRES:surface",
        "nbm": None,
        "convert": None
    },
    "shortwave_radiation": {
        "hrrr": "DSWRF:surface",
        "nbm": "DSWRF:surface",
        "convert": None
    },
    # "visibility": {
    #     "hrrr": "VIS:surface",
    #     "nbm": "VIS:surface",
    #     "convert": None
    # },
}

now = datetime.utcnow()
run_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
run_time = run_time - timedelta(days =1) #for testing: running this right after utc midnight gives errors :(

print(f"Forecast run: {run_time}")

# Download model data
print("Downloading HRRR")
FH_HRRR = FastHerbie(DATES=[run_time], model="hrrr", product="sfc", fxx=range(1, 49))
#FH_HRRR.download(overwrite=True) #overwrite cached files

print("Downloading NBM CONUS")
FH_NBM_CO = FastHerbie(DATES=[run_time], model="nbm", product="co", fxx=range(51, 169, 3))
#FH_NBM_CO.download(overwrite=True)

cities = pd.read_csv(CITIES_FILE)
states = ["AK", "HI", "PR"]
# Only get CONUS cities here; non-CONUS is handled by Open-Meteo
cities = cities.query("state_id not in @states")

def extract_from_dataset(ds, row, model_name):
    """Pull forecast values from the model grid using preprocessed indices"""
    prefix = model_name.replace("-", "_")
    
    lat_idx_col = f"{prefix}_lat_idx"
    lon_idx_col = f"{prefix}_lon_idx"
    
    #use indices if available, otherwise fall back to lat/lon lookup
    #HI, PR need this fallback because their grids are differently structured
    if not pd.isna(row[lat_idx_col]) and not pd.isna(row[lon_idx_col]):
        iy, ix = int(row[lat_idx_col]), int(row[lon_idx_col])
        vals = ds.isel(y=iy, x=ix).values
    else:
        grid_lat_col = f"{prefix}_grid_lat"
        grid_lon_col = f"{prefix}_grid_lon"
        vals = ds.sel(latitude=row[grid_lat_col], 
                     longitude=row[grid_lon_col], 
                     method="nearest").values
    return vals


def safe_xarray(FH, var, name):
    """Load xarray data - automatically downloads subset"""
    try:
        # This downloads the subset AND loads it
        ds = FH.xarray(var)
        ds = ds[0] if isinstance(ds, list) else ds
        if hasattr(ds, 'data_vars'):
            var_name = list(ds.data_vars.keys())[0]
            return ds[var_name]
        return ds
    except Exception as e:
        # Mercator projection error - try with backend_kwargs
        try:
            ds = FH.xarray(var, backend_kwargs={'errors': 'ignore'})
            ds = ds[0] if isinstance(ds, list) else ds
            if hasattr(ds, 'data_vars'):
                var_name = list(ds.data_vars.keys())[0]
                return ds[var_name]
            return ds
        except:
            print(f"  Warning: {name} couldn't load {var} - {e}")
            return None
    

# def safe_xarray(FH, var, name):
#     """Load xarray data with basic error handling"""
#     try:
#         ds = FH.xarray(var)
#         ds = ds[0] if isinstance(ds, list) else ds
#         if hasattr(ds, 'data_vars'):
#             var_name = list(ds.data_vars.keys())[0]
#             return ds[var_name]
#         return ds
#     except Exception as e:
#         print(f"  Warning: {name} couldn't load {var} - {e}")
#         return None
    

# print("\nChecking HRRR availability:")
# try:
#     test_ds = FH_HRRR.xarray("TMP:2 m above ground")
#     print(f"  HRRR loaded successfully: {type(test_ds)}")
# except Exception as e:
#     print(f"  HRRR error: {e}")

def main_processing(FH_HRRR, FH_NBM_CO, cities, output_root = OUTPUT_ROOT):
    """ Main processing loop: outputted file structure is state -> var csvs (each csv contains a row for each city)"""
    for var_name, var_config in VARIABLES.items():
        print(f"Processing {var_name}")

        hrrr_search = var_config["hrrr"]
        nbm_search = var_config["nbm"]
        convert_func = var_config.get("convert")

        # load datasets for this variable
        ds_hrrr = safe_xarray(FH_HRRR, hrrr_search, name = 'FH_HRRR') if hrrr_search else None
        ds_nbm_co = safe_xarray(FH_NBM_CO, nbm_search, name = 'FH_NBM_CO') if nbm_search else None

        # check if critical datasets loaded
        if ds_hrrr is None:
            print("ERROR: HRRR data failed to load")
        if ds_nbm_co is None:
            print("ERROR: NBM-CO data failed to load")

        for state_id, group in cities.groupby("state_id"):
            print(f"\n{state_id}: {len(group)} cities")
            state_folder = Path(output_root) / state_id
            state_folder.mkdir(parents=True, exist_ok=True)

            rows = []
            failed = []
            
            for _, row in group.iterrows():
                try:
                    model_domain = row["model_domain"]
                    vals, hours = [], []

                    # figure out which datasets to use
                    if model_domain == "hrrr":
                        ds_h = ds_hrrr
                        model_h = "hrrr"
                        ds_n1 = None
                        model_n1 = None
                        ds_n3 = ds_nbm_co
                        model_n3 = "nbm-co"
                        hours_n3 = range(51, 169, 3)
                    else:
                        failed.append((row['city'], f"unknown domain: {model_domain}"))
                        continue

                    # extract forecasts
                    if ds_h is not None:
                        v = extract_from_dataset(ds_h, row, model_h)
                        if len(v) == 0:
                            raise ValueError("HRRR extraction returned empty array")
                        vals += list(v)
                        hours += list(range(0, len(v)))

                    if ds_n3 is not None:
                        v = extract_from_dataset(ds_n3, row, model_n3)
                        if len(v) == 0:
                            raise ValueError("NBM 3-hourly extraction returned empty array")
                        vals += list(v)
                        hours += list(hours_n3)

                    # fill in missing hours (forward fill from 3-hourly data)
                    lookup = dict(zip(hours, vals))
                    full_hours = list(range(1, 169))
                    full_vals = []
                    
                    for h in full_hours:
                        if h in lookup:
                            val = lookup[h]
                        else:
                            # copy from most recent available hour
                            prev = max([hh for hh in lookup.keys() if hh < h], default=None)
                            val = lookup.get(prev, np.nan)
                        
                        # apply unit conversions if needed
                        if convert_func and not np.isnan(val):
                            val = convert_func(val)
                        
                        full_vals.append(val)

                    row_data = [row["city"].strip(), run_time.strftime("%Y-%m-%d %H:%M:%S+00:00")] + full_vals
                    rows.append(row_data)

                except Exception as e:
                    failed.append((row['city'], str(e)))


            # save results
            header = ["city", "forecast_day"] + [f"{h}h" for h in range(1, 169)]
            df = pd.DataFrame(rows, columns=header)
            csv_file = state_folder / f"{state_id}_{var_name}_{run_time.strftime('%Y')}.csv.gz"

            if csv_file.exists():
                df.to_csv(csv_file, mode="a", header=False, index=False, compression="gzip")
            else:
                df.to_csv(csv_file, index=False, compression="gzip")
            #10x compression! holy moly
            print(f"  Saved {len(rows)} cities")
    print("Done!")

def main_processing_by_city(FH_HRRR, FH_NBM_CO, cities, output_root = OUTPUT_ROOT):
    """ Same as above, but file structure is state -> city -> var csvs."""
    for var_name, var_config in VARIABLES.items():
        print(f"Processing {var_name}")

        hrrr_search = var_config["hrrr"]
        nbm_search = var_config["nbm"]
        convert_func = var_config.get("convert")

        # load datasets for this variable
        ds_hrrr = safe_xarray(FH_HRRR, hrrr_search, name='FH_HRRR') if hrrr_search else None
        ds_nbm_co = safe_xarray(FH_NBM_CO, nbm_search, name='FH_NBM_CO') if nbm_search else None

        # check if critical datasets loaded
        if ds_hrrr is None:
            print("ERROR: HRRR data failed to load")
            continue
        if ds_nbm_co is None:
            print("ERROR: NBM-CO data failed to load")
            continue

        failed = []
        processed = 0
        
        for _, row in cities.iterrows():
            try:
                model_domain = row["model_domain"]
                vals, hours = [], []

                # figure out which datasets to use
                if model_domain == "hrrr":
                    ds_h = ds_hrrr
                    model_h = "hrrr"
                    ds_n3 = ds_nbm_co
                    model_n3 = "nbm-co"
                    hours_n3 = range(51, 169, 3)
                else:
                    failed.append((row['city'], f"unknown domain: {model_domain}"))
                    continue

                # extract forecasts
                if ds_h is not None:
                    v = extract_from_dataset(ds_h, row, model_h)
                    if len(v) == 0:
                        raise ValueError("HRRR extraction returned empty array")
                    vals += list(v)
                    hours += list(range(0, len(v)))

                if ds_n3 is not None:
                    v = extract_from_dataset(ds_n3, row, model_n3)
                    if len(v) == 0:
                        raise ValueError("NBM 3-hourly extraction returned empty array")
                    vals += list(v)
                    hours += list(hours_n3)

                # for now, just put in nothing for missing hours
                lookup = dict(zip(hours, vals))
                full_hours = list(range(1, 169))
                full_vals = []
                
                for h in full_hours:
                    if h in lookup:
                        val = lookup[h]
                    else:
                        # prev = max([hh for hh in lookup.keys() if hh < h], default=None)
                        # val = lookup.get(prev, np.nan)
                        val = np.nan
                    
                    if convert_func and not np.isnan(val):
                        val = convert_func(val)
                    
                    full_vals.append(val)

                # # Create city folder: output_root/STATE/COUNTY/CITY/
                # city_name = row["city"].strip().replace("/", "-")  # sanitize filename
                # city_folder = Path(output_root) / row["state_id"] / row["county_name"] / city_name
                # city_folder.mkdir(parents=True, exist_ok=True)

                # Create city folder: output_root/STATE/CITY/
                city_name = row["city"].strip().replace("/", "-")  # sanitize filename
                # city_folder = Path(output_root) / row["state_id"] / city_name / run_time.strftime('%Y')
                outdir = "{}/{}/{}_{}N_{}W/{}".format(output_root, row["state_id"], city_name, row["lat"], row["lng"], run_time.strftime('%Y'))
                city_folder = Path(outdir)
                city_folder.mkdir(parents=True, exist_ok=True)
                
            

                # Save to: output_root/GA/Atlanta/temperature_2m_2025.csv.gz
                csv_file = city_folder / f"{city_name}_{row['state_id']}_{var_name}_{run_time.strftime('%Y')}.csv" #.csv.gz for compressed
                
                # Create dataframe for this one city
                row_data = [row["city"].strip(), run_time.strftime("%Y-%m-%d %H:%M:%S+00:00")] + full_vals
                header = ["city", "forecast_day"] + [f"{h}h" for h in range(1, 169)]
                df = pd.DataFrame([row_data], columns=header)
                
                # Append or create file
                if csv_file.exists():
                    df.to_csv(csv_file, mode="a", header=False, index=False) #compression="gzip"
                else:
                    df.to_csv(csv_file, index=False) #compression="gzip"
                
                processed += 1
                if processed % 100 == 0:
                    print(f"  {processed}/{len(cities)} cities processed...")

            except Exception as e:
                failed.append((row['city'], str(e)))

        print(f"  Completed: {processed} cities, {len(failed)} failures")


main_processing_by_city(FH_HRRR, FH_NBM_CO, cities, OUTPUT_ROOT)
