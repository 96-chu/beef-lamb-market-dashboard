from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from src.load.load_to_sqlite import DEFAULT_DB_PATH, build_sqlite


DEFAULT_ROW_LIMIT = 100
MAX_ROW_LIMIT = 500
MAX_SQL_LENGTH = 8_000

TABLE_DESCRIPTIONS = {
    "fact_exports": (
        "Monthly DAFF export flows by report month, destination, product, and metric. "
        "Use tonnes for export volume analysis."
    ),
    "fact_production": (
        "Quarterly ABS production and slaughter series by date, product, state, "
        "metric group, and unit."
    ),
    "market_quarterly_summary": (
        "Compact quarterly beef/lamb summary with exports_tonnes, production_tonnes, "
        "and slaughter_value."
    ),
    "market_insights": (
        "Precomputed business insights, recommendations, narratives, and period changes."
    ),
    "market_forecast": (
        "Forecast scenarios for export volume, production, and export share."
    ),
    "vw_latest_kpis": (
        "Latest monthly export and latest quarterly production KPI values for beef and lamb."
    ),
    "vw_quarterly_market": (
        "Quarterly summary view with product names and export_share_pct."
    ),
    "vw_top_destinations_annual": (
        "Top 10 annual export destinations by product and year."
    ),
    "vw_forecast_base_annual": (
        "Base annual forecast values by product and target metric."
    ),
    "vw_market_insights": (
        "Business insight view enriched with readable product names."
    ),
}

BUSINESS_GLOSSARY = [
    {
        "term": "exports_tonnes",
        "meaning": "Total exported volume measured in tonnes.",
    },
    {
        "term": "production_tonnes",
        "meaning": "Australia-level meat production measured in tonnes.",
    },
    {
        "term": "slaughter_value",
        "meaning": "ABS slaughter value in the source series unit.",
    },
    {
        "term": "export_share_pct",
        "meaning": "exports_tonnes divided by production_tonnes, expressed as a percentage.",
    },
    {
        "term": "beef/lamb",
        "meaning": "Core products for this dashboard. Mutton and all_meat are supporting export metrics.",
    },
]

JOIN_GUIDE = [
    "fact_exports.product -> dim_product.product_code",
    "fact_exports.destination -> dim_destination.destination_name",
    "fact_production.product -> dim_product.product_code",
    "fact_production.state -> dim_state.state_name",
    "market_quarterly_summary.product -> dim_product.product_code",
    "market_forecast.product -> dim_product.product_code",
    "market_insights.product -> dim_product.product_code",
]

READ_ONLY_PATTERN = re.compile(r"^\s*(select|with)\b", re.IGNORECASE | re.DOTALL)
BLOCKED_SQL_PATTERN = re.compile(
    r"\b("
    r"attach|alter|analyze|begin|commit|create|delete|detach|drop|insert|pragma|"
    r"reindex|replace|rollback|update|vacuum"
    r")\b",
    re.IGNORECASE,
)


class SQLToolError(ValueError):
    """Raised when a SQL tool request is unsafe or cannot be executed."""


def ensure_database(db_path: Path = DEFAULT_DB_PATH) -> Path:
    db_path = Path(db_path)
    if not db_path.exists():
        build_sqlite(db_path=db_path)
    return db_path


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def serialize_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def validate_read_only_sql(sql: str) -> str:
    query = sql.strip()
    if not query:
        raise SQLToolError("SQL query is empty.")
    if len(query) > MAX_SQL_LENGTH:
        raise SQLToolError(f"SQL query is too long. Limit is {MAX_SQL_LENGTH} characters.")
    if query.count(";") > 1 or (";" in query and not query.endswith(";")):
        raise SQLToolError("Only one SQL statement is allowed.")
    query = query.rstrip(";").strip()
    if not READ_ONLY_PATTERN.match(query):
        raise SQLToolError("Only SELECT or WITH read-only queries are allowed.")
    if BLOCKED_SQL_PATTERN.search(query):
        raise SQLToolError("Query contains a blocked SQL keyword.")
    return query


def authorizer(action: int, _arg1: str, _arg2: str, _db: str, _trigger: str) -> int:
    allowed_actions = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
    }
    recursive_action = getattr(sqlite3, "SQLITE_RECURSIVE", None)
    if recursive_action is not None:
        allowed_actions.add(recursive_action)
    if action in allowed_actions:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def get_schema(db_path: Path = DEFAULT_DB_PATH, include_samples: bool = False) -> dict[str, Any]:
    db_path = ensure_database(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        objects = connection.execute(
            """
            SELECT name, type
            FROM sqlite_master
            WHERE type IN ('table', 'view')
                AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name
            """
        ).fetchall()

        tables = []
        for obj in objects:
            name = obj["name"]
            columns = connection.execute(
                f"PRAGMA table_info({quote_identifier(name)})"
            ).fetchall()
            row_count = None
            if obj["type"] == "table":
                row_count = connection.execute(
                    f"SELECT COUNT(*) AS row_count FROM {quote_identifier(name)}"
                ).fetchone()["row_count"]

            table = {
                "name": name,
                "type": obj["type"],
                "description": TABLE_DESCRIPTIONS.get(name, ""),
                "row_count": row_count,
                "columns": [
                    {
                        "name": column["name"],
                        "type": column["type"],
                        "nullable": not bool(column["notnull"]),
                        "primary_key": bool(column["pk"]),
                    }
                    for column in columns
                ],
            }
            if include_samples and obj["type"] in {"table", "view"}:
                sample_rows = connection.execute(
                    f"SELECT * FROM {quote_identifier(name)} LIMIT 3"
                ).fetchall()
                table["sample_rows"] = [dict(row) for row in sample_rows]
            tables.append(table)

    return {
        "database_path": str(db_path),
        "dialect": "SQLite",
        "tables": tables,
        "join_guide": JOIN_GUIDE,
        "business_glossary": BUSINESS_GLOSSARY,
        "query_rules": [
            "Use read-only SELECT or WITH queries only.",
            "Prefer the vw_* views for common KPI, quarterly, forecast, and insight questions.",
            "Use fact_exports for monthly destination export analysis.",
            "Use fact_production with state = 'Australia' for national production analysis.",
            f"Default API row limit is {DEFAULT_ROW_LIMIT}; ask for aggregated results first.",
        ],
    }


def run_sql_query(
    sql: str,
    db_path: Path = DEFAULT_DB_PATH,
    row_limit: int = DEFAULT_ROW_LIMIT,
) -> dict[str, Any]:
    db_path = ensure_database(db_path)
    query = validate_read_only_sql(sql)
    limit = max(1, min(int(row_limit), MAX_ROW_LIMIT))
    started = time.perf_counter()

    deadline = time.perf_counter() + 3.0

    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.set_authorizer(authorizer)
        connection.set_progress_handler(
            lambda: 1 if time.perf_counter() > deadline else 0,
            250_000,
        )
        cursor = connection.execute(query)
        if cursor.description is None:
            raise SQLToolError("Query did not return a result set.")

        columns = [column[0] for column in cursor.description]
        fetched_rows = cursor.fetchmany(limit + 1)
        truncated = len(fetched_rows) > limit
        rows = [
            {column: serialize_value(row[column]) for column in columns}
            for row in fetched_rows[:limit]
        ]

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "sql": query,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "limit": limit,
        "elapsed_ms": elapsed_ms,
    }
