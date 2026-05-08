-- DuckDB star schema for the beef and lamb portfolio BI layer.
-- Source CSVs remain in data/processed; this schema creates a compact model
-- for Power BI, ad hoc SQL analysis, and upload/report services.

DROP VIEW IF EXISTS mart_business_signals;
DROP VIEW IF EXISTS mart_forecast_scenario_summary;
DROP VIEW IF EXISTS mart_kpi_snapshot;
DROP VIEW IF EXISTS mart_destination_yoy;
DROP VIEW IF EXISTS mart_quarterly_market;

DROP TABLE IF EXISTS fact_insights;
DROP TABLE IF EXISTS fact_forecast;
DROP TABLE IF EXISTS fact_market_quarterly;
DROP TABLE IF EXISTS fact_production_quarterly;
DROP TABLE IF EXISTS fact_exports_monthly;
DROP TABLE IF EXISTS dim_state;
DROP TABLE IF EXISTS dim_destination;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_date;

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    date_value DATE NOT NULL,
    year INTEGER NOT NULL,
    month_number INTEGER NOT NULL,
    month_label TEXT NOT NULL,
    quarter_number INTEGER NOT NULL,
    quarter_label TEXT NOT NULL,
    period_type TEXT NOT NULL
);

CREATE TABLE dim_product (
    product_key INTEGER PRIMARY KEY,
    product_code TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    product_family TEXT NOT NULL
);

CREATE TABLE dim_destination (
    destination_key INTEGER PRIMARY KEY,
    destination_name TEXT NOT NULL UNIQUE,
    region_group TEXT NOT NULL DEFAULT 'Destination market'
);

CREATE TABLE dim_state (
    state_key INTEGER PRIMARY KEY,
    state_name TEXT NOT NULL UNIQUE,
    country_name TEXT NOT NULL DEFAULT 'Australia'
);

CREATE TABLE fact_exports_monthly (
    report_month_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    destination_key INTEGER NOT NULL,
    release_month DATE,
    metric_name TEXT NOT NULL,
    metric_group TEXT NOT NULL,
    unit TEXT NOT NULL,
    tonnes DOUBLE NOT NULL,
    source_file TEXT,
    FOREIGN KEY (report_month_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
    FOREIGN KEY (destination_key) REFERENCES dim_destination(destination_key)
);

CREATE TABLE fact_production_quarterly (
    quarter_date_key INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    state_key INTEGER NOT NULL,
    release_month DATE,
    metric_group TEXT NOT NULL,
    unit TEXT NOT NULL,
    measure TEXT,
    animal TEXT,
    series_type TEXT,
    series_id TEXT,
    value DOUBLE NOT NULL,
    source_file TEXT,
    FOREIGN KEY (quarter_date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
    FOREIGN KEY (state_key) REFERENCES dim_state(state_key)
);

CREATE TABLE fact_market_quarterly (
    quarter_label TEXT NOT NULL,
    product_key INTEGER NOT NULL,
    exports_tonnes DOUBLE,
    production_tonnes DOUBLE,
    slaughter_value DOUBLE,
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key)
);

CREATE TABLE fact_forecast (
    forecast_year INTEGER NOT NULL,
    product_key INTEGER NOT NULL,
    target_metric TEXT NOT NULL,
    period_type TEXT NOT NULL,
    period_label TEXT NOT NULL,
    scenario TEXT NOT NULL,
    forecast_value DOUBLE NOT NULL,
    unit TEXT NOT NULL,
    model_name TEXT,
    model_detail TEXT,
    training_start TEXT,
    training_end TEXT,
    training_points INTEGER,
    residual_std DOUBLE,
    backtest_mape_pct DOUBLE,
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key)
);

CREATE TABLE fact_insights (
    insight_id TEXT PRIMARY KEY,
    product_key INTEGER,
    category TEXT NOT NULL,
    metric TEXT NOT NULL,
    period_label TEXT,
    comparison_period TEXT,
    value DOUBLE,
    comparison_value DOUBLE,
    change_value DOUBLE,
    change_pct DOUBLE,
    unit TEXT,
    direction TEXT,
    business_signal TEXT,
    recommendation TEXT,
    narrative TEXT,
    sort_order INTEGER,
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key)
);

