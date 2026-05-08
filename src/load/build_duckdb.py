from __future__ import annotations

from pathlib import Path
from typing import Optional
import argparse

import duckdb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SQL_DIR = PROJECT_ROOT / "sql"
DEFAULT_DB_PATH = PROCESSED_DIR / "meat_market.duckdb"
DEFAULT_WINDOW_TOKEN = "2024_01_to_2025_12"
DEFAULT_FORECAST_YEAR = 2026


OPTIONAL_TABLE_COLUMNS = {
    "stg_insights": [
        "insight_id",
        "category",
        "metric",
        "product",
        "period",
        "comparison_period",
        "value",
        "comparison_value",
        "change_value",
        "change_pct",
        "unit",
        "direction",
        "business_signal",
        "recommendation",
        "narrative",
        "sort_order",
    ],
    "stg_forecast": [
        "forecast_year",
        "target_metric",
        "product",
        "period_type",
        "period",
        "scenario",
        "forecast_value",
        "unit",
        "model_name",
        "model_detail",
        "training_start",
        "training_end",
        "training_points",
        "residual_std",
        "backtest_mape_pct",
    ],
}


def processed_path(file_name: str, processed_dir: Path) -> Path:
    return processed_dir / file_name


def load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required processed CSV not found: {path}")
    return pd.read_csv(path)


def load_optional_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        print(f"Optional CSV not found, skipping: {path}")
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path)


def read_sql(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def product_name_sql() -> str:
    return """
        CASE product_code
            WHEN 'beef' THEN 'Beef'
            WHEN 'lamb' THEN 'Lamb'
            WHEN 'mutton' THEN 'Mutton'
            WHEN 'all_meat' THEN 'All Meat'
            ELSE REPLACE(product_code, '_', ' ')
        END
    """


def release_month_sql(alias: str) -> str:
    return f"""
        CAST(
            CASE
                WHEN {alias}.release_month IS NULL THEN NULL
                WHEN LENGTH(CAST({alias}.release_month AS VARCHAR)) = 7
                    THEN CAST({alias}.release_month AS VARCHAR) || '-01'
                ELSE CAST({alias}.release_month AS VARCHAR)
            END
            AS DATE
        )
    """


def create_dimensions(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        f"""
        INSERT INTO dim_product
        SELECT
            ROW_NUMBER() OVER (ORDER BY product_code) AS product_key,
            product_code,
            {product_name_sql()} AS product_name,
            CASE
                WHEN product_code IN ('beef', 'lamb') THEN 'core meat'
                ELSE 'supporting meat'
            END AS product_family
        FROM (
            SELECT DISTINCT product AS product_code FROM stg_exports
            UNION
            SELECT DISTINCT product AS product_code FROM stg_production
            UNION
            SELECT DISTINCT product AS product_code FROM stg_summary
            UNION
            SELECT DISTINCT product AS product_code FROM stg_forecast
            UNION
            SELECT DISTINCT product AS product_code FROM stg_insights
        )
        WHERE product_code IS NOT NULL;
        """
    )

    connection.execute(
        """
        INSERT INTO dim_destination
        SELECT
            ROW_NUMBER() OVER (ORDER BY destination) AS destination_key,
            destination AS destination_name,
            CASE
                WHEN destination ILIKE '%USA%' THEN 'North America'
                WHEN destination IN ('Japan', 'China', 'South Korea', 'Taiwan', 'Indonesia')
                    THEN 'North Asia and Southeast Asia'
                WHEN destination IN ('Dubai', 'Iran', 'Bahrain', 'Abu Dhabi')
                    THEN 'Middle East'
                ELSE 'Destination market'
            END AS region_group
        FROM (
            SELECT DISTINCT destination FROM stg_exports
        )
        WHERE destination IS NOT NULL;
        """
    )

    connection.execute(
        """
        INSERT INTO dim_state
        SELECT
            ROW_NUMBER() OVER (ORDER BY state) AS state_key,
            state AS state_name,
            'Australia' AS country_name
        FROM (
            SELECT DISTINCT state FROM stg_production
        )
        WHERE state IS NOT NULL;
        """
    )

    connection.execute(
        """
        INSERT INTO dim_date
        SELECT
            CAST(STRFTIME(date_value, '%Y%m%d') AS INTEGER) AS date_key,
            date_value,
            YEAR(date_value) AS year,
            MONTH(date_value) AS month_number,
            STRFTIME(date_value, '%Y-%m') AS month_label,
            QUARTER(date_value) AS quarter_number,
            CAST(YEAR(date_value) AS VARCHAR) || 'Q' || CAST(QUARTER(date_value) AS VARCHAR)
                AS quarter_label,
            'calendar' AS period_type
        FROM (
            SELECT DISTINCT
                CAST(report_month AS DATE) AS date_value
            FROM stg_exports
            WHERE report_month IS NOT NULL

            UNION

            SELECT DISTINCT
                CAST(date AS DATE) AS date_value
            FROM stg_production
            WHERE date IS NOT NULL
        )
        ORDER BY date_value;
        """
    )


def create_facts(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        f"""
        INSERT INTO fact_exports_monthly
        SELECT
            d.date_key AS report_month_key,
            p.product_key,
            dest.destination_key,
            {release_month_sql("e")} AS release_month,
            e.metric_name,
            e.metric_group,
            e.unit,
            CAST(e.tonnes AS DOUBLE) AS tonnes,
            e.source_file
        FROM stg_exports AS e
        JOIN dim_date AS d
            ON CAST(e.report_month AS DATE) = d.date_value
        JOIN dim_product AS p
            ON e.product = p.product_code
        JOIN dim_destination AS dest
            ON e.destination = dest.destination_name
        WHERE e.tonnes IS NOT NULL;
        """
    )

    connection.execute(
        f"""
        INSERT INTO fact_production_quarterly
        SELECT
            d.date_key AS quarter_date_key,
            p.product_key,
            s.state_key,
            {release_month_sql("prod")} AS release_month,
            prod.metric_group,
            prod.unit,
            prod.measure,
            prod.animal,
            prod.series_type,
            prod.series_id,
            CAST(prod.value AS DOUBLE) AS value,
            prod.source_file
        FROM stg_production AS prod
        JOIN dim_date AS d
            ON CAST(prod.date AS DATE) = d.date_value
        JOIN dim_product AS p
            ON prod.product = p.product_code
        JOIN dim_state AS s
            ON prod.state = s.state_name
        WHERE prod.value IS NOT NULL;
        """
    )

    connection.execute(
        """
        INSERT INTO fact_market_quarterly
        SELECT
            summary.quarter AS quarter_label,
            p.product_key,
            CAST(summary.exports_tonnes AS DOUBLE) AS exports_tonnes,
            CAST(summary.production_tonnes AS DOUBLE) AS production_tonnes,
            CAST(summary.slaughter_value AS DOUBLE) AS slaughter_value
        FROM stg_summary AS summary
        JOIN dim_product AS p
            ON summary.product = p.product_code;
        """
    )

    connection.execute(
        """
        INSERT INTO fact_forecast
        SELECT
            CAST(f.forecast_year AS INTEGER) AS forecast_year,
            p.product_key,
            f.target_metric,
            f.period_type,
            f.period AS period_label,
            f.scenario,
            CAST(f.forecast_value AS DOUBLE) AS forecast_value,
            f.unit,
            f.model_name,
            f.model_detail,
            f.training_start,
            f.training_end,
            CAST(f.training_points AS INTEGER) AS training_points,
            CAST(f.residual_std AS DOUBLE) AS residual_std,
            CAST(f.backtest_mape_pct AS DOUBLE) AS backtest_mape_pct
        FROM stg_forecast AS f
        JOIN dim_product AS p
            ON f.product = p.product_code
        WHERE f.forecast_value IS NOT NULL;
        """
    )

    connection.execute(
        """
        INSERT INTO fact_insights
        SELECT
            i.insight_id,
            p.product_key,
            i.category,
            i.metric,
            i.period AS period_label,
            i.comparison_period,
            CAST(i.value AS DOUBLE) AS value,
            CAST(i.comparison_value AS DOUBLE) AS comparison_value,
            CAST(i.change_value AS DOUBLE) AS change_value,
            CAST(i.change_pct AS DOUBLE) AS change_pct,
            i.unit,
            i.direction,
            i.business_signal,
            i.recommendation,
            i.narrative,
            CAST(i.sort_order AS INTEGER) AS sort_order
        FROM stg_insights AS i
        LEFT JOIN dim_product AS p
            ON i.product = p.product_code
        WHERE i.insight_id IS NOT NULL;
        """
    )


def build_duckdb(
    db_path: Path = DEFAULT_DB_PATH,
    processed_dir: Path = PROCESSED_DIR,
    window_token: str = DEFAULT_WINDOW_TOKEN,
    forecast_year: int = DEFAULT_FORECAST_YEAR,
    overwrite: bool = True,
) -> Path:
    """
    Build a DuckDB database from processed CSV outputs.
    """
    processed_dir = Path(processed_dir)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if overwrite and db_path.exists():
        db_path.unlink()

    exports = load_required_csv(
        processed_path(f"exports_clean_{window_token}.csv", processed_dir)
    )
    production = load_required_csv(
        processed_path(f"production_clean_latest_{window_token}.csv", processed_dir)
    )
    summary = load_required_csv(
        processed_path(f"market_quarterly_summary_{window_token}.csv", processed_dir)
    )
    insights = load_optional_csv(
        processed_path(f"market_insights_{window_token}.csv", processed_dir),
        OPTIONAL_TABLE_COLUMNS["stg_insights"],
    )
    forecast = load_optional_csv(
        processed_path(
            f"market_forecast_{window_token}_for_{forecast_year}.csv",
            processed_dir,
        ),
        OPTIONAL_TABLE_COLUMNS["stg_forecast"],
    )

    with duckdb.connect(str(db_path)) as connection:
        connection.execute(read_sql(SQL_DIR / "duckdb_schema.sql"))
        connection.register("stg_exports", exports)
        connection.register("stg_production", production)
        connection.register("stg_summary", summary)
        connection.register("stg_insights", insights)
        connection.register("stg_forecast", forecast)

        create_dimensions(connection)
        create_facts(connection)
        connection.execute(read_sql(SQL_DIR / "marts.sql"))

    print(f"Built DuckDB database: {db_path}")
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a DuckDB star-schema database from processed CSV outputs."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Output DuckDB database path.",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=PROCESSED_DIR,
        help="Directory containing processed CSV outputs.",
    )
    parser.add_argument(
        "--window-token",
        type=str,
        default=DEFAULT_WINDOW_TOKEN,
        help="File-name token such as 2024_01_to_2025_12.",
    )
    parser.add_argument(
        "--forecast-year",
        type=int,
        default=DEFAULT_FORECAST_YEAR,
        help="Forecast year token used in the processed forecast CSV file name.",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Do not delete an existing DuckDB file before building.",
    )
    args = parser.parse_args()

    build_duckdb(
        db_path=args.db_path,
        processed_dir=args.processed_dir,
        window_token=args.window_token,
        forecast_year=args.forecast_year,
        overwrite=not args.no_overwrite,
    )


if __name__ == "__main__":
    main()
