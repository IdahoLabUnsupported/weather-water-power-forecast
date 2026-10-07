# Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED

# weather-water-power-forecast
The software maintains a continuously updated U.S. archive of weather, water flow, and electricity demand forecasts. Daily snapshots preserve forecasts up to seven days ahead, enabling backtesting, forecast evaluation, trend analysis, and energy-water system research.

## Repository structure

- `source_code/weather/` – Weather retrieval for CONUS (Herbie) and non-CONUS (Open-Meteo) cities.
- `source_code/water/` – NOAA NWPS continuous gauge discovery and 7-day water forecasts.
- `source_code/electricity/` – CAISO 7-day load forecast retrieval.
- `source_code/map/` – Interactive Leaflet map generator and supporting shapefiles/templates.
- `data/` – Output directory; populated only by GitHub Actions.

## Data collection and timing

- **Weather (Open-Meteo, non-CONUS)**
  - Collected daily by `Daily Forecast Pipeline` at **00:00 UTC** using the Open-Meteo ECMWF-IFS model.
  - `time_of_1h` is the first hourly timestamp returned by Open-Meteo for that forecast (typically close to `00:00:00+00:00` for the forecast day). Columns `1h…168h` step forward hourly from `time_of_1h`.

- **Weather (Herbie, CONUS)**
  - Collected daily by `Daily Forecast Pipeline` at **00:00 UTC** using HRRR and NBM-CO via the Herbie library.
  - For each city in CONUS, the script builds a 168-hour forecast horizon (1h…168h) from the model output, anchored to the 00Z run time used in the Herbie configuration.

- **Water (NOAA NWPS)**
  - Collected daily by `Daily Water Forecast Data` at **18:00 UTC**, when NWPS stageflow forecasts are typically available for the new day.
  - For each gauge, `time_of_1h` is the earliest `validTime` returned by the API (the first available hour near the start of that daily forecast cycle, often around 18Z). Columns `1h…168h` are 168 hourly values starting at `time_of_1h`.

**Electricity (CAISO)**
  - Collected daily by `Daily Forecast Pipeline` at **00:00 UTC** using the 7-day SLD_FCST product.
  - `time_of_1h` is typically `01:00:00+00:00`, so `1h` corresponds to 01Z and the remaining columns step forward hourly.

### Example data rows

**Weather (Open-Meteo / Herbie)**

All weather CSVs share a common structure:

```csv
forecast_day,time_of_1h,1h,2h,3h,4h,...
2025-03-15 00:02:10+00:00,2025-03-15 00:00:00+00:00,-5.2,-5.0,-4.9,-4.7,...
```

- `forecast_day` – UTC timestamp when the forecast was retrieved and appended.
- `time_of_1h` – UTC time of the first hourly forecast value for that row (the start of the time series).
- `1h`, `2h`, … – forecast values at `time_of_1h + 0 h`, `+1 h`, `+2 h`, etc., for the given variable and location.

**Water (NOAA NWPS)**

Water CSVs produced by `source_code/water/all_gauges.py` look like:

```csv
forecast_day,time_of_1h,1h,2h,3h,4h,...,168h
2025-03-15T18:05:12Z,2025-03-15T18:00:00Z,2.31,2.29,2.27,2.26,...,1.84
```

- `forecast_day` – UTC time when the NWPS forecast was issued (or when it was fetched, if the API omits `issuedTime`).
- `time_of_1h` – earliest `validTime` returned by the NWPS API for that gauge on that day.
- `1h` – forecast stage/flow at `time_of_1h`.
- `2h`, `3h`, …, `168h` – forecast values at `time_of_1h + 1 h`, `+2 h`, …, `+167 h`.

**Electricity (CAISO)**

CAISO CSVs produced by `source_code/electricity/fetch_caiso_electricity.py` use:

```csv
forecast_day,time_of_1h,1h,2h,3h,4h,...,168h
2025-03-15,2025-03-15 01:00:00+0000,1500.2,1498.7,1496.0,1493.5,...,1620.3
```

- `forecast_day` – UTC date when the CAISO forecast was retrieved and written.
- `time_of_1h` – first `INTERVAL_START_GMT` timestamp in the CAISO product for that resource (typically 01:00 UTC).
- `1h` – forecast load for that resource at `time_of_1h`.
- `2h`, `3h`, …, `168h` – forecast loads at `time_of_1h + 1 h`, `+2 h`, …, `+167 h`.
