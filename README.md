# Australian Beef & Lamb Market Dashboard

A portfolio-style data project that turns raw Australian beef and lamb source files into cleaned reporting tables, six executive chart exports, and a static business dashboard that can be published with GitHub Pages.

The current reporting window focuses on `2024-01` to `2025-12`:
- exports are monthly DAFF destination flows
- production is quarterly ABS livestock production and slaughter
- the dashboard packages both the market outputs and the ETL logic behind them

## What This Project Does

This repository currently supports four layers of work:

1. Clean raw source files from release folders under `data/raw/`.
2. Deduplicate overlapping releases and keep only the latest valid business records.
3. Build quarterly summary outputs and six report-ready PNG charts.
4. Export a static front-end package in `dashboard/` for local review or GitHub Pages deployment.

## Data Sources

### 1. ABS Livestock Products, Australia

Used for quarterly slaughter and meat production.

- Source type: ABS Excel workbooks
- Raw location: `data/raw/production/<release-month>/`
- Workbooks used by the current cleaning logic:
  - `7215003.xlsx` for beef slaughter
  - `7215006.xlsx` for lamb slaughter
  - `7215009.xlsx` for beef production
  - `7215012.xlsx` for lamb production

How the project uses ABS data:
- Reads the `Data1` sheet from each workbook
- Extracts description, series type, and series id metadata from fixed ABS rows
- Keeps only `Original` series
- Parses measure, animal, and state from ABS description strings
- Standardizes `Total (State)` to `Australia`
- Deduplicates repeated history by keeping the latest `release_month` for each `date + series_id`
- Filters the final business window to `2024-01` through `2025-12`

### 2. DAFF Monthly 57 Destination Reports

Used for monthly export flows by destination.

- Source type: DAFF Excel destination reports
- Raw location: `data/raw/exports/<release-month>/`
- Common file pattern: `m57dest.xlsx`

How the project uses DAFF data:
- Reads the `Report` sheet
- Extracts the business `report_month` from the title row
- Normalizes headers and destination names
- Keeps only the dashboard metrics:
  - `Beef & Veal Total`
  - `Total Lamb`
  - `Total Mutton`
  - `Total Meats`
- Removes subtotal and catch-all destinations such as:
  - `Total Aus`
  - `Total Asia`
  - `Other EU`
  - `All Other Countries`
- Deduplicates repeated releases by keeping the latest `release_month` for each `report_month + destination + metric_name`
- Aggregates monthly flows into quarterly exports for reporting

## Pipeline Overview

The current end-to-end reporting pipeline is driven by [src/run_reporting_pipeline.py](src/run_reporting_pipeline.py).

Main processing steps:

1. Production cleaning  
   Implemented in [src/transform/clean_production.py](src/transform/clean_production.py)

2. Export cleaning  
   Implemented in [src/transform/clean_exports.py](src/transform/clean_exports.py)

3. Quarterly market summary build  
   Implemented in [src/build_market_summary.py](src/build_market_summary.py)

4. Chart export  
   Implemented in [src/build_report_charts.py](src/build_report_charts.py)

5. Static dashboard asset export  
   Implemented in [src/export_dashboard_assets.py](src/export_dashboard_assets.py)

## Current Outputs

The current reporting flow produces these main artifacts for the `2024-01` to `2025-12` window:

- `production_clean_archive_2024_01_to_2025_12.csv`
- `production_clean_latest_2024_01_to_2025_12.csv`
- `exports_clean_2024_01_to_2025_12.csv`
- `exports_quarterly_2024_01_to_2025_12.csv`
- `market_quarterly_summary_2024_01_to_2025_12.csv`
- `dashboard/data/dashboard_data.json`

Generated chart exports:

1. `chart_01_kpi_cards.png`
2. `chart_02_production_trend.png`
3. `chart_03_exports_trend.png`
4. `chart_04_export_product_mix.png`
5. `chart_05_top_destinations.png`
6. `chart_06_production_vs_exports.png`

These images are copied into `dashboard/assets/reports/` and reused by the static dashboard.

## Dashboard

The dashboard entry point is [dashboard/index.html](dashboard/index.html).

It includes:
- a business-style landing section with run coverage
- KPI cards for latest beef and lamb exports and production
- an auto-playing report deck based on the six exported PNG charts
- front-end interactive charts powered by `dashboard/data/dashboard_data.json`
- detailed source-system cards describing provenance and transformation logic
- an interactive ETL pipeline view
- quality-control and artifact inventory sections

The dashboard assets are deployed from `.github/workflows/deploy-dashboard.yml` when `main` is updated.

## Local Setup

### 1. Create the conda environment

```bash
conda env create -f environment.yml
```

### 2. Activate the environment

```bash
conda activate meat-bi
```

## Run The Pipeline

To refresh the full reporting package for the current business window:

```bash
python src/run_reporting_pipeline.py \
  --start-release-month 2024-01 \
  --end-release-month 2025-12 \
  --start-data-month 2024-01 \
  --end-data-month 2025-12
```

This run is intended to:
- clean production releases
- clean export releases
- build quarterly market summary data
- generate six PNG charts
- export dashboard JSON and copy report assets into `dashboard/`

## Run The Dashboard Locally

Because the front-end reads JSON with `fetch`, it should be served from a local static server instead of opened directly with `file://`.

From the project root:

```bash
python3 -m http.server 8000 --directory dashboard
```

Then open:

```text
http://localhost:8000
```

## Repository Structure

```text
beef-lamb-market-dashboard/
  dashboard/                 static front-end and packaged report assets
  data/raw/                  local raw ABS and DAFF release folders
  data/processed/            local cleaned and summary outputs
  reports/charts/            generated PNG report exports
  src/
    transform/               source-specific cleaning logic
    build_market_summary.py
    build_report_charts.py
    export_dashboard_assets.py
    run_pipeline.py
    run_reporting_pipeline.py
  .github/workflows/         GitHub Pages deployment workflow
  environment.yml
```

## Notes On Tracked Files

This repository currently ignores local data and generated report assets:

- `data/`
- `reports/`

That means raw source files, processed CSV outputs, and generated chart images are expected to exist locally during development, but are not committed to Git by default.

## AI-Assisted Development Note

This project was developed with personal instructions and iterative prompting used together with Codex.

In practice, that means:
- the project direction, business framing, and presentation goals were defined by me
- Codex was used to help implement Python pipeline code, static dashboard code, and documentation updates
- the repository reflects an AI-assisted development workflow rather than fully manual coding

I want that collaboration to be explicit, so the dashboard and codebase should be understood as a portfolio project built through guided human direction plus Codex execution support.

## Limitations

- The current portfolio scope is centered on the `2024-01` to `2025-12` reporting window.
- Production is quarterly, while exports are monthly, so the reporting layer mixes frequencies intentionally.
- Export analysis excludes subtotal destinations to avoid double counting.
- The static dashboard is designed for presentation and explanation, not for live backend querying.
