from pathlib import Path
from typing import Optional
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CHARTS_BASE_DIR = PROJECT_ROOT / "reports" / "charts"

EXPORTS_CLEAN_SINGLE = "exports_clean_{release_month}.csv"
EXPORTS_CLEAN_RANGE = "exports_clean_{start_release_month}_to_{end_release_month}.csv"
EXPORTS_CLEAN_ALL = "exports_clean_all.csv"

EXPORTS_QUARTERLY_SINGLE = "exports_quarterly_{release_month}.csv"
EXPORTS_QUARTERLY_RANGE = "exports_quarterly_{start_release_month}_to_{end_release_month}.csv"
EXPORTS_QUARTERLY_ALL = "exports_quarterly_all.csv"

PRODUCTION_LATEST_SINGLE = "production_clean_latest_{release_month}.csv"
PRODUCTION_LATEST_RANGE = (
    "production_clean_latest_{start_release_month}_to_{end_release_month}.csv"
)
PRODUCTION_LATEST_ALL = "production_clean_latest_all.csv"

MARKET_SUMMARY_SINGLE = "market_quarterly_summary_{release_month}.csv"
MARKET_SUMMARY_RANGE = "market_quarterly_summary_{start_release_month}_to_{end_release_month}.csv"
MARKET_SUMMARY_ALL = "market_quarterly_summary_all.csv"

COLOR_MAP = {
    "beef": "#9d3d2f",
    "lamb": "#5c7c46",
    "mutton": "#c08b2c",
    "production": "#3e5c76",
    "exports": "#d17a22",
}


def build_file_name(
    single_pattern: str,
    range_pattern: str,
    all_pattern: str,
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> str:
    if release_month:
        return single_pattern.format(release_month=release_month.replace("-", "_"))

    if start_release_month and end_release_month:
        return range_pattern.format(
            start_release_month=start_release_month.replace("-", "_"),
            end_release_month=end_release_month.replace("-", "_"),
        )

    return all_pattern


def build_run_label(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> str:
    if release_month:
        return release_month.replace("-", "_")

    if start_release_month and end_release_month:
        return (
            f"{start_release_month.replace('-', '_')}"
            f"_to_{end_release_month.replace('-', '_')}"
        )

    return "all"


def save_figure(fig: plt.Figure, output_dir: Path, file_name: str) -> None:
    output_path = output_dir / file_name
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved chart to: {output_path}")


def build_month_window_label(exports_clean: pd.DataFrame) -> str:
    report_months = pd.to_datetime(exports_clean["report_month"], errors="coerce").dropna()
    if report_months.empty:
        return "the selected reporting window"

    return (
        f"{report_months.min().strftime('%Y-%m')} to "
        f"{report_months.max().strftime('%Y-%m')}"
    )


def load_inputs(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    exports_clean_path = PROCESSED_DIR / build_file_name(
        EXPORTS_CLEAN_SINGLE,
        EXPORTS_CLEAN_RANGE,
        EXPORTS_CLEAN_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    exports_quarterly_path = PROCESSED_DIR / build_file_name(
        EXPORTS_QUARTERLY_SINGLE,
        EXPORTS_QUARTERLY_RANGE,
        EXPORTS_QUARTERLY_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    production_path = PROCESSED_DIR / build_file_name(
        PRODUCTION_LATEST_SINGLE,
        PRODUCTION_LATEST_RANGE,
        PRODUCTION_LATEST_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    market_summary_path = PROCESSED_DIR / build_file_name(
        MARKET_SUMMARY_SINGLE,
        MARKET_SUMMARY_RANGE,
        MARKET_SUMMARY_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    for path in [
        exports_clean_path,
        exports_quarterly_path,
        production_path,
        market_summary_path,
    ]:
        if not path.exists():
            raise FileNotFoundError(f"Required input file not found: {path}")

    exports_clean = pd.read_csv(exports_clean_path)
    exports_quarterly = pd.read_csv(exports_quarterly_path)
    production = pd.read_csv(production_path)
    market_summary = pd.read_csv(market_summary_path)
    return exports_clean, exports_quarterly, production, market_summary


def chart_kpi_cards(
    output_dir: Path,
    exports_clean: pd.DataFrame,
    production: pd.DataFrame,
) -> None:
    month_window_label = build_month_window_label(exports_clean)
    export_totals = (
        exports_clean[exports_clean["product"].isin(["beef", "lamb"])]
        .groupby(["report_month", "product"], as_index=False)["tonnes"]
        .sum()
    )
    export_totals["report_month"] = pd.to_datetime(export_totals["report_month"])
    latest_month = export_totals["report_month"].max()
    latest_exports = export_totals[export_totals["report_month"] == latest_month]

    production_totals = (
        production[
            (production["state"] == "Australia")
            & (production["metric_group"] == "production")
            & (production["product"].isin(["beef", "lamb"]))
        ]
        .groupby(["quarter", "product"], as_index=False)["value"]
        .sum()
    )
    latest_quarter = production_totals["quarter"].max()
    latest_production = production_totals[production_totals["quarter"] == latest_quarter]

    card_specs = [
        (
            "Latest Beef Exports",
            latest_exports.loc[latest_exports["product"] == "beef", "tonnes"].sum(),
            "tonnes",
            latest_month.strftime("%Y-%m"),
            COLOR_MAP["beef"],
        ),
        (
            "Latest Lamb Exports",
            latest_exports.loc[latest_exports["product"] == "lamb", "tonnes"].sum(),
            "tonnes",
            latest_month.strftime("%Y-%m"),
            COLOR_MAP["lamb"],
        ),
        (
            "Latest Beef Production",
            latest_production.loc[latest_production["product"] == "beef", "value"].sum(),
            "tonnes",
            latest_quarter,
            COLOR_MAP["production"],
        ),
        (
            "Latest Lamb Production",
            latest_production.loc[latest_production["product"] == "lamb", "value"].sum(),
            "tonnes",
            latest_quarter,
            COLOR_MAP["production"],
        ),
    ]

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(
        0.02,
        0.95,
        "Australian Beef and Lamb Market KPI Snapshot",
        fontsize=20,
        fontweight="bold",
        ha="left",
        va="top",
    )
    ax.text(
        0.02,
        0.88,
        (
            "Latest monthly exports and latest quarterly production from the "
            f"cleaned {month_window_label} window."
        ),
        fontsize=11,
        color="#444444",
        ha="left",
        va="top",
    )

    x_positions = [0.03, 0.28, 0.53, 0.78]
    for x_pos, (title, value, unit, period_label, color) in zip(x_positions, card_specs):
        rect = plt.Rectangle(
            (x_pos, 0.25),
            0.19,
            0.46,
            facecolor=color,
            alpha=0.92,
            linewidth=0,
        )
        ax.add_patch(rect)
        ax.text(x_pos + 0.015, 0.64, title, fontsize=12, color="white", va="top")
        ax.text(
            x_pos + 0.015,
            0.47,
            f"{value:,.0f}",
            fontsize=23,
            fontweight="bold",
            color="white",
            va="center",
        )
        ax.text(x_pos + 0.015, 0.36, f"{unit} | {period_label}", fontsize=10, color="white")

    save_figure(fig, output_dir, "chart_01_kpi_cards.png")


def chart_production_trend(output_dir: Path, production: pd.DataFrame) -> None:
    prod = (
        production[
            (production["state"] == "Australia")
            & (production["metric_group"] == "production")
            & (production["product"].isin(["beef", "lamb"]))
        ]
        .groupby(["quarter", "product"], as_index=False)["value"]
        .sum()
    )
    pivot = (
        prod.pivot(index="quarter", columns="product", values="value")
        .fillna(0)
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    for product in ["beef", "lamb"]:
        ax.plot(
            pivot.index,
            pivot[product],
            marker="o",
            linewidth=2.5,
            label=product.title(),
            color=COLOR_MAP[product],
        )

    ax.set_title("Quarterly Australia Production Trend", fontsize=16, fontweight="bold")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("Tonnes")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(frameon=False)
    plt.xticks(rotation=45)

    save_figure(fig, output_dir, "chart_02_production_trend.png")


def chart_exports_trend(output_dir: Path, exports_clean: pd.DataFrame) -> None:
    exports = (
        exports_clean[exports_clean["product"].isin(["beef", "lamb"])]
        .groupby(["report_month", "product"], as_index=False)["tonnes"]
        .sum()
    )
    exports["report_month"] = pd.to_datetime(exports["report_month"])
    pivot = (
        exports.pivot(index="report_month", columns="product", values="tonnes")
        .fillna(0)
        .sort_index()
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    for product in ["beef", "lamb"]:
        ax.plot(
            pivot.index,
            pivot[product],
            marker="o",
            linewidth=2.5,
            label=product.title(),
            color=COLOR_MAP[product],
        )

    ax.set_title("Monthly Export Trend", fontsize=16, fontweight="bold")
    ax.set_xlabel("Report Month")
    ax.set_ylabel("Tonnes")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(frameon=False)
    fig.autofmt_xdate()

    save_figure(fig, output_dir, "chart_03_exports_trend.png")


def chart_export_mix(output_dir: Path, exports_quarterly: pd.DataFrame) -> None:
    mix = (
        exports_quarterly[exports_quarterly["product"].isin(["beef", "lamb", "mutton"])]
        .groupby(["quarter", "product"], as_index=False)["tonnes"]
        .sum()
    )
    pivot = (
        mix.pivot(index="quarter", columns="product", values="tonnes")
        .fillna(0)
        .sort_index()
    )
    pivot = pivot.reindex(columns=["beef", "lamb", "mutton"], fill_value=0)

    fig, ax = plt.subplots(figsize=(12, 6))
    bottom = np.zeros(len(pivot))
    for product in ["beef", "lamb", "mutton"]:
        values = pivot[product].to_numpy()
        ax.bar(
            pivot.index,
            values,
            bottom=bottom,
            label=product.title(),
            color=COLOR_MAP[product],
        )
        bottom = bottom + values

    ax.set_title("Quarterly Export Product Mix", fontsize=16, fontweight="bold")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("Tonnes")
    ax.legend(frameon=False)
    plt.xticks(rotation=45)

    save_figure(fig, output_dir, "chart_04_export_product_mix.png")


def chart_top_destinations(output_dir: Path, exports_clean: pd.DataFrame) -> None:
    month_window_label = build_month_window_label(exports_clean)
    totals = (
        exports_clean[exports_clean["product"].isin(["beef", "lamb"])]
        .groupby(["destination", "product"], as_index=False)["tonnes"]
        .sum()
    )
    beef_top = (
        totals[totals["product"] == "beef"]
        .sort_values("tonnes", ascending=False)
        .head(10)
        .sort_values("tonnes")
    )
    lamb_top = (
        totals[totals["product"] == "lamb"]
        .sort_values("tonnes", ascending=False)
        .head(10)
        .sort_values("tonnes")
    )

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    axes[0].barh(beef_top["destination"], beef_top["tonnes"], color=COLOR_MAP["beef"])
    axes[0].set_title("Top Beef Export Destinations")
    axes[0].set_xlabel("Tonnes")

    axes[1].barh(lamb_top["destination"], lamb_top["tonnes"], color=COLOR_MAP["lamb"])
    axes[1].set_title("Top Lamb Export Destinations")
    axes[1].set_xlabel("Tonnes")

    fig.suptitle(
        f"Top Export Destinations Across {month_window_label}",
        fontsize=16,
        fontweight="bold",
    )
    plt.tight_layout()

    save_figure(fig, output_dir, "chart_05_top_destinations.png")


def chart_production_vs_exports(output_dir: Path, market_summary: pd.DataFrame) -> None:
    summary = market_summary[market_summary["product"].isin(["beef", "lamb"])].copy()
    summary = summary.sort_values(["quarter", "product"])

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=False)
    for axis, product in zip(axes, ["beef", "lamb"]):
        subset = summary[summary["product"] == product].copy()
        x = np.arange(len(subset))
        width = 0.38

        axis.bar(
            x - width / 2,
            subset["production_tonnes"].fillna(0),
            width=width,
            color=COLOR_MAP["production"],
            label="Production",
        )
        axis.bar(
            x + width / 2,
            subset["exports_tonnes"].fillna(0),
            width=width,
            color=COLOR_MAP["exports"],
            label="Exports",
        )
        axis.set_title(product.title())
        axis.set_xlabel("Quarter")
        axis.set_ylabel("Tonnes")
        axis.set_xticks(x)
        axis.set_xticklabels(subset["quarter"], rotation=45)
        axis.grid(axis="y", linestyle="--", alpha=0.3)

    axes[0].legend(frameon=False)
    fig.suptitle(
        "Quarterly Production vs Exports",
        fontsize=16,
        fontweight="bold",
    )
    plt.tight_layout()

    save_figure(fig, output_dir, "chart_06_production_vs_exports.png")


def build_report_charts(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> list[Path]:
    exports_clean, exports_quarterly, production, market_summary = load_inputs(
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    output_dir = CHARTS_BASE_DIR / build_run_label(
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    chart_kpi_cards(output_dir, exports_clean, production)
    chart_production_trend(output_dir, production)
    chart_exports_trend(output_dir, exports_clean)
    chart_export_mix(output_dir, exports_quarterly)
    chart_top_destinations(output_dir, exports_clean)
    chart_production_vs_exports(output_dir, market_summary)

    return sorted(output_dir.glob("*.png"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build report-ready PNG charts from processed beef and lamb market data."
    )
    parser.add_argument(
        "--release-month",
        type=str,
        default=None,
        help="Single release month token such as 2025-12",
    )
    parser.add_argument(
        "--start-release-month",
        type=str,
        default=None,
        help="Start release month for a range, for example 2024-01",
    )
    parser.add_argument(
        "--end-release-month",
        type=str,
        default=None,
        help="End release month for a range, for example 2025-12",
    )
    args = parser.parse_args()

    build_report_charts(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )


if __name__ == "__main__":
    main()
