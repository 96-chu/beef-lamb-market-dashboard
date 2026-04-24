from __future__ import annotations

from pathlib import Path
from datetime import datetime, UTC
from typing import Optional
import argparse
import json
import shutil

import pandas as pd

from build_forecast import build_forecast
from build_insights import build_insights


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
DASHBOARD_DATA_DIR = DASHBOARD_DIR / "data"
DASHBOARD_REPORTS_DIR = DASHBOARD_DIR / "assets" / "reports"
REPORTS_DIR = PROJECT_ROOT / "reports" / "charts"


def slugify(token: str) -> str:
    return token.replace("-", "_")


def build_run_label(start_release_month: str, end_release_month: str) -> str:
    return f"{slugify(start_release_month)}_to_{slugify(end_release_month)}"


def load_inputs(run_label: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(PROCESSED_DIR / f"market_quarterly_summary_{run_label}.csv")
    exports = pd.read_csv(PROCESSED_DIR / f"exports_quarterly_{run_label}.csv")
    production = pd.read_csv(PROCESSED_DIR / f"production_clean_latest_{run_label}.csv")
    return summary, exports, production


def series_records(df: pd.DataFrame, x_col: str, series_col: str, value_col: str) -> list[dict]:
    pivot = (
        df.pivot(index=x_col, columns=series_col, values=value_col)
        .fillna(0)
        .sort_index()
    )
    records: list[dict] = []
    for idx, row in pivot.iterrows():
        item = {"label": idx}
        for col, val in row.items():
            item[str(col)] = round(float(val), 2)
        records.append(item)
    return records


def safe_float(value: object, digits: int = 2) -> float | None:
    if pd.isna(value):
        return None
    return round(float(value), digits)


def format_tonnes(value: float | None) -> str:
    if value is None:
        return "not available"
    return f"{value:,.0f} tonnes"


def format_pct(value: float | None) -> str:
    if value is None:
        return "not available"
    return f"{value:.1f}%"


def format_change(value: float | None, unit: str) -> str:
    if value is None:
        return "not available"
    if unit == "percentage_points":
        return f"{value:+.1f} pts"
    if unit == "percent":
        return f"{value:+.1f}%"
    if unit == "tonnes":
        return f"{value:+,.0f} tonnes"
    return f"{value:+,.2f}"


def metric_label(metric: str) -> str:
    labels = {
        "exports_yoy": "Export growth",
        "production_yoy": "Production growth",
        "export_share_of_production": "Export share of production",
        "top4_destination_share": "Destination concentration",
        "destination_yoy_gain": "Destination gain",
        "destination_yoy_decline": "Destination decline",
        "export_mix_share": "Product mix shift",
        "exports_tonnes": "Exports",
        "production_tonnes": "Production",
        "export_share_pct": "Export share",
    }
    return labels.get(metric, metric.replace("_", " ").title())


def product_label(product: str) -> str:
    return product.replace("_", " ").title()


def load_or_build_insights(
    run_label: str,
    start_release_month: str,
    end_release_month: str,
) -> pd.DataFrame:
    path = PROCESSED_DIR / f"market_insights_{run_label}.csv"
    if not path.exists():
        build_insights(
            start_release_month=start_release_month,
            end_release_month=end_release_month,
        )
    return pd.read_csv(path)


def load_or_build_forecast(
    run_label: str,
    start_release_month: str,
    end_release_month: str,
    forecast_year: int,
) -> pd.DataFrame:
    path = PROCESSED_DIR / f"market_forecast_{run_label}_for_{forecast_year}.csv"
    if not path.exists():
        build_forecast(
            start_release_month=start_release_month,
            end_release_month=end_release_month,
            forecast_year=forecast_year,
        )
    return pd.read_csv(path)


def row_to_insight_card(row: pd.Series) -> dict:
    value = safe_float(row.get("value"))
    change_value = safe_float(row.get("change_value"))
    change_pct = safe_float(row.get("change_pct"))
    unit = str(row.get("unit"))

    if unit == "tonnes":
        value_label = format_tonnes(value)
    elif unit == "percent":
        value_label = format_pct(value)
    elif unit == "percentage_points":
        value_label = f"{value:.1f}%" if value is not None else "not available"
    else:
        value_label = str(value)

    return {
        "title": f"{product_label(str(row.get('product')))} | {metric_label(str(row.get('metric')))}",
        "category": str(row.get("category")).replace("_", " ").title(),
        "period": str(row.get("period")),
        "direction": str(row.get("direction")),
        "valueLabel": value_label,
        "changeLabel": (
            format_pct(change_pct)
            if change_pct is not None
            else format_change(change_value, unit)
        ),
        "businessSignal": str(row.get("business_signal")),
        "recommendation": str(row.get("recommendation")),
        "narrative": str(row.get("narrative")),
    }


def annual_base_forecast_cards(forecast: pd.DataFrame) -> list[dict]:
    annual_base = forecast[
        (forecast["period_type"] == "annual")
        & (forecast["scenario"] == "base")
        & (forecast["target_metric"].isin(["exports_tonnes", "production_tonnes", "export_share_pct"]))
    ].copy()
    metric_order = {
        "exports_tonnes": 1,
        "production_tonnes": 2,
        "export_share_pct": 3,
    }
    annual_base["_metric_order"] = annual_base["target_metric"].map(metric_order)
    annual_base = annual_base.sort_values(["product", "_metric_order"])

    cards = []
    for _, row in annual_base.iterrows():
        value = safe_float(row["forecast_value"])
        unit = str(row["unit"])
        if unit == "tonnes":
            value_label = format_tonnes(value)
        elif unit == "percent":
            value_label = format_pct(value)
        else:
            value_label = str(value)

        cards.append(
            {
                "label": f"{product_label(str(row['product']))} {metric_label(str(row['target_metric']))}",
                "value": value,
                "valueLabel": value_label,
                "unit": unit,
                "period": str(row["period"]),
                "targetMetric": str(row["target_metric"]),
                "product": str(row["product"]),
            }
        )
    return cards


def annual_scenario_summary(forecast: pd.DataFrame) -> list[dict]:
    annual = forecast[forecast["period_type"] == "annual"].copy()
    records = []
    for product in ["beef", "lamb"]:
        product_rows = annual[annual["product"] == product]
        exports = product_rows[product_rows["target_metric"] == "exports_tonnes"]
        production = product_rows[product_rows["target_metric"] == "production_tonnes"]
        export_share = product_rows[product_rows["target_metric"] == "export_share_pct"]

        def value_for(rows: pd.DataFrame, scenario: str) -> float | None:
            subset = rows[rows["scenario"] == scenario]
            if subset.empty:
                return None
            return safe_float(subset.iloc[0]["forecast_value"])

        records.append(
            {
                "product": product,
                "label": product_label(product),
                "exports": {
                    "conservative": value_for(exports, "conservative"),
                    "base": value_for(exports, "base"),
                    "high": value_for(exports, "high"),
                },
                "productionBase": value_for(production, "base"),
                "exportShare": {
                    "conservative": value_for(export_share, "conservative"),
                    "base": value_for(export_share, "base"),
                    "high": value_for(export_share, "high"),
                },
            }
        )
    return records


def build_business_report(
    insights: pd.DataFrame,
    forecast: pd.DataFrame,
    export_month_start: str,
    export_month_end: str,
    forecast_year: int,
) -> dict:
    insights = insights.sort_values("sort_order").copy()
    key_metrics = [
        "exports_yoy",
        "production_yoy",
        "export_share_of_production",
        "top4_destination_share",
        "destination_yoy_gain",
        "destination_yoy_decline",
        "export_mix_share",
    ]
    key_findings = [
        row_to_insight_card(row)
        for _, row in insights[insights["metric"].isin(key_metrics)].head(12).iterrows()
    ]

    annual_cards = annual_base_forecast_cards(forecast)
    scenario_summary = annual_scenario_summary(forecast)

    beef_export = next(
        (item for item in annual_cards if item["product"] == "beef" and item["targetMetric"] == "exports_tonnes"),
        None,
    )
    lamb_export = next(
        (item for item in annual_cards if item["product"] == "lamb" and item["targetMetric"] == "exports_tonnes"),
        None,
    )
    beef_share = next(
        (item for item in annual_cards if item["product"] == "beef" and item["targetMetric"] == "export_share_pct"),
        None,
    )
    lamb_share = next(
        (item for item in annual_cards if item["product"] == "lamb" and item["targetMetric"] == "export_share_pct"),
        None,
    )

    executive_summary = [
        "Beef is the clearer growth engine, with export expansion outpacing production growth in the latest year-on-year view.",
        "Lamb needs portfolio-level interpretation: total exports softened, but export share of production stayed elevated because supply also declined.",
        "Destination exposure is a central commercial risk, especially for beef where the top four markets account for most export volume.",
        (
            f"The base forecast points to {beef_export['valueLabel']} of beef exports "
            f"and {lamb_export['valueLabel']} of lamb exports in {forecast_year}."
        )
        if beef_export and lamb_export
        else "The forecast layer provides a base outlook and scenario bands for the next reporting year.",
        (
            f"Base export-share pressure is estimated at {beef_share['valueLabel']} for beef "
            f"and {lamb_share['valueLabel']} for lamb in {forecast_year}."
        )
        if beef_share and lamb_share
        else "Export share of production is used as a pressure indicator for supply-demand balance.",
    ]

    impact_factors = [
        {
            "factor": "Climate and environmental conditions",
            "pressure": "Supply volatility",
            "businessImpact": (
                "Rainfall, pasture availability, heat stress, and water constraints can change herd or flock turnoff, carcass weights, and production timing."
            ),
            "forecastUse": "Use the conservative production case when seasonal conditions reduce supply confidence.",
            "watchMetrics": ["Rainfall outlook", "Pasture growth", "Livestock weights", "Water availability"],
        },
        {
            "factor": "Feed and input costs",
            "pressure": "Margin and production response",
            "businessImpact": (
                "Feed, energy, and on-farm operating costs influence finishing decisions and can shift the volume available for export channels."
            ),
            "forecastUse": "Stress test the base case if input costs rise faster than export prices.",
            "watchMetrics": ["Feed grain prices", "Energy costs", "Farmgate margins", "Processor margins"],
        },
        {
            "factor": "Processing and cold-chain capacity",
            "pressure": "Throughput constraint",
            "businessImpact": (
                "Labour availability, plant throughput, refrigeration, and container capacity can limit how quickly production converts into export shipments."
            ),
            "forecastUse": "Treat high export scenarios as capacity-dependent rather than purely demand-driven.",
            "watchMetrics": ["Plant utilisation", "Labour availability", "Cold storage capacity", "Container availability"],
        },
        {
            "factor": "Freight, ports, and shipping reliability",
            "pressure": "Service-level risk",
            "businessImpact": (
                "Port delays, freight cost changes, and shipping schedule reliability can affect delivery performance in premium destination markets."
            ),
            "forecastUse": "Apply scenario bands to destination exposure when logistics reliability weakens.",
            "watchMetrics": ["Freight rates", "Port dwell time", "Transit reliability", "Container lead time"],
        },
        {
            "factor": "Trade access and biosecurity",
            "pressure": "Market access risk",
            "businessImpact": (
                "Export certification, biosecurity status, tariff access, and destination-market rules can quickly change achievable volume by country."
            ),
            "forecastUse": "Use destination concentration insights to prioritise risk monitoring for key markets.",
            "watchMetrics": ["Trade access notices", "Biosecurity alerts", "Tariff changes", "Destination approvals"],
        },
        {
            "factor": "Currency and consumer demand",
            "pressure": "Demand and pricing sensitivity",
            "businessImpact": (
                "Exchange rates, retail demand, foodservice recovery, and competitor supply influence how much volume destinations can absorb."
            ),
            "forecastUse": "Use the high case only where demand strength is supported by market pricing and destination growth signals.",
            "watchMetrics": ["AUD exchange rate", "Import demand", "Foodservice demand", "Competitor supply"],
        },
    ]

    recommendations = [
        "Use beef as the headline growth story, but frame it with concentration risk in the largest destination markets.",
        "Position lamb as a market-portfolio problem rather than a simple decline story: identify growing destinations separately from falling ones.",
        "Track export share of production as the core supply-demand pressure metric across the forecast year.",
        "Connect the scenario bands to operating assumptions: climate affects supply, logistics affects executable shipments, and trade access affects destination allocation.",
        "Add external datasets in a later version for rainfall, freight rates, exchange rates, and feed costs to turn the qualitative risk matrix into a quantified driver model.",
    ]

    return {
        "title": f"{forecast_year} Commercial Outlook",
        "subtitle": (
            f"Integrated business report for {export_month_start} to {export_month_end}, "
            "combining market insights, forecast scenarios, and operating risk factors."
        ),
        "executiveSummary": executive_summary,
        "keyFindings": key_findings,
        "forecast": {
            "year": forecast_year,
            "model": "Linear trend with monthly or quarterly seasonality",
            "methodNote": (
                "The forecast is a transparent baseline model. Scenario bands are not live AI predictions; they translate model error and business uncertainty into conservative, base, and high cases."
            ),
            "annualBaseCards": annual_cards,
            "scenarioSummary": scenario_summary,
        },
        "impactFactors": impact_factors,
        "recommendations": recommendations,
        "limitations": [
            "Forecasts are based on the historical ABS and DAFF series currently packaged in the project.",
            "Environmental, logistics, currency, and trade factors are represented as scenario drivers, not live external inputs.",
            "The next enhancement would join external climate, freight, feed-cost, and FX datasets into the forecasting layer.",
        ],
    }


def build_payload(
    start_release_month: str,
    end_release_month: str,
    forecast_year: Optional[int] = None,
) -> dict:
    run_label = build_run_label(start_release_month, end_release_month)
    summary, exports_quarterly, production = load_inputs(run_label)

    exports_clean = pd.read_csv(PROCESSED_DIR / f"exports_clean_{run_label}.csv")
    exports_clean["report_month"] = pd.to_datetime(exports_clean["report_month"])
    production["date"] = pd.to_datetime(production["date"])
    export_release_months = int(exports_clean["release_month"].nunique())
    production_release_folders = int(production["release_month"].nunique())
    export_month_start = exports_clean["report_month"].min().strftime("%Y-%m")
    export_month_end = exports_clean["report_month"].max().strftime("%Y-%m")
    production_release_start = production["release_month"].min()
    production_release_end = production["release_month"].max()
    if forecast_year is None:
        forecast_year = int(exports_clean["report_month"].dt.year.max()) + 1

    insights = load_or_build_insights(
        run_label=run_label,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    forecast = load_or_build_forecast(
        run_label=run_label,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
        forecast_year=forecast_year,
    )

    latest_export_month = exports_clean["report_month"].max()
    latest_export_rows = exports_clean[
        (exports_clean["report_month"] == latest_export_month)
        & (exports_clean["product"].isin(["beef", "lamb"]))
    ]
    latest_export_kpis = (
        latest_export_rows.groupby("product", as_index=False)["tonnes"]
        .sum()
        .set_index("product")["tonnes"]
        .to_dict()
    )

    latest_prod_quarter = summary["quarter"].max()
    latest_prod_rows = summary[summary["quarter"] == latest_prod_quarter].set_index("product")

    production_trend = series_records(
        summary[summary["product"].isin(["beef", "lamb"])][["quarter", "product", "production_tonnes"]],
        "quarter",
        "product",
        "production_tonnes",
    )

    exports_monthly = (
        exports_clean[exports_clean["product"].isin(["beef", "lamb"])]
        .groupby(["report_month", "product"], as_index=False)["tonnes"]
        .sum()
    )
    exports_monthly["month_label"] = exports_monthly["report_month"].dt.strftime("%Y-%m")
    exports_trend = series_records(
        exports_monthly[["month_label", "product", "tonnes"]],
        "month_label",
        "product",
        "tonnes",
    )

    export_mix = (
        exports_quarterly[exports_quarterly["product"].isin(["beef", "lamb", "mutton"])]
        .groupby(["quarter", "product"], as_index=False)["tonnes"]
        .sum()
    )
    export_mix_records = series_records(export_mix, "quarter", "product", "tonnes")

    top_destinations = {}
    export_destinations = (
        exports_clean[exports_clean["product"].isin(["beef", "lamb"])]
        .groupby(["destination", "product"], as_index=False)["tonnes"]
        .sum()
    )
    for product in ["beef", "lamb"]:
        subset = (
            export_destinations[export_destinations["product"] == product]
            .sort_values("tonnes", ascending=False)
            .head(8)
        )
        top_destinations[product] = [
            {"destination": row["destination"], "tonnes": round(float(row["tonnes"]), 2)}
            for _, row in subset.iterrows()
        ]

    comparison_records = []
    comparison = summary[summary["product"].isin(["beef", "lamb"])].sort_values(["quarter", "product"])
    for quarter, quarter_rows in comparison.groupby("quarter"):
        item = {"label": quarter}
        for _, row in quarter_rows.iterrows():
            item[f"{row['product']}_production"] = round(float(row["production_tonnes"]), 2)
            item[f"{row['product']}_exports"] = round(float(row["exports_tonnes"]), 2)
        comparison_records.append(item)

    production_coverage = production[production["state"] == "Australia"][["quarter", "product", "metric_group", "value"]]
    australia_states = int(production["state"].nunique())
    quarter_count = int(summary["quarter"].nunique())

    payload = {
        "meta": {
            "project_title": "Australian Beef & Lamb Market Intelligence",
            "subtitle": "A business-style static dashboard that explains both the market outcomes and the pipeline behind them.",
            "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "data_window": {
                "start": export_month_start,
                "end": export_month_end,
                "frequency": "monthly exports and quarterly production",
            },
            "coverage": {
                "export_release_months": export_release_months,
                "production_release_folders": production_release_folders,
                "quarters_in_scope": quarter_count,
                "production_states": australia_states,
                "clean_export_rows": int(len(exports_clean)),
                "clean_production_rows": int(len(production)),
            },
        },
        "kpis": [
            {
                "label": "Latest Beef Exports",
                "value": round(float(latest_export_kpis.get("beef", 0.0)), 2),
                "unit": "tonnes",
                "period": latest_export_month.strftime("%Y-%m"),
                "accent": "copper",
            },
            {
                "label": "Latest Lamb Exports",
                "value": round(float(latest_export_kpis.get("lamb", 0.0)), 2),
                "unit": "tonnes",
                "period": latest_export_month.strftime("%Y-%m"),
                "accent": "moss",
            },
            {
                "label": "Latest Beef Production",
                "value": round(float(latest_prod_rows.loc["beef", "production_tonnes"]), 2),
                "unit": "tonnes",
                "period": latest_prod_quarter,
                "accent": "navy",
            },
            {
                "label": "Latest Lamb Production",
                "value": round(float(latest_prod_rows.loc["lamb", "production_tonnes"]), 2),
                "unit": "tonnes",
                "period": latest_prod_quarter,
                "accent": "olive",
            },
        ],
        "sources": [
            {
                "title": "ABS Livestock Products, Australia",
                "type": "Quarterly production and slaughter",
                "scope": (
                    f"Production releases used: {production_release_start} to "
                    f"{production_release_end}. Each workbook contains long historical quarterly series."
                ),
                "raw_files": ["7215003.xlsx", "7215006.xlsx", "7215009.xlsx", "7215012.xlsx"],
                "logic": [
                    "Read the Data1 worksheet from each workbook.",
                    "Extract description, series type, and series id metadata from fixed ABS rows.",
                    "Keep only Original series to avoid mixing adjusted or trend variants.",
                    "Deduplicate overlapping releases by keeping the latest release_month for each date + series_id record.",
                    f"Filter the final business window down to {export_month_start} through {export_month_end}.",
                ],
                "outputs": [
                    f"production_clean_archive_{run_label}.csv",
                    f"production_clean_latest_{run_label}.csv",
                ],
            },
            {
                "title": "DAFF Monthly 57 Destination Reports",
                "type": "Monthly export flow",
                "scope": f"Monthly export releases used: {start_release_month} through {end_release_month}.",
                "raw_files": [
                    f"{start_release_month[2:4]}{start_release_month[5:7]}_m57dest.xlsx",
                    "...",
                    f"{end_release_month[2:4]}{end_release_month[5:7]}_m57dest.xlsx",
                ],
                "logic": [
                    "Read the Report worksheet and normalize destination column names.",
                    "Keep only the dashboard metrics: Beef & Veal Total, Total Lamb, Total Mutton, and Total Meats.",
                    "Exclude Total Aus and destination subtotal rows such as Total Asia or Other EU to prevent double counting.",
                    "Deduplicate overlapping release folders by keeping the latest release_month per report_month + destination + metric_name.",
                    "Aggregate monthly flows into quarterly export totals for report-ready views.",
                ],
                "outputs": [
                    f"exports_clean_{run_label}.csv",
                    f"exports_quarterly_{run_label}.csv",
                ],
            },
        ],
        "pipeline": {
            "summary": "The dashboard is driven by a repeatable ETL flow that starts from raw Excel files, standardizes market measures, removes duplicate time series, validates coverage, and packages business-ready outputs for static delivery.",
            "nodes": [
                {
                    "id": "raw",
                    "title": "Raw Source Intake",
                    "eyebrow": "Step 1",
                    "tech": ["Excel", "Folder-based release management"],
                    "input": ["ABS quarterly production workbooks", "DAFF monthly 57 destination reports"],
                    "logic": [
                        "Organize source files by release folder under data/raw/production and data/raw/exports.",
                        "Treat each folder as a release event rather than as final business truth.",
                    ],
                    "output": ["Structured raw release folders", "Traceable source provenance by month"],
                    "why": "This preserves lineage and lets the pipeline compare overlapping releases safely.",
                },
                {
                    "id": "production-clean",
                    "title": "Production Cleaning",
                    "eyebrow": "Step 2",
                    "tech": ["Python", "pandas"],
                    "input": ["ABS Data1 sheets", "Description metadata", "Series ids"],
                    "logic": [
                        "Melt wide quarterly tables into long fact rows.",
                        "Parse measure, animal, and state from ABS description strings.",
                        "Keep Original series only.",
                        "Keep the latest release for each date + series_id pair.",
                        f"Restrict the business window to {export_month_start} through {export_month_end}.",
                    ],
                    "output": [
                        f"production_clean_archive_{run_label}.csv",
                        f"production_clean_latest_{run_label}.csv",
                    ],
                    "why": "Production workbooks contain decades of repeated history, so release-aware deduplication is essential.",
                },
                {
                    "id": "exports-clean",
                    "title": "Export Cleaning",
                    "eyebrow": "Step 3",
                    "tech": ["Python", "pandas", "Regex normalization"],
                    "input": ["DAFF monthly Report sheets"],
                    "logic": [
                        "Normalize headers and destination names.",
                        "Keep monthly flow measures for beef, lamb, mutton, and total meats.",
                        "Remove Total Aus and subtotal destinations such as Total Asia or Other Middle East.",
                        "Keep the latest release for each report_month + destination + metric_name.",
                    ],
                    "output": [f"exports_clean_{run_label}.csv"],
                    "why": "Destination subtotals would otherwise inflate totals and distort ranking views.",
                },
                {
                    "id": "aggregate",
                    "title": "Quarterly Reporting Layer",
                    "eyebrow": "Step 4",
                    "tech": ["Python aggregation", "Quarter period logic"],
                    "input": ["Clean monthly exports", "Clean latest production"],
                    "logic": [
                        "Aggregate monthly export flows into quarterly destination totals.",
                        "Merge quarterly exports with Australia-level production and slaughter signals.",
                        "Create a compact market summary table for beef and lamb.",
                    ],
                    "output": [
                        f"exports_quarterly_{run_label}.csv",
                        f"market_quarterly_summary_{run_label}.csv",
                    ],
                    "why": "This layer powers both executive summary views and chart-ready comparisons.",
                },
                {
                    "id": "reporting",
                    "title": "Static Report Packaging",
                    "eyebrow": "Step 5",
                    "tech": ["Matplotlib", "JSON export", "Static dashboard assets"],
                    "input": ["Processed CSV outputs", "Quarterly market summary"],
                    "logic": [
                        "Render six report figures as reusable PNG assets.",
                        "Export chart series and narrative metadata into dashboard_data.json.",
                        "Load everything into a static front-end suitable for GitHub Pages.",
                    ],
                    "output": ["dashboard/data/dashboard_data.json", "dashboard/assets/reports/*.png"],
                    "why": "The final business layer is portable, reviewable, and ready for public portfolio presentation.",
                },
            ],
        },
        "analytics": {
            "productionTrend": production_trend,
            "exportsTrend": exports_trend,
            "exportMix": export_mix_records,
            "topDestinations": top_destinations,
            "productionVsExports": comparison_records,
        },
        "businessReport": build_business_report(
            insights=insights,
            forecast=forecast,
            export_month_start=export_month_start,
            export_month_end=export_month_end,
            forecast_year=forecast_year,
        ),
        "reportSlides": [
            {
                "title": "Executive KPI Snapshot",
                "caption": "Latest monthly exports and latest quarterly production metrics for beef and lamb.",
                "image": "assets/reports/chart_01_kpi_cards.png",
            },
            {
                "title": "Quarterly Production Trend",
                "caption": (
                    "Australia-level production shows beef scale versus lamb seasonality "
                    f"across {quarter_count} quarters."
                ),
                "image": "assets/reports/chart_02_production_trend.png",
            },
            {
                "title": "Monthly Export Trend",
                "caption": "Monthly export flows show a stronger beef volume profile with a visible reset in early 2025.",
                "image": "assets/reports/chart_03_exports_trend.png",
            },
            {
                "title": "Quarterly Product Mix",
                "caption": "Quarterly export mix highlights the dominance of beef and the steady role of lamb and mutton.",
                "image": "assets/reports/chart_04_export_product_mix.png",
            },
            {
                "title": "Destination Ranking",
                "caption": "Destination rankings isolate final markets rather than subtotal regions to preserve analytical integrity.",
                "image": "assets/reports/chart_05_top_destinations.png",
            },
            {
                "title": "Production vs Exports",
                "caption": "Quarterly production and export totals can be compared side by side for each product line.",
                "image": "assets/reports/chart_06_production_vs_exports.png",
            },
        ],
        "artifacts": [
            {
                "label": "Production Latest",
                "path": f"data/processed/production_clean_latest_{run_label}.csv",
                "description": "Deduplicated ABS quarterly facts within the target business window.",
            },
            {
                "label": "Exports Clean",
                "path": f"data/processed/exports_clean_{run_label}.csv",
                "description": "Monthly destination-level export facts with subtotal rows removed.",
            },
            {
                "label": "Exports Quarterly",
                "path": f"data/processed/exports_quarterly_{run_label}.csv",
                "description": "Quarterly destination-level export totals with completeness flags.",
            },
            {
                "label": "Market Summary",
                "path": f"data/processed/market_quarterly_summary_{run_label}.csv",
                "description": "Executive comparison layer for quarterly exports, production, and slaughter.",
            },
            {
                "label": "Market Insights",
                "path": f"data/processed/market_insights_{run_label}.csv",
                "description": "Structured business insight table with narratives, signals, and recommendations.",
            },
            {
                "label": "Market Forecast",
                "path": f"data/processed/market_forecast_{run_label}_for_{forecast_year}.csv",
                "description": "Scenario forecast output for exports, production, and export-share pressure.",
            },
        ],
        "qualityRules": [
            "Keep only ABS Original series and DAFF monthly_flow exports.",
            "Deduplicate production by date + series_id using the latest release month.",
            "Deduplicate exports by report_month + destination + metric_name using the latest release month.",
            "Exclude subtotal destinations such as Total Asia, Other EU, and All Other Countries.",
            f"Limit the business reporting window to {export_month_start} through {export_month_end} after deduplication.",
        ],
    }
    return payload


def copy_report_images(run_label: str) -> None:
    source_dir = REPORTS_DIR / run_label
    DASHBOARD_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for image_path in sorted(source_dir.glob("*.png")):
        shutil.copy2(image_path, DASHBOARD_REPORTS_DIR / image_path.name)


def export_dashboard_assets(
    start_release_month: str,
    end_release_month: str,
    forecast_year: Optional[int] = None,
) -> Path:
    run_label = build_run_label(start_release_month, end_release_month)
    payload = build_payload(start_release_month, end_release_month, forecast_year=forecast_year)

    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)
    copy_report_images(run_label)

    output_path = DASHBOARD_DATA_DIR / "dashboard_data.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved dashboard data to: {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export processed market data and report images into the static dashboard directory."
    )
    parser.add_argument("--start-release-month", type=str, required=True)
    parser.add_argument("--end-release-month", type=str, required=True)
    parser.add_argument(
        "--forecast-year",
        type=int,
        default=None,
        help="Forecast year to package into the dashboard. Defaults to the next year after the latest data.",
    )
    args = parser.parse_args()

    export_dashboard_assets(
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
        forecast_year=args.forecast_year,
    )


if __name__ == "__main__":
    main()
