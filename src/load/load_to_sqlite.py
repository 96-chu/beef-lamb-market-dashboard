from pathlib import Path
from typing import Optional
import argparse
import sqlite3

import pandas as pd


# Define project level paths.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SQL_DIR = PROJECT_ROOT / "sql"
SCHEMA_PATH = SQL_DIR / "schema.sql"
DEFAULT_DB_PATH = PROCESSED_DIR / "meat_market.db"

# Map product codes to readable names for the product dimension.
PRODUCT_NAME_MAP = {
    "beef": "Beef",
    "lamb": "Lamb",
    "mutton": "Mutton",
    "all_meat": "All Meat",
}


def get_processed_file_paths(month: Optional[str] = None) -> tuple[Path, Path]:
    """
    Return the expected cleaned CSV file paths.

    If a month is provided, load month specific outputs.
    If month is None, load the consolidated all month outputs.
    """
    if month:
        month_token = month.replace("-", "_")
        production_path = PROCESSED_DIR / f"production_clean_{month_token}.csv"
        exports_path = PROCESSED_DIR / f"exports_clean_{month_token}.csv"
    else:
        production_path = PROCESSED_DIR / "production_clean_all.csv"
        exports_path = PROCESSED_DIR / "exports_clean_all.csv"

    if not production_path.exists():
        raise FileNotFoundError(f"Production file not found: {production_path}")

    if not exports_path.exists():
        raise FileNotFoundError(f"Export file not found: {exports_path}")

    return production_path, exports_path


def read_schema(schema_path: Path) -> str:
    """
    Read the SQL schema file from disk.
    """
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return schema_path.read_text(encoding="utf-8")


def normalize_production_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply lightweight type normalization to the cleaned production DataFrame.

    This step ensures date and numeric fields are ready for SQLite loading.
    """
    normalized = df.copy()

    normalized["date"] = pd.to_datetime(
        normalized["date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    normalized["year"] = pd.to_numeric(
        normalized["year"], errors="coerce"
    ).astype("Int64")

    normalized["value"] = pd.to_numeric(
        normalized["value"], errors="coerce"
    )

    normalized = normalized.dropna(
        subset=["date", "year", "product", "metric_group", "unit", "state", "value"]
    ).copy()

    normalized["year"] = normalized["year"].astype(int)

    return normalized


def normalize_exports_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply lightweight type normalization to the cleaned export DataFrame.

    This step ensures date and numeric fields are ready for SQLite loading.
    """
    normalized = df.copy()

    normalized["report_month"] = pd.to_datetime(
        normalized["report_month"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    normalized["tonnes"] = pd.to_numeric(
        normalized["tonnes"], errors="coerce"
    )

    normalized = normalized.dropna(
        subset=[
            "report_month",
            "destination",
            "metric_name",
            "product",
            "metric_group",
            "unit",
            "tonnes",
        ]
    ).copy()

    return normalized


def build_product_dimension(
    production_df: pd.DataFrame,
    exports_df: pd.DataFrame,
) -> list[tuple[str, str, str]]:
    """
    Build rows for the product dimension from both cleaned datasets.
    """
    product_codes = set(production_df["product"].dropna().unique()).union(
        set(exports_df["product"].dropna().unique())
    )

    rows = []
    for product_code in sorted(product_codes):
        product_name = PRODUCT_NAME_MAP.get(
            product_code,
            product_code.replace("_", " ").title(),
        )
        rows.append((product_code, product_name, "meat"))

    return rows


def build_state_dimension(production_df: pd.DataFrame) -> list[tuple[str, str]]:
    """
    Build rows for the state dimension from the production dataset.
    """
    states = sorted(production_df["state"].dropna().unique())
    return [(state, "Australia") for state in states]


def build_destination_dimension(exports_df: pd.DataFrame) -> list[tuple[str]]:
    """
    Build rows for the destination dimension from the export dataset.
    """
    destinations = sorted(exports_df["destination"].dropna().unique())
    return [(destination,) for destination in destinations]


def execute_schema(connection: sqlite3.Connection, schema_sql: str) -> None:
    """
    Execute the full schema SQL script.

    The schema drops old tables and recreates fresh tables and indexes.
    """
    cursor = connection.cursor()
    cursor.executescript(schema_sql)
    connection.commit()


def load_dimensions(
    connection: sqlite3.Connection,
    production_df: pd.DataFrame,
    exports_df: pd.DataFrame,
) -> None:
    """
    Load dimension tables before loading fact tables.
    """
    product_rows = build_product_dimension(production_df, exports_df)
    state_rows = build_state_dimension(production_df)
    destination_rows = build_destination_dimension(exports_df)

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
        product_rows,
    )

    cursor.executemany(
        """
        INSERT OR REPLACE INTO dim_state (
            state_name,
            country_name
        )
        VALUES (?, ?)
        """,
        state_rows,
    )

    cursor.executemany(
        """
        INSERT OR REPLACE INTO dim_destination (
            destination_name
        )
        VALUES (?)
        """,
        destination_rows,
    )

    connection.commit()


def load_facts(
    connection: sqlite3.Connection,
    production_df: pd.DataFrame,
    exports_df: pd.DataFrame,
) -> None:
    """
    Load fact tables into SQLite.

    The schema already exists at this point, so pandas appends rows
    into the predefined tables.
    """
    production_columns = [
        "folder_month",
        "date",
        "quarter",
        "year",
        "product",
        "metric_group",
        "unit",
        "measure",
        "animal",
        "state",
        "series_type",
        "series_id",
        "value",
        "source_file",
    ]

    exports_columns = [
        "folder_month",
        "report_month",
        "destination",
        "metric_name",
        "product",
        "metric_group",
        "unit",
        "tonnes",
        "source_file",
    ]

    production_df[production_columns].to_sql(
        "fact_production",
        connection,
        if_exists="append",
        index=False,
    )

    exports_df[exports_columns].to_sql(
        "fact_exports",
        connection,
        if_exists="append",
        index=False,
    )

    connection.commit()


def main() -> None:
    """
    Load cleaned CSV files into a local SQLite database.

    Usage examples:
    python src/load/load_to_sqlite.py --month 2025-12
    python src/load/load_to_sqlite.py
    """
    parser = argparse.ArgumentParser(
        description="Load cleaned production and export CSV files into SQLite."
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="Month folder token such as 2025-12",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DEFAULT_DB_PATH),
        help="SQLite database output path",
    )
    args = parser.parse_args()

    production_path, exports_path = get_processed_file_paths(month=args.month)

    production_df = pd.read_csv(production_path)
    exports_df = pd.read_csv(exports_path)

    production_df = normalize_production_df(production_df)
    exports_df = normalize_exports_df(exports_df)

    schema_sql = read_schema(SCHEMA_PATH)

    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        execute_schema(connection, schema_sql)
        load_dimensions(connection, production_df, exports_df)
        load_facts(connection, production_df, exports_df)

    print(f"Loaded SQLite database to: {db_path}")


if __name__ == "__main__":
    main()