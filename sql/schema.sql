PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS vw_market_insights;
DROP VIEW IF EXISTS vw_forecast_base_annual;
DROP VIEW IF EXISTS vw_top_destinations_annual;
DROP VIEW IF EXISTS vw_latest_kpis;
DROP VIEW IF EXISTS vw_quarterly_market;

DROP TABLE IF EXISTS market_forecast;
DROP TABLE IF EXISTS market_insights;
DROP TABLE IF EXISTS market_quarterly_summary;
DROP TABLE IF EXISTS fact_production;
DROP TABLE IF EXISTS fact_exports;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_state;
DROP TABLE IF EXISTS dim_destination;

CREATE TABLE dim_product (
    product_code TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    product_category TEXT NOT NULL DEFAULT 'meat'
);

CREATE TABLE dim_state (
    state_name TEXT PRIMARY KEY,
    country_name TEXT NOT NULL DEFAULT 'Australia'
);

CREATE TABLE dim_destination (
    destination_name TEXT PRIMARY KEY,
    region_group TEXT NOT NULL DEFAULT 'Destination market'
);

CREATE TABLE fact_exports (
    export_id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_month TEXT NOT NULL,
    report_month TEXT NOT NULL,
    year INTEGER NOT NULL,
    quarter TEXT NOT NULL,
    destination TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    product TEXT NOT NULL,
    metric_group TEXT NOT NULL,
    unit TEXT NOT NULL,
    period_type TEXT NOT NULL,
    report_scope TEXT NOT NULL,
    is_cumulative INTEGER NOT NULL DEFAULT 0,
    tonnes REAL NOT NULL,
    source_file TEXT NOT NULL,
    FOREIGN KEY (product) REFERENCES dim_product(product_code),
    FOREIGN KEY (destination) REFERENCES dim_destination(destination_name)
);

CREATE TABLE fact_production (
    production_id INTEGER PRIMARY KEY AUTOINCREMENT,
    release_month TEXT NOT NULL,
    date TEXT NOT NULL,
    quarter TEXT NOT NULL,
    quarter_start_date TEXT,
    quarter_end_date TEXT,
    year INTEGER NOT NULL,
    product TEXT NOT NULL,
    metric_group TEXT NOT NULL,
    unit TEXT NOT NULL,
    period_type TEXT NOT NULL,
    measure TEXT,
    animal TEXT,
    state TEXT NOT NULL,
    series_type TEXT,
    series_id TEXT,
    value REAL NOT NULL,
    source_file TEXT NOT NULL,
    FOREIGN KEY (product) REFERENCES dim_product(product_code),
    FOREIGN KEY (state) REFERENCES dim_state(state_name)
);

CREATE TABLE market_quarterly_summary (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    quarter TEXT NOT NULL,
    product TEXT NOT NULL,
    exports_tonnes REAL,
    production_tonnes REAL,
    slaughter_value REAL,
    FOREIGN KEY (product) REFERENCES dim_product(product_code)
);

CREATE TABLE market_insights (
    insight_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    metric TEXT NOT NULL,
    product TEXT,
    period TEXT,
    comparison_period TEXT,
    value REAL,
    comparison_value REAL,
    change_value REAL,
    change_pct REAL,
    unit TEXT,
    direction TEXT,
    business_signal TEXT,
    recommendation TEXT,
    narrative TEXT,
    sort_order INTEGER,
    FOREIGN KEY (product) REFERENCES dim_product(product_code)
);

CREATE TABLE market_forecast (
    forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_year INTEGER NOT NULL,
    target_metric TEXT NOT NULL,
    product TEXT NOT NULL,
    period_type TEXT NOT NULL,
    period TEXT NOT NULL,
    scenario TEXT NOT NULL,
    forecast_value REAL,
    unit TEXT,
    model_name TEXT,
    model_detail TEXT,
    training_start TEXT,
    training_end TEXT,
    training_points INTEGER,
    residual_std REAL,
    backtest_mape_pct REAL,
    FOREIGN KEY (product) REFERENCES dim_product(product_code)
);

CREATE INDEX idx_fact_exports_month_product_destination
ON fact_exports (report_month, product, destination);

CREATE INDEX idx_fact_exports_year_product_destination
ON fact_exports (year, product, destination);

CREATE INDEX idx_fact_exports_metric_group
ON fact_exports (metric_group, unit);

CREATE INDEX idx_fact_production_date_product_state
ON fact_production (date, product, state);

CREATE INDEX idx_fact_production_metric_group
ON fact_production (metric_group, unit);

CREATE INDEX idx_market_summary_quarter_product
ON market_quarterly_summary (quarter, product);

CREATE INDEX idx_market_forecast_product_period
ON market_forecast (product, period_type, period, scenario);

CREATE VIEW vw_quarterly_market AS
SELECT
    s.quarter,
    s.product,
    p.product_name,
    s.exports_tonnes,
    s.production_tonnes,
    s.slaughter_value,
    CASE
        WHEN s.production_tonnes IS NULL OR s.production_tonnes = 0 THEN NULL
        ELSE ROUND(s.exports_tonnes * 100.0 / s.production_tonnes, 2)
    END AS export_share_pct
FROM market_quarterly_summary AS s
LEFT JOIN dim_product AS p
    ON s.product = p.product_code;

CREATE VIEW vw_latest_kpis AS
WITH latest_export_month AS (
    SELECT MAX(report_month) AS report_month
    FROM fact_exports
    WHERE product IN ('beef', 'lamb')
),
latest_production_quarter AS (
    SELECT MAX(date) AS date
    FROM fact_production
    WHERE product IN ('beef', 'lamb')
        AND state = 'Australia'
        AND metric_group = 'production'
        AND unit = 'tonnes'
),
monthly_exports AS (
    SELECT
        'latest_monthly_exports' AS metric,
        e.report_month AS period,
        e.product,
        SUM(e.tonnes) AS value,
        'tonnes' AS unit
    FROM fact_exports AS e
    JOIN latest_export_month AS latest
        ON e.report_month = latest.report_month
    WHERE e.product IN ('beef', 'lamb')
        AND e.metric_group = 'export_volume'
    GROUP BY e.report_month, e.product
),
quarterly_production AS (
    SELECT
        'latest_quarterly_production' AS metric,
        p.quarter AS period,
        p.product,
        SUM(p.value) AS value,
        'tonnes' AS unit
    FROM fact_production AS p
    JOIN latest_production_quarter AS latest
        ON p.date = latest.date
    WHERE p.product IN ('beef', 'lamb')
        AND p.state = 'Australia'
        AND p.metric_group = 'production'
        AND p.unit = 'tonnes'
    GROUP BY p.quarter, p.product
)
SELECT * FROM monthly_exports
UNION ALL
SELECT * FROM quarterly_production;

CREATE VIEW vw_top_destinations_annual AS
WITH destination_totals AS (
    SELECT
        year,
        product,
        destination,
        SUM(tonnes) AS tonnes
    FROM fact_exports
    WHERE product IN ('beef', 'lamb')
        AND metric_group = 'export_volume'
    GROUP BY year, product, destination
),
ranked AS (
    SELECT
        year,
        product,
        destination,
        tonnes,
        RANK() OVER (
            PARTITION BY year, product
            ORDER BY tonnes DESC
        ) AS destination_rank
    FROM destination_totals
)
SELECT
    year,
    product,
    destination,
    ROUND(tonnes, 2) AS tonnes,
    destination_rank
FROM ranked
WHERE destination_rank <= 10;

CREATE VIEW vw_forecast_base_annual AS
SELECT
    f.forecast_year,
    f.product,
    p.product_name,
    f.target_metric,
    f.forecast_value,
    f.unit,
    f.model_name,
    f.training_start,
    f.training_end,
    f.training_points,
    f.backtest_mape_pct
FROM market_forecast AS f
LEFT JOIN dim_product AS p
    ON f.product = p.product_code
WHERE f.scenario = 'base'
    AND f.period_type = 'annual';

CREATE VIEW vw_market_insights AS
SELECT
    i.insight_id,
    i.category,
    i.metric,
    i.product,
    p.product_name,
    i.period,
    i.comparison_period,
    i.value,
    i.comparison_value,
    i.change_value,
    i.change_pct,
    i.unit,
    i.direction,
    i.business_signal,
    i.recommendation,
    i.narrative,
    i.sort_order
FROM market_insights AS i
LEFT JOIN dim_product AS p
    ON i.product = p.product_code;
