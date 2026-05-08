from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_PATH = SQL_DIR / "schema.sql"
DEFAULT_DB_PATH = PROCESSED_DIR / "meat_market.db"
DEFAULT_WINDOW_TOKEN = "2024_01_to_2025_12"
DEFAULT_FORECAST_YEAR = 2026

PRODUCT_NAME_MAP = {
    "beef": "Beef",
    "lamb": "Lamb",
    "mutton": "Mutton",
    "all_meat": "All Meat",
}

OPTIONAL_TABLE_COLUMNS = {
    "market_insights": [
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
    "market_forecast": [
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

EXPORT_COLUMNS = [
    "release_month",
    "report_month",
    "year",
    "quarter",
    "destination",
    "metric_name",
    "product",
    "metric_group",
    "unit",
    "period_type",
    "report_scope",
    "is_cumulative",
    "tonnes",
    "source_file",
]

PRODUCTION_COLUMNS = [
    "release_month",
    "date",
    "quarter",
    "quarter_start_date",
    "quarter_end_date",
    "year",
    "product",
    "metric_group",
    "unit",
    "period_type",
    "measure",
    "animal",
    "state",
    "series_type",
    "series_id",
    "value",
    "source_file",
]

SUMMARY_COLUMNS = [
    "quarter",
    "product",
    "exports_tonnes",
    "production_tonnes",
    "slaughter_value",
]


def processed_path(file_name: str, processed_dir: Path = PROCESSED_DIR) -> Path:
    return Path(processed_dir) / file_name


def read_schema(schema_path: Path = SCHEMA_PATH) -> str:
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return schema_path.read_text(encoding="utf-8")


def load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required processed CSV not found: {path}")
    return pd.read_csv(path)


def load_optional_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        print(f"Optional CSV not found, loading empty table: {path}")
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path)


def normalize_date_column(df: pd.DataFrame, column: str) -> None:
    if column in df.columns:
        df[column] = pd.to_datetime(df[column], errors="coerce").dt.strftime("%Y-%m-%d")


def normalize_exports_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalize_date_column(normalized, "report_month")
    normalized["year"] = pd.to_numeric(normalized["year"], errors="coerce").astype("Int64")
    normalized["is_cumulative"] = (
        pd.to_numeric(normalized["is_cumulative"], errors="coerce").fillna(0).astype(int)
    )
    normalized["tonnes"] = pd.to_numeric(normalized["tonnes"], errors="coerce")
    normalized = normalized.dropna(
        subset=[
            "release_month",
            "report_month",
            "year",
            "quarter",
            "destination",
            "metric_name",
            "product",
            "metric_group",
            "unit",
            "period_type",
            "report_scope",
            "tonnes",
            "source_file",
        ]
    ).copy()
    normalized["year"] = normalized["year"].astype(int)
    return normalized[EXPORT_COLUMNS]


def normalize_production_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in ["date", "quarter_start_date", "quarter_end_date"]:
        normalize_date_column(normalized, column)
    normalized["year"] = pd.to_numeric(normalized["year"], errors="coerce").astype("Int64")
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    normalized = normalized.dropna(
        subset=[
            "release_month",
            "date",
            "quarter",
            "year",
            "product",
            "metric_group",
            "unit",
            "period_type",
            "state",
            "value",
            "source_file",
        ]
    ).copy()
    normalized["year"] = normalized["year"].astype(int)
    return normalized[PRODUCTION_COLUMNS]


def normalize_summary_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in ["exports_tonnes", "production_tonnes", "slaughter_value"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=["quarter", "product"]).copy()
    return normalized[SUMMARY_COLUMNS]


def normalize_insights_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in [
        "value",
        "comparison_value",
        "change_value",
        "change_pct",
        "sort_order",
    ]:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=["insight_id", "category", "metric"]).copy()
    return normalized[OPTIONAL_TABLE_COLUMNS["market_insights"]]


def normalize_forecast_df(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in [
        "forecast_year",
        "forecast_value",
        "training_points",
        "residual_std",
        "backtest_mape_pct",
    ]:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(
        subset=[
            "forecast_year",
            "target_metric",
            "product",
            "period_type",
            "period",
            "scenario",
        ]
    ).copy()
    normalized["forecast_year"] = normalized["forecast_year"].astype(int)
    if "training_points" in normalized.columns:
        normalized["training_points"] = normalized["training_points"].astype("Int64")
    return normalized[OPTIONAL_TABLE_COLUMNS["market_forecast"]]


def build_product_dimension(*frames: pd.DataFrame) -> list[tuple[str, str, str]]:
    product_codes: set[str] = set()
    for frame in frames:
        if "product" in frame.columns:
            product_codes.update(frame["product"].dropna().astype(str).unique())

    rows = []
    for product_code in sorted(product_codes):
        product_name = PRODUCT_NAME_MAP.get(
            product_code,
            product_code.replace("_", " ").title(),
        )
        rows.append((product_code, product_name, "meat"))
    return rows


def infer_region_group(destination: str) -> str:
    if "USA" in destination or destination in {"Canada East", "Canada West"}:
        return "North America"
    if destination in {"Japan", "China", "South Korea", "Taiwan", "Hong Kong"}:
        return "North Asia"
    if destination in {
        "Indonesia",
        "Malaysia",
        "Philippines",
        "Singapore",
        "Thailand",
    }:
        return "Southeast Asia"
    if destination in {
        "Abu Dhabi",
        "Bahrain",
        "Dubai",
        "Iran",
        "Jordan",
        "Kuwait",
        "Qatar",
        "Saudi Arabia",
    }:
        return "Middle East"
    if destination in {"United Kingdom", "Austria"}:
        return "Europe"
    return "Destination market"


def build_destination_dimension(exports_df: pd.DataFrame) -> list[tuple[str, str]]:
    destinations = sorted(exports_df["destination"].dropna().astype(str).unique())
    return [(destination, infer_region_group(destination)) for destination in destinations]


def build_state_dimension(production_df: pd.DataFrame) -> list[tuple[str, str]]:
    states = sorted(production_df["state"].dropna().astype(str).unique())
    return [(state, "Australia") for state in states]


def execute_schema(connection: sqlite3.Connection, schema_sql: str) -> None:
    connection.executescript(schema_sql)
    connection.commit()


def load_dimensions(
    connection: sqlite3.Connection,
    exports: pd.DataFrame,
    production: pd.DataFrame,
    summary: pd.DataFrame,
    insights: pd.DataFrame,
    forecast: pd.DataFrame,
) -> None:
    cursor = connection.cursor()
    cursor.executemany(
        """
        INSERT OR REPLACE INTO dim_product (
            product_code,
            product_name,
            product_category
        )
        VALUES (?, ?, ?)
        """,
        build_product_dimension(exports, production, summary, insights, forecast),
    )
    cursor.executemany(
        """
        INSERT OR REPLACE INTO dim_destination (
            destination_name,
            region_group
        )
        VALUES (?, ?)
        """,
        build_destination_dimension(exports),
    )
    cursor.executemany(
        """
        INSERT OR REPLACE INTO dim_state (
            state_name,
            country_name
        )
        VALUES (?, ?)
        """,
        build_state_dimension(production),
    )
    connection.commit()


def to_sql_records(df: pd.DataFrame, table_name: str, connection: sqlite3.Connection) -> None:
    clean = df.where(pd.notna(df), None)
    clean.to_sql(table_name, connection, if_exists="append", index=False)


def load_facts_and_marts(
    connection: sqlite3.Connection,
    exports: pd.DataFrame,
    production: pd.DataFrame,
    summary: pd.DataFrame,
    insights: pd.DataFrame,
    forecast: pd.DataFrame,
) -> None:
    to_sql_records(exports, "fact_exports", connection)
    to_sql_records(production, "fact_production", connection)
    to_sql_records(summary, "market_quarterly_summary", connection)
    to_sql_records(insights, "market_insights", connection)
    to_sql_records(forecast, "market_forecast", connection)
    connection.commit()


def build_sqlite(
    db_path: Path = DEFAULT_DB_PATH,
    processed_dir: Path = PROCESSED_DIR,
    window_token: str = DEFAULT_WINDOW_TOKEN,
    forecast_year: int = DEFAULT_FORECAST_YEAR,
) -> Path:
    processed_dir = Path(processed_dir)
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    exports = normalize_exports_df(
        load_required_csv(processed_path(f"exports_clean_{window_token}.csv", processed_dir))
    )
    production = normalize_production_df(
        load_required_csv(
            processed_path(f"production_clean_latest_{window_token}.csv", processed_dir)
        )
    )
    summary = normalize_summary_df(
        load_required_csv(
            processed_path(f"market_quarterly_summary_{window_token}.csv", processed_dir)
        )
    )
    insights = normalize_insights_df(
        load_optional_csv(
            processed_path(f"market_insights_{window_token}.csv", processed_dir),
            OPTIONAL_TABLE_COLUMNS["market_insights"],
        )
    )
    forecast = normalize_forecast_df(
        load_optional_csv(
            processed_path(
                f"market_forecast_{window_token}_for_{forecast_year}.csv",
                processed_dir,
            ),
            OPTIONAL_TABLE_COLUMNS["market_forecast"],
        )
    )

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        execute_schema(connection, read_schema())
        load_dimensions(connection, exports, production, summary, insights, forecast)
        load_facts_and_marts(connection, exports, production, summary, insights, forecast)

    print(f"Loaded SQLite database to: {db_path}")
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load processed beef and lamb market outputs into SQLite."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="SQLite database output path.",
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
    args = parser.parse_args()

    build_sqlite(
        db_path=args.db_path,
        processed_dir=args.processed_dir,
        window_token=args.window_token,
        forecast_year=args.forecast_year,
    )


if __name__ == "__main__":
    main()
