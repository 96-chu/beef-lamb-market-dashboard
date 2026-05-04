# Semantic Model Notes

Use the DuckDB star schema as the semantic model source.

Recommended import tables:

- `dim_date`
- `dim_product`
- `dim_destination`
- `dim_state`
- `fact_exports_monthly`
- `fact_production_quarterly`
- `fact_market_quarterly`
- `fact_forecast`
- `fact_insights`

Recommended mart views for report pages:

- `mart_kpi_snapshot`
- `mart_quarterly_market`
- `mart_destination_yoy`
- `mart_forecast_scenario_summary`
- `mart_business_signals`

