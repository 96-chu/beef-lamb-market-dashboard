from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.build_forecast import build_forecast_from_frames
from src.build_insights import build_insights_from_frames


@dataclass
class ReportRequest:
    """Input settings used by the upload page or future API route."""

    forecast_year: Optional[int] = None
    scenario_pct: float = 0.10


def frame_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame into JSON-friendly records."""
    clean = df.where(pd.notna(df), None)
    return json.loads(clean.to_json(orient="records"))


def summarize_forecast(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Create a compact annual base-scenario table for a report header."""
    subset = forecasts[
        forecasts["scenario"].eq("base")
        & forecasts["period_type"].eq("annual")
        & forecasts["target_metric"].isin(
            ["exports_tonnes", "production_tonnes", "export_share_pct"]
        )
    ].copy()

    if subset.empty:
        return pd.DataFrame()

    summary = subset.pivot_table(
        index=["forecast_year", "product"],
        columns="target_metric",
        values="forecast_value",
        aggfunc="first",
    ).reset_index()
    summary.columns.name = None
    return summary.sort_values(["forecast_year", "product"]).reset_index(drop=True)


def build_markdown_report(
    insights: pd.DataFrame,
    forecasts: pd.DataFrame,
) -> str:
    """Build a concise business report from service outputs."""
    lines = [
        "# Beef & Lamb Market Report",
        "",
        "## Executive Signals",
    ]

    for _, row in insights.head(6).iterrows():
        lines.append(f"- **{row['product'].title()}**: {row['business_signal']}")

    forecast_summary = summarize_forecast(forecasts)
    if not forecast_summary.empty:
        lines.extend(["", "## Base Forecast"])
        for _, row in forecast_summary.iterrows():
            exports = row.get("exports_tonnes")
            production = row.get("production_tonnes")
            share = row.get("export_share_pct")
            lines.append(
                "- "
                f"{int(row['forecast_year'])} {row['product'].title()}: "
                f"exports {exports:,.0f} tonnes, "
                f"production {production:,.0f} tonnes, "
                f"export share {share:.1f}%."
            )

    lines.extend(
        [
            "",
            "## Commercial Interpretation",
            "- Growth markets should be reviewed against production capacity, not only export demand.",
            "- Declining destinations should be separated into demand softness, channel shift, or allocation change.",
            "- Forecast scenarios should be used as planning bands rather than point promises.",
            "- Supply chain, seasonal production, destination concentration, and climate-exposed supply should be monitored together.",
        ]
    )
    return "\n".join(lines)


def generate_market_report(
    exports: pd.DataFrame,
    summary: pd.DataFrame,
    request: Optional[ReportRequest] = None,
) -> dict:
    """
    Generate insight, forecast, and report outputs from uploaded data.

    The return value is intentionally plain dictionaries/lists so it can be
    returned by FastAPI later or consumed directly by Streamlit now.
    """
    request = request or ReportRequest()
    insights = build_insights_from_frames(exports, summary)
    forecasts = build_forecast_from_frames(
        exports,
        summary,
        forecast_year=request.forecast_year,
        scenario_pct=request.scenario_pct,
    )
    forecast_summary = summarize_forecast(forecasts)

    return {
        "generated_at_utc": pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "forecast_year": int(forecasts["forecast_year"].dropna().max()),
        "scenario_pct": request.scenario_pct,
        "report_markdown": build_markdown_report(insights, forecasts),
        "insights": frame_to_records(insights),
        "forecasts": frame_to_records(forecasts),
        "forecast_summary": frame_to_records(forecast_summary),
    }
