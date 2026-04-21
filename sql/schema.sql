PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_production;
DROP TABLE IF EXISTS fact_exports;
DROP TABLE IF EXISTS dim_product;
DROP TABLE IF EXISTS dim_state;
DROP TABLE IF EXISTS dim_destination;

CREATE TABLE dim_product (
    product_code TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    product_category TEXT
);

CREATE TABLE dim_state (
    state_name TEXT PRIMARY KEY,
    country_name TEXT NOT NULL DEFAULT 'Australia'
);

CREATE TABLE dim_destination (
    destination_name TEXT PRIMARY KEY
);

CREATE TABLE fact_production (
    production_id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_month TEXT NOT NULL,
    date TEXT NOT NULL,
    quarter TEXT NOT NULL,
    year INTEGER NOT NULL,
    product TEXT NOT NULL,
    metric_group TEXT NOT NULL,
    unit TEXT NOT NULL,
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

CREATE TABLE fact_exports (
    export_id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_month TEXT NOT NULL,
    report_month TEXT NOT NULL,
    destination TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    product TEXT NOT NULL,
    metric_group TEXT NOT NULL,
    unit TEXT NOT NULL,
    tonnes REAL NOT NULL,
    source_file TEXT NOT NULL,
    FOREIGN KEY (product) REFERENCES dim_product(product_code),
    FOREIGN KEY (destination) REFERENCES dim_destination(destination_name)
);

CREATE INDEX idx_fact_production_date_product_state
ON fact_production (date, product, state);

CREATE INDEX idx_fact_production_metric_group
ON fact_production (metric_group, unit);

CREATE INDEX idx_fact_exports_month_product_destination
ON fact_exports (report_month, product, destination);

CREATE INDEX idx_fact_exports_metric_group
ON fact_exports (metric_group, unit);
