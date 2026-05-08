# Metric Definitions

This semantic layer describes the portfolio KPIs used by the static dashboard,
DuckDB marts, Power BI model, and upload-driven report generator.

## Core Grain

- Export facts are monthly destination-level tonnes by product.
- Production facts are quarterly state-level values by product and metric group.
- Market summary facts are quarterly Australia-level product totals.
- Forecast facts contain monthly, quarterly, and annual planning scenarios.

## KPI Dictionary

### Latest Exports

- **Business meaning:** Most recent monthly export demand for beef or lamb.
- **Formula:** `SUM(fact_exports_monthly.tonnes)` filtered to the latest `report_month_key`.
- **Unit:** tonnes.
- **Decision use:** Measures current outbound demand and helps size near-term logistics and market allocation.
- **Caution:** Monthly exports are seasonal, so compare with the same month last year where possible.

### Latest Production

- **Business meaning:** Most recent quarterly Australia-level meat production.
- **Formula:** `SUM(fact_production_quarterly.value)` filtered to `metric_group = 'production'`, `state_name = 'Australia'`, and latest quarter.
- **Unit:** tonnes.
- **Decision use:** Indicates available supply capacity behind export growth.
- **Caution:** Production is quarterly while exports are monthly; period alignment is handled in quarterly marts.

### Export Tonnes

- **Business meaning:** Product volume sold into export markets.
- **Formula:** `SUM(fact_exports_monthly.tonnes)` by month, quarter, year, product, or destination.
- **Unit:** tonnes.
- **Decision use:** Tracks demand momentum, destination concentration, and product mix.
- **Caution:** Subtotal destinations are removed in the cleaning layer to avoid double counting.

### Production Tonnes

- **Business meaning:** Meat produced domestically for a product.
- **Formula:** `SUM(fact_production_quarterly.value)` for production records.
- **Unit:** tonnes.
- **Decision use:** Supply-side anchor for interpreting export growth or decline.
- **Caution:** State-level totals include an Australia aggregate row; use either state detail or Australia total, not both.

### Export Share Of Production

- **Business meaning:** Portion of production volume represented by exports.
- **Formula:** `exports_tonnes / production_tonnes * 100`.
- **Unit:** percent.
- **Decision use:** Pressure indicator for export pull versus available supply.
- **Caution:** This is a directional ratio, not a full domestic consumption calculation.

### Year-On-Year Export Change

- **Business meaning:** How much annual export volume changed versus the previous year.
- **Formula:** `current_year_export_tonnes - prior_year_export_tonnes`.
- **Unit:** tonnes.
- **Decision use:** Identifies product and destination growth/decline drivers.
- **Caution:** Small destinations can show high percentage swings on low volume.

### Year-On-Year Export Change Percent

- **Business meaning:** Relative export growth or decline versus the previous year.
- **Formula:** `(current_year_export_tonnes / prior_year_export_tonnes - 1) * 100`.
- **Unit:** percent.
- **Decision use:** Highlights momentum and market risk.
- **Caution:** Interpret together with absolute tonnes to avoid over-weighting small markets.

### Top Destination Share

- **Business meaning:** Concentration of export demand in leading destination markets.
- **Formula:** `top_n_destination_tonnes / total_product_export_tonnes * 100`.
- **Unit:** percent.
- **Decision use:** Supports account prioritisation and concentration-risk discussion.
- **Caution:** Destination labels distinguish markets such as USA East and USA West when source data does.

### Forecast Value

- **Business meaning:** Estimated future exports, production, or export share under a scenario.
- **Formula:** Linear trend with seasonal fixed effects; scenarios use residual error and configured percentage bands.
- **Unit:** tonnes or percent.
- **Decision use:** Planning range for capacity, market focus, and risk review.
- **Caution:** Forecasts are scenario bands, not guarantees; climate, policy, biosecurity, freight, and currency shocks can move outcomes.

### Backtest MAPE

- **Business meaning:** Historical forecast error from a simple holdout backtest.
- **Formula:** `MEAN(ABS((actual - predicted) / actual)) * 100`.
- **Unit:** percent.
- **Decision use:** Provides a rough reliability indicator for forecast discussion.
- **Caution:** The history window is short, so use it as a transparency measure rather than a full model validation framework.

## Recommended Power BI Measures

```DAX
Export Tonnes = SUM ( fact_exports_monthly[tonnes] )

Production Tonnes = SUM ( fact_production_quarterly[value] )

Export Share % = DIVIDE ( [Export Tonnes], [Production Tonnes] )

Forecast Value = SUM ( fact_forecast[forecast_value] )

YoY Export Change =
    [Export Tonnes]
        - CALCULATE ( [Export Tonnes], SAMEPERIODLASTYEAR ( dim_date[date_value] ) )

YoY Export Change % =
    DIVIDE (
        [YoY Export Change],
        CALCULATE ( [Export Tonnes], SAMEPERIODLASTYEAR ( dim_date[date_value] ) )
    )
```

