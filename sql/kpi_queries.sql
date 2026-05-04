-- Portfolio KPI queries for DuckDB, Power BI validation, and analyst review.

-- 1. Executive KPI snapshot for the latest available periods.
SELECT
    kpi_group,
    period_label,
    product_name,
    ROUND(kpi_value, 0) AS kpi_value,
    unit
FROM mart_kpi_snapshot
ORDER BY kpi_group, product_name;

-- 2. Annual export, production, and export-share view.
SELECT
    year,
    product_name,
    ROUND(SUM(exports_tonnes), 0) AS exports_tonnes,
    ROUND(SUM(production_tonnes), 0) AS production_tonnes,
    ROUND(SUM(exports_tonnes) / NULLIF(SUM(production_tonnes), 0) * 100, 1)
        AS export_share_pct
FROM mart_quarterly_market
GROUP BY year, product_name
ORDER BY year, product_name;

-- 3. Destination growth and decline ranking.
SELECT
    year,
    product_name,
    destination_name,
    ROUND(export_tonnes, 0) AS export_tonnes,
    ROUND(yoy_change_tonnes, 0) AS yoy_change_tonnes,
    ROUND(yoy_change_pct, 1) AS yoy_change_pct
FROM mart_destination_yoy
WHERE prior_year_export_tonnes IS NOT NULL
ORDER BY ABS(yoy_change_tonnes) DESC
LIMIT 20;

-- 4. Forecast scenario bands for annual planning.
SELECT
    forecast_year,
    product_name,
    target_metric,
    scenario,
    ROUND(forecast_value, 1) AS forecast_value,
    unit,
    ROUND(backtest_mape_pct, 1) AS backtest_mape_pct
FROM mart_forecast_scenario_summary
WHERE period_type = 'annual'
ORDER BY forecast_year, product_name, target_metric, scenario;

-- 5. Business signals that can be displayed in a report page.
SELECT
    sort_order,
    product_name,
    category,
    metric,
    direction,
    business_signal,
    recommendation
FROM mart_business_signals
ORDER BY sort_order
LIMIT 12;

