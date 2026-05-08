# Australian Beef & Lamb Market Dashboard

A portfolio-style data project that turns raw Australian beef and lamb source files into cleaned reporting tables, six executive chart exports, and a static business dashboard that can be published with GitHub Pages.

The current reporting window focuses on `2024-01` to `2025-12`:
- exports are monthly DAFF destination flows
- production is quarterly ABS livestock production and slaughter
- the dashboard packages both the market outputs and the ETL logic behind them

## Live Demo

Visit the dashboard here: [https://beef-lamb-market-dashboard.vercel.app/](https://beef-lamb-market-dashboard.vercel.app/)

## What This Project Does

This repository currently supports six layers of work:

1. Clean raw source files from release folders under `data/raw/`.
2. Deduplicate overlapping releases and keep only the latest valid business records.
3. Build quarterly summary outputs and six report-ready PNG charts.
4. Export a static front-end package in `dashboard/` for local review or GitHub Pages deployment.
5. Build a DuckDB star schema, SQL marts, and upload-driven report generator for BI workflows.
6. Serve an AI Agent layer with SQLite, FastAPI, provider-based tool calling, natural-language SQL, summaries, chart suggestions, and a React query page.

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

6. DuckDB star schema and KPI marts  
   Implemented in [src/load/build_duckdb.py](src/load/build_duckdb.py), [sql/duckdb_schema.sql](sql/duckdb_schema.sql), [sql/marts.sql](sql/marts.sql), and [sql/kpi_queries.sql](sql/kpi_queries.sql)

7. Upload-driven report generation  
   Implemented in [src/services/report_service.py](src/services/report_service.py) and [app/streamlit_upload.py](app/streamlit_upload.py)

8. AI Agent API and React query page  
   Implemented in [src/load/load_to_sqlite.py](src/load/load_to_sqlite.py), [src/agent/sql_tools.py](src/agent/sql_tools.py), [src/agent/providers.py](src/agent/providers.py), [src/agent/openai_agent.py](src/agent/openai_agent.py), [api/main.py](api/main.py), and [frontend/](frontend/)

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

## Build The DuckDB BI Model

To create a local DuckDB database from processed CSV outputs:

```bash
python src/load/build_duckdb.py \
  --window-token 2024_01_to_2025_12 \
  --forecast-year 2026
```

This creates `data/processed/meat_market.duckdb` with:

- dimension tables for date, product, destination, and state
- fact tables for monthly exports, quarterly production, quarterly market summary, forecasts, and business insights
- BI mart views for KPI snapshots, quarterly market trends, destination year-on-year movement, forecasts, and business signals

Metric definitions are documented in [data_model/metric_definitions.md](data_model/metric_definitions.md).

## Run The Upload Report App

The Streamlit app accepts processed CSV uploads and returns insights, forecast records, and a markdown business report:

```bash
streamlit run app/streamlit_upload.py
```

Expected upload files:

- `exports_clean_*.csv`
- `market_quarterly_summary_*.csv`

The same logic is exposed through service functions in [src/services/report_service.py](src/services/report_service.py), so it can be moved behind FastAPI later without changing the analytics model.

## Build The SQLite AI Agent Database

The AI Agent uses a local SQLite database built from the processed reporting outputs:

```bash
python src/load/load_to_sqlite.py \
  --window-token 2024_01_to_2025_12 \
  --forecast-year 2026
```

This creates `data/processed/meat_market.db` with:

- `fact_exports`
- `fact_production`
- `market_quarterly_summary`
- `market_insights`
- `market_forecast`
- dimensions for product, destination, and state
- analysis views such as `vw_latest_kpis`, `vw_quarterly_market`, `vw_top_destinations_annual`, `vw_forecast_base_annual`, and `vw_market_insights`

## Run The AI Agent API

The Agent provider is selected by `AI_PROVIDER`.

Provider options:

- `groq`: production default, OpenAI-compatible hosted inference
- `ollama`: local development with a local model
- `openai`: OpenAI Responses API, useful when switching back to OpenAI

`AI_MODEL` overrides the provider-specific model variable when set.

### Groq provider for production

The default hosted provider is Groq with `llama-3.1-8b-instant`.
Groq uses an OpenAI-compatible base URL, so no local model process is needed.

```bash
export AI_PROVIDER="groq"
export GROQ_API_KEY="your-groq-api-key"
export GROQ_MODEL="llama-3.1-8b-instant"
export GROQ_BASE_URL="https://api.groq.com/openai/v1"
uvicorn api.main:app --reload --port 8001
```

Use this setup for Vercel and other production-style deployments. If Groq changes model availability or you want to test another free-tier model, set `GROQ_MODEL` or the generic `AI_MODEL`.

### Ollama provider

For local-only development, you can still use Ollama with Llama 3.1 8B Instruct:

```bash
ollama pull llama3.1:8b-instruct-q4_0

export AI_PROVIDER="ollama"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.1:8b-instruct-q4_0"
uvicorn api.main:app --reload --port 8001
```

Make sure the Ollama desktop app is running, or run `ollama serve` in a separate terminal.

You can also use the generic model override:

```bash
export AI_MODEL="llama3.1:8b-instruct-q4_0"
```

### OpenAI provider

To switch back to OpenAI:

```bash
export AI_PROVIDER="openai"
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-5.4-mini"
uvicorn api.main:app --reload --port 8001
```

Main endpoints:

- `GET /api/health`
- `GET /api/schema`
- `POST /api/sql`
- `POST /api/chat`
- `POST /api/report`

The Agent exposes two internal tools to the model:

- `get_schema`: returns SQLite tables, views, columns, business glossary, and join guidance
- `run_sql_query`: executes read-only SQLite `SELECT` or `WITH` queries with a row limit

`POST /api/chat` performs natural-language-to-SQL, executes the SQL, summarizes the result, and returns a chart recommendation. `POST /api/report` generates the slower business report separately, so the React page can show answer, SQL, rows, and chart first.

## Deploy The AI Agent To Vercel

This repo is configured for a single Vercel deployment that serves:

- the React AI Agent page from `frontend/dist`
- the FastAPI app through `api/index.py`
- same-origin `/api/*` requests through `vercel.json` rewrites to `/api/index`

### 1. Build the SQLite database

Vercel cannot see your local ignored files. Build the SQLite database and commit the deployable DB file:

```bash
python src/load/load_to_sqlite.py \
  --window-token 2024_01_to_2025_12 \
  --forecast-year 2026

git add data/processed/meat_market.db
```

The `.gitignore` keeps raw data ignored but allows `data/processed/meat_market.db`, which is small enough for this portfolio deployment. For a larger production system, move this data to a managed database instead of committing SQLite.

### 2. Configure Vercel environment variables

Set these variables in Vercel Project Settings:

```text
AI_PROVIDER=groq
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.1-8b-instant
GROQ_BASE_URL=https://api.groq.com/openai/v1
CORS_ORIGINS=https://your-project.vercel.app
```

For Preview Deployments, add your preview domain to `CORS_ORIGINS`, or use a comma-separated list:

```text
CORS_ORIGINS=https://your-project.vercel.app,https://your-preview.vercel.app,http://localhost:5173,http://localhost:5273
```

### 3. Deploy from the repository root

The root `vercel.json` handles the build:

- `npm --prefix frontend ci`
- `npm --prefix frontend run build`
- output directory: `frontend/dist`
- Python dependencies: `requirements.txt`
- API function entry: `api/index.py`

After deployment, verify:

```text
https://your-project.vercel.app/api/health
```

Expected provider fields:

```json
{
  "provider": "groq",
  "model": "llama-3.1-8b-instant",
  "available": true
}
```

## Run The React AI Agent Page

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:5173
```

The Vite dev server proxies `/api/*` requests to `http://localhost:8001`.

## Power BI Blueprint

The [powerbi/](powerbi/) folder contains:

- a PBIP project blueprint
- DAX measures
- model and report design screenshots
- instructions for connecting the DuckDB star schema or CSV marts in Power BI Desktop

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
  frontend/                  React AI Agent query page
  api/                       FastAPI app for the Agent layer
  data/raw/                  local raw ABS and DAFF release folders
  data/processed/            local cleaned and summary outputs
  reports/charts/            generated PNG report exports
  src/
    agent/                   OpenAI orchestration and read-only SQL tools
    services/                API-ready report generation service layer
    transform/               source-specific cleaning logic
    load/                    database loaders for SQLite and DuckDB
    build_market_summary.py
    build_report_charts.py
    export_dashboard_assets.py
    run_pipeline.py
    run_reporting_pipeline.py
  sql/                       SQLite schema plus DuckDB marts and KPI examples
  data_model/                metric definitions and KPI semantics
  powerbi/                   Power BI project blueprint, DAX, and screenshots
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
