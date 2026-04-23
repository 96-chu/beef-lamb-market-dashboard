-- Check available tables.
SELECT name
FROM sqlite_master
WHERE type = 'table'
ORDER BY name;

-- Check row counts for each fact table.
SELECT COUNT(*) AS production_rows
FROM fact_production;

SELECT COUNT(*) AS export_rows
FROM fact_exports;

-- Check product coverage in production data.
SELECT
    product,
    metric_group,
    unit,
    COUNT(*) AS row_count,
    MIN(date) AS min_date,
    MAX(date) AS max_date
FROM fact_production
GROUP BY product, metric_group, unit
ORDER BY product, metric_group, unit;

-- Check product coverage in export data.
SELECT
    product,
    metric_group,
    unit,
    COUNT(*) AS row_count,
    MIN(report_month) AS min_report_month,
    MAX(report_month) AS max_report_month
FROM fact_exports
GROUP BY product, metric_group, unit
ORDER BY product, metric_group, unit;

-- Check distinct states in production data.
SELECT DISTINCT state
FROM fact_production
ORDER BY state;

-- Check distinct destinations in export data.
SELECT DISTINCT destination
FROM fact_exports
ORDER BY destination;

-- Check production totals by state and product.
SELECT
    state,
    product,
    metric_group,
    unit,
    ROUND(SUM(value), 2) AS total_value
FROM fact_production
GROUP BY state, product, metric_group, unit
ORDER BY state, product, metric_group;

-- Check export totals by destination and product.
SELECT
    destination,
    product,
    ROUND(SUM(tonnes), 2) AS total_tonnes
FROM fact_exports
GROUP BY destination, product
ORDER BY total_tonnes DESC
LIMIT 20;

-- Check for duplicated production records.
SELECT
    date,
    product,
    metric_group,
    state,
    series_id,
    COUNT(*) AS duplicate_count
FROM fact_production
GROUP BY date, product, metric_group, state, series_id
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- Check for duplicated export records.
SELECT
    report_month,
    destination,
    metric_name,
    COUNT(*) AS duplicate_count
FROM fact_exports
GROUP BY report_month, destination, metric_name
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- Quick production preview.
SELECT *
FROM fact_production
ORDER BY date, product, state
LIMIT 20;

-- Quick export preview.
SELECT *
FROM fact_exports
ORDER BY report_month, product, destination
LIMIT 20;