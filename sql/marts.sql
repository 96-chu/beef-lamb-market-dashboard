-- BI marts built on top of the DuckDB star schema.

CREATE OR REPLACE VIEW mart_quarterly_market AS
SELECT
    mq.quarter_label,
    CAST(SUBSTR(mq.quarter_label, 1, 4) AS INTEGER) AS year,
    CAST(SUBSTR(mq.quarter_label, 6, 1) AS INTEGER) AS quarter_number,
    p.product_code,
    p.product_name,
    mq.exports_tonnes,
    mq.production_tonnes,
    mq.slaughter_value,
    mq.exports_tonnes / NULLIF(mq.production_tonnes, 0) * 100 AS export_share_pct
FROM fact_market_quarterly AS mq
JOIN dim_product AS p
    ON mq.product_key = p.product_key;

CREATE OR REPLACE VIEW mart_destination_yoy AS
WITH annual_destination AS (
    SELECT
        d.year,
        p.product_code,
        p.product_name,
        dest.destination_name,
        SUM(f.tonnes) AS export_tonnes
    FROM fact_exports_monthly AS f
    JOIN dim_date AS d
        ON f.report_month_key = d.date_key
    JOIN dim_product AS p
        ON f.product_key = p.product_key
    JOIN dim_destination AS dest
        ON f.destination_key = dest.destination_key
    WHERE p.product_code IN ('beef', 'lamb')
    GROUP BY 1, 2, 3, 4
)
SELECT
    year,
    product_code,
    product_name,
    destination_name,
    export_tonnes,
    LAG(export_tonnes) OVER (
        PARTITION BY product_code, destination_name
        ORDER BY year
    ) AS prior_year_export_tonnes,
    export_tonnes
        - LAG(export_tonnes) OVER (
            PARTITION BY product_code, destination_name
            ORDER BY year
        ) AS yoy_change_tonnes,
    (
        export_tonnes
        / NULLIF(
            LAG(export_tonnes) OVER (
                PARTITION BY product_code, destination_name
                ORDER BY year
            ),
            0
        )
        - 1
    ) * 100 AS yoy_change_pct
FROM annual_destination;

CREATE OR REPLACE VIEW mart_kpi_snapshot AS
WITH latest_export_month AS (
    SELECT MAX(report_month_key) AS date_key
    FROM fact_exports_monthly
),
latest_production_quarter AS (
    SELECT MAX(quarter_date_key) AS date_key
    FROM fact_production_quarterly
    WHERE metric_group = 'production'
        AND state_key IN (
            SELECT state_key FROM dim_state WHERE state_name = 'Australia'
        )
)
SELECT
    'Latest exports' AS kpi_group,
    d.month_label AS period_label,
    p.product_code,
    p.product_name,
    SUM(f.tonnes) AS kpi_value,
    'tonnes' AS unit
FROM fact_exports_monthly AS f
JOIN latest_export_month AS latest
    ON f.report_month_key = latest.date_key
JOIN dim_date AS d
    ON f.report_month_key = d.date_key
JOIN dim_product AS p
    ON f.product_key = p.product_key
WHERE p.product_code IN ('beef', 'lamb')
GROUP BY 1, 2, 3, 4

UNION ALL

SELECT
    'Latest production' AS kpi_group,
    d.quarter_label AS period_label,
    p.product_code,
    p.product_name,
    SUM(f.value) AS kpi_value,
    'tonnes' AS unit
FROM fact_production_quarterly AS f
JOIN latest_production_quarter AS latest
    ON f.quarter_date_key = latest.date_key
JOIN dim_date AS d
    ON f.quarter_date_key = d.date_key
JOIN dim_product AS p
    ON f.product_key = p.product_key
JOIN dim_state AS s
    ON f.state_key = s.state_key
WHERE p.product_code IN ('beef', 'lamb')
    AND s.state_name = 'Australia'
    AND f.metric_group = 'production'
GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW mart_forecast_scenario_summary AS
SELECT
    forecast_year,
    p.product_code,
    p.product_name,
    target_metric,
    period_type,
    period_label,
    scenario,
    forecast_value,
    unit,
    model_name,
    backtest_mape_pct
FROM fact_forecast AS f
JOIN dim_product AS p
    ON f.product_key = p.product_key;

CREATE OR REPLACE VIEW mart_business_signals AS
SELECT
    i.sort_order,
    p.product_code,
    p.product_name,
    i.category,
    i.metric,
    i.period_label,
    i.direction,
    i.business_signal,
    i.recommendation,
    i.narrative
FROM fact_insights AS i
LEFT JOIN dim_product AS p
    ON i.product_key = p.product_key;

