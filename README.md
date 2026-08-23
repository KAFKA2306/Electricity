# Electricity — U.S. grid evidence

[![EIA data integrity](https://github.com/KAFKA2306/Electricity/actions/workflows/eia-data.yml/badge.svg)](https://github.com/KAFKA2306/Electricity/actions/workflows/eia-data.yml)
[![EIA electricity source](https://github.com/KAFKA2306/Electricity/actions/workflows/eia-electricity-source.yml/badge.svg)](https://github.com/KAFKA2306/Electricity/actions/workflows/eia-electricity-source.yml)
[![Deploy Pages](https://github.com/KAFKA2306/Electricity/actions/workflows/pages.yml/badge.svg)](https://github.com/KAFKA2306/Electricity/actions/workflows/pages.yml)

**EIA一次情報から、米国の電力需要・発電・発電構成・設備容量を再現可能な形で追跡します。**

## Public dashboard

- Daily dashboard: https://kafka2306.github.io/Electricity/
- Latest complete US48 demand and day-over-day change
- Latest complete net generation
- Generation mix aligned to a common complete UTC day
- Operating and planned capacity shown separately
- Every public value is read from the canonical JSON below; Pages does not maintain a second database

## Canonical data

- [`api/v1/electricity/index.json`](api/v1/electricity/index.json) — dataset frequency, kind and primary source
- [`api/v1/electricity/demand.json`](api/v1/electricity/demand.json) — daily actual demand
- [`api/v1/electricity/generation.json`](api/v1/electricity/generation.json) — daily actual net generation
- [`api/v1/electricity/generation-mix.json`](api/v1/electricity/generation-mix.json) — daily generation by fuel
- [`api/v1/electricity/interchange.json`](api/v1/electricity/interchange.json) — daily interchange
- [`api/v1/electricity/capacity.json`](api/v1/electricity/capacity.json) — reported generator inventory
- [`api/v1/electricity/capacity-additions.json`](api/v1/electricity/capacity-additions.json) — planned / retired capacity
- [`api/v1/electricity/metrics.json`](api/v1/electricity/metrics.json) — compact latest observations

Daily actuals are generated from complete hourly observations in EIA U.S. Electric System Operating Data. Generator inventory comes from EIA-860M. Raw evidence retains source URL, retrieval time and SHA-256 under `data/electricity/official/`.

## Data contract

- daily actual demand / generation and monthly capacity inventory are different cadences
- MWh generation or demand is not mixed with MW capacity
- operating and planned capacity remain separate
- incomplete hourly days are not promoted to complete daily observations
- forecast values are not presented as actuals
- missing or stale observations are not replaced with zero

## Verification

- [`.github/workflows/eia-data.yml`](.github/workflows/eia-data.yml) validates the canonical data contract
- [`.github/workflows/eia-electricity-source.yml`](.github/workflows/eia-electricity-source.yml) refreshes primary EIA evidence
- [`.github/workflows/pages.yml`](.github/workflows/pages.yml) builds Pages from canonical JSON and verifies the exact deployed commit

## Primary sources

- EIA Open Data: https://www.eia.gov/opendata/
- EIA bulk downloads: https://www.eia.gov/opendata/bulkfiles.php
- EIA-860M: https://www.eia.gov/electricity/data/eia860m/
