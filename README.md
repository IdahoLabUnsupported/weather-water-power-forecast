# Copyright 2025, Battelle Energy Alliance, LLC, ALL RIGHTS RESERVED

# weather-water-power-forecast
The software maintains a continuously updated U.S. archive of weather, water flow, and electricity demand forecasts. Daily snapshots preserve forecasts up to seven days ahead, enabling backtesting, forecast evaluation, trend analysis, and energy-water system research.

## Repository structure

- `source_code/weather/` – Weather retrieval for CONUS (Herbie) and non-CONUS (Open-Meteo) cities.
- `source_code/water/` – NOAA NWPS continuous gauge discovery and 7-day water forecasts.
- `source_code/electricity/` – CAISO 7-day load forecast retrieval.
- `source_code/map/` – Interactive Leaflet map generator and supporting shapefiles/templates.
- `data/` – Output directory; populated only by GitHub Actions.

## Data outputs

- Weather forecasts written under `data/weather/`.
- River stage/flow forecasts written under `data/water/`.
- CAISO 7-day load forecasts written under `data/electricity/`.
- Interactive Leaflet map written to `data_locations.html`.

All data products are updated once per day by GitHub Actions, currently scheduled around **00:01 UTC**. For detailed data formats, timing, and example rows, see `data/README.md`.
