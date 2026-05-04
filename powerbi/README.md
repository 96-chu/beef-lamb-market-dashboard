# Power BI Model Blueprint

This folder contains a version-controlled Power BI Desktop blueprint for the
beef and lamb market intelligence portfolio project.

## Files

- `BeefLambMarketDashboard.pbip` is the project entry file for a Power BI Desktop project workflow.
- `dax/measures.dax` contains the measures used in the semantic model.
- `screenshots/model_view.svg` documents the intended star-schema relationship design.
- `screenshots/report_page.svg` documents the intended executive report page layout.

## Data Connection

Preferred model source:

```text
data/processed/meat_market.duckdb
```

Build it with:

```bash
python src/load/build_duckdb.py \
  --window-token 2024_01_to_2025_12 \
  --forecast-year 2026
```

Power BI Desktop does not natively write a valid `.pbix` file from Python in this
macOS development environment. Open the PBIP blueprint in Power BI Desktop,
connect to the DuckDB marts or exported CSVs, add the DAX measures, and save the
final binary as `BeefLambMarketDashboard.pbix`.

## Recommended Pages

1. **Executive Overview**
   - KPI cards for latest exports, latest production, and export share.
   - Quarterly export and production trend by product.
   - Forecast scenario band by product.

2. **Destination Portfolio**
   - Destination ranking by tonnes.
   - Year-on-year gain and decline waterfall or bar chart.
   - Concentration signal by top destinations.

3. **Forecast And Risk**
   - Annual forecast by target metric and scenario.
   - Backtest MAPE table.
   - Business signals and recommendations table.

