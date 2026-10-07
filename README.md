# Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED

# weather-water-power-forecast
The software maintains a continuously updated U.S. archive of weather, water flow, and electricity demand forecasts. Daily snapshots preserve forecasts up to seven days ahead, enabling backtesting, forecast evaluation, trend analysis, and energy-water system research.

## Repository structure

- `source_code/weather/` – Weather retrieval for CONUS (Herbie) and non-CONUS (Open-Meteo) cities.
- `source_code/water/` – NOAA NWPS continuous gauge discovery and 7-day water forecasts.
- `source_code/electricity/` – CAISO 7-day load forecast retrieval (no gridstatus dependency).
- `source_code/map/` – Interactive Leaflet map generator and supporting shapefiles/templates.
- `data/` – Output directory; populated only by GitHub Actions and local runs.

## Data collection and timing

- **Weather (Open-Meteo, non-CONUS)**
  - Collected daily by `Daily Forecast Pipeline` at **00:00 UTC**.
  - `time_of_1h` is always `00:00:00+00:00` for each forecast day, so `1h` corresponds to 00Z, `2h` to 01Z, … up to 168h.

- **Weather (Herbie, CONUS)**
  - Collected daily by `Daily Forecast Pipeline` at **00:00 UTC** using HRRR and NBM-CO via the Herbie library.
  - For each city in CONUS, the script builds a 168-hour forecast horizon (1h…168h) from the model output, anchored to the 00Z run time used in the Herbie configuration.

- **Water (NOAA NWPS)**
  - Collected daily by `Daily Water Forecast Data` at **18:00 UTC** to align with the NWPS stageflow forecast cycle.
  - For each gauge, `time_of_1h` is the first `validTime` returned by the API (often near 18Z). Columns `1h…168h` are 168 hourly values starting at `time_of_1h`.

- **Electricity (CAISO)**
  - Collected daily by `Daily Forecast Pipeline` at **00:00 UTC** using the 7-day SLD_FCST product.
  - `time_of_1h` is typically `01:00:00+00:00`, so `1h` corresponds to 01Z and the remaining columns step forward hourly.

For all three domains, the true valid time for column `h` is:

> `valid_time_utc = time_of_1h + (h - 1) hours`

When comparing to other datasets (e.g., reanalyses, observations, or other models), use `valid_time_utc` (and location) as the key rather than assuming that `1h` always corresponds to the same wall-clock time across products.
