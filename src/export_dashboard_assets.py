from __future__ import annotations

from pathlib import Path
from datetime import datetime, UTC
import argparse
import json
import shutil

import pandas as pd


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


def build_payload(
    start_release_month: str,
    end_release_month: str,
) -> dict:
    run_label = build_run_label(start_release_month, end_release_month)
    summary, exports_quarterly, production = load_inputs(run_label)

    exports_clean = pd.read_csv(PROCESSED_DIR / f"exports_clean_{run_label}.csv")
    exports_clean["report_month"] = pd.to_datetime(exports_clean["report_month"])
    production["date"] = pd.to_datetime(production["date"])

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
                "start": "2024-01",
                "end": "2025-12",
                "frequency": "monthly exports and quarterly production",
            },
            "coverage": {
                "export_release_months": 24,
                "production_release_folders": 7,
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
                "scope": "Production releases used: 2024-06 to 2025-12. Each workbook contains long historical quarterly series.",
                "raw_files": ["7215003.xlsx", "7215006.xlsx", "7215009.xlsx", "7215012.xlsx"],
                "logic": [
                    "Read the Data1 worksheet from each workbook.",
                    "Extract description, series type, and series id metadata from fixed ABS rows.",
                    "Keep only Original series to avoid mixing adjusted or trend variants.",
                    "Deduplicate overlapping releases by keeping the latest release_month for each date + series_id record.",
                    "Filter the final business window down to 2024-01 through 2025-12.",
                ],
                "outputs": [
                    "production_clean_archive_2024_01_to_2025_12.csv",
                    "production_clean_latest_2024_01_to_2025_12.csv",
                ],
            },
            {
                "title": "DAFF Monthly 57 Destination Reports",
                "type": "Monthly export flow",
                "scope": "Monthly export releases used: 2024-01 through 2025-12.",
                "raw_files": ["2401_m57dest.xlsx", "...", "2512_m57dest.xlsx"],
                "logic": [
                    "Read the Report worksheet and normalize destination column names.",
                    "Keep only the dashboard metrics: Beef & Veal Total, Total Lamb, Total Mutton, and Total Meats.",
                    "Exclude Total Aus and destination subtotal rows such as Total Asia or Other EU to prevent double counting.",
                    "Deduplicate overlapping release folders by keeping the latest release_month per report_month + destination + metric_name.",
                    "Aggregate monthly flows into quarterly export totals for report-ready views.",
                ],
                "outputs": [
                    "exports_clean_2024_01_to_2025_12.csv",
                    "exports_quarterly_2024_01_to_2025_12.csv",
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
                        "Restrict the business window to 2024-01 through 2025-12.",
                    ],
                    "output": [
                        "production_clean_archive_2024_01_to_2025_12.csv",
                        "production_clean_latest_2024_01_to_2025_12.csv",
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
                    "output": ["exports_clean_2024_01_to_2025_12.csv"],
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
                        "exports_quarterly_2024_01_to_2025_12.csv",
                        "market_quarterly_summary_2024_01_to_2025_12.csv",
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
        "reportSlides": [
            {
                "title": "Executive KPI Snapshot",
                "caption": "Latest monthly exports and latest quarterly production metrics for beef and lamb.",
                "image": "assets/reports/chart_01_kpi_cards.png",
            },
            {
                "title": "Quarterly Production Trend",
                "caption": "Australia-level production shows beef scale versus lamb seasonality across eight quarters.",
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
                "path": "data/processed/production_clean_latest_2024_01_to_2025_12.csv",
                "description": "Deduplicated ABS quarterly facts within the target business window.",
            },
            {
                "label": "Exports Clean",
                "path": "data/processed/exports_clean_2024_01_to_2025_12.csv",
                "description": "Monthly destination-level export facts with subtotal rows removed.",
            },
            {
                "label": "Exports Quarterly",
                "path": "data/processed/exports_quarterly_2024_01_to_2025_12.csv",
                "description": "Quarterly destination-level export totals with completeness flags.",
            },
            {
                "label": "Market Summary",
                "path": "data/processed/market_quarterly_summary_2024_01_to_2025_12.csv",
                "description": "Executive comparison layer for quarterly exports, production, and slaughter.",
            },
        ],
        "qualityRules": [
            "Keep only ABS Original series and DAFF monthly_flow exports.",
            "Deduplicate production by date + series_id using the latest release month.",
            "Deduplicate exports by report_month + destination + metric_name using the latest release month.",
            "Exclude subtotal destinations such as Total Asia, Other EU, and All Other Countries.",
            "Limit the business reporting window to 2024-01 through 2025-12 after deduplication.",
        ],
    }
    return payload


def copy_report_images(run_label: str) -> None:
    source_dir = REPORTS_DIR / run_label
    DASHBOARD_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    for image_path in sorted(source_dir.glob("*.png")):
        shutil.copy2(image_path, DASHBOARD_REPORTS_DIR / image_path.name)


def export_dashboard_assets(start_release_month: str, end_release_month: str) -> Path:
    run_label = build_run_label(start_release_month, end_release_month)
    payload = build_payload(start_release_month, end_release_month)

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
    args = parser.parse_args()

    export_dashboard_assets(
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )


if __name__ == "__main__":
    main()
