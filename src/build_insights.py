from pathlib import Path
from typing import Optional
import argparse

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

EXPORTS_CLEAN_SINGLE = "exports_clean_{release_month}.csv"
EXPORTS_CLEAN_RANGE = "exports_clean_{start_release_month}_to_{end_release_month}.csv"
EXPORTS_CLEAN_ALL = "exports_clean_all.csv"

MARKET_SUMMARY_SINGLE = "market_quarterly_summary_{release_month}.csv"
MARKET_SUMMARY_RANGE = "market_quarterly_summary_{start_release_month}_to_{end_release_month}.csv"
MARKET_SUMMARY_ALL = "market_quarterly_summary_all.csv"

OUTPUT_SINGLE = "market_insights_{release_month}.csv"
OUTPUT_RANGE = "market_insights_{start_release_month}_to_{end_release_month}.csv"
OUTPUT_ALL = "market_insights_all.csv"

CORE_PRODUCTS = ["beef", "lamb"]
MIX_PRODUCTS = ["beef", "lamb", "mutton"]


def build_file_name(
    single_pattern: str,
    range_pattern: str,
    all_pattern: str,
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> str:
    """
    Build a processed file name based on the selected release mode.
    """
    if release_month:
        return single_pattern.format(release_month=release_month.replace("-", "_"))

    if start_release_month and end_release_month:
        return range_pattern.format(
            start_release_month=start_release_month.replace("-", "_"),
            end_release_month=end_release_month.replace("-", "_"),
        )

    return all_pattern


def validate_release_mode(
    release_month: Optional[str],
    start_release_month: Optional[str],
    end_release_month: Optional[str],
) -> None:
    if release_month and (start_release_month or end_release_month):
        raise ValueError(
            "Use either --release-month or a start and end release month range, not both."
        )

    if (start_release_month and not end_release_month) or (
        end_release_month and not start_release_month
    ):
        raise ValueError(
            "Both --start-release-month and --end-release-month must be provided together."
        )


def load_inputs(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exports_path = PROCESSED_DIR / build_file_name(
        EXPORTS_CLEAN_SINGLE,
        EXPORTS_CLEAN_RANGE,
        EXPORTS_CLEAN_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    summary_path = PROCESSED_DIR / build_file_name(
        MARKET_SUMMARY_SINGLE,
        MARKET_SUMMARY_RANGE,
        MARKET_SUMMARY_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    if not exports_path.exists():
        raise FileNotFoundError(f"Cleaned export file not found: {exports_path}")

    if not summary_path.exists():
        raise FileNotFoundError(f"Market summary file not found: {summary_path}")

    exports = pd.read_csv(exports_path)
    summary = pd.read_csv(summary_path)

    validate_exports(exports)
    validate_summary(summary)

    exports["report_month"] = pd.to_datetime(exports["report_month"], errors="coerce")
    exports["tonnes"] = pd.to_numeric(exports["tonnes"], errors="coerce")
    exports = exports.dropna(subset=["report_month", "tonnes"]).copy()
    exports["year"] = exports["report_month"].dt.year

    for col in ["exports_tonnes", "production_tonnes", "slaughter_value"]:
        summary[col] = pd.to_numeric(summary[col], errors="coerce")
    summary["year"] = summary["quarter"].astype(str).str[:4].astype(int)

    return exports, summary


def validate_exports(df: pd.DataFrame) -> None:
    required_columns = {
        "report_month",
        "destination",
        "product",
        "tonnes",
    }
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in cleaned exports file: {sorted(missing_columns)}"
        )


def validate_summary(df: pd.DataFrame) -> None:
    required_columns = {
        "quarter",
        "product",
        "exports_tonnes",
        "production_tonnes",
        "slaughter_value",
    }
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in market summary file: {sorted(missing_columns)}"
        )


def pct_change(current: float, previous: float) -> Optional[float]:
    if pd.isna(current) or pd.isna(previous) or previous == 0:
        return None
    return (current / previous - 1) * 100


def direction_from_change(change_pct: Optional[float]) -> str:
    if change_pct is None:
        return "not_available"
    if change_pct >= 10:
        return "strong_growth"
    if change_pct >= 3:
        return "growth"
    if change_pct <= -10:
        return "strong_decline"
    if change_pct <= -3:
        return "decline"
    return "stable"


def direction_from_point_change(change_value: Optional[float]) -> str:
    if change_value is None:
        return "not_available"
    if change_value >= 3:
        return "rising"
    if change_value <= -3:
        return "falling"
    return "stable"


def format_tonnes(value: float) -> str:
    return f"{value:,.0f} tonnes"


def format_pct(value: Optional[float]) -> str:
    if value is None or pd.isna(value):
        return "not available"
    return f"{value:.1f}%"


def product_label(product: str) -> str:
    return product.replace("_", " ").title()


def add_insight(
    records: list[dict],
    *,
    insight_id: str,
    category: str,
    metric: str,
    product: str,
    period: str,
    comparison_period: Optional[str],
    value: Optional[float],
    comparison_value: Optional[float],
    change_value: Optional[float],
    change_pct: Optional[float],
    unit: str,
    direction: str,
    business_signal: str,
    recommendation: str,
    narrative: str,
    sort_order: int,
) -> None:
    records.append(
        {
            "insight_id": insight_id,
            "category": category,
            "metric": metric,
            "product": product,
            "period": period,
            "comparison_period": comparison_period,
            "value": value,
            "comparison_value": comparison_value,
            "change_value": change_value,
            "change_pct": change_pct,
            "unit": unit,
            "direction": direction,
            "business_signal": business_signal,
            "recommendation": recommendation,
            "narrative": narrative,
            "sort_order": sort_order,
        }
    )


def annual_market_totals(summary: pd.DataFrame) -> pd.DataFrame:
    annual = (
        summary[summary["product"].isin(CORE_PRODUCTS)]
        .groupby(["year", "product"], as_index=False)
        .agg(
            exports_tonnes=("exports_tonnes", "sum"),
            production_tonnes=("production_tonnes", "sum"),
            slaughter_value=("slaughter_value", "sum"),
        )
    )
    annual["export_share_pct"] = (
        annual["exports_tonnes"] / annual["production_tonnes"] * 100
    )
    return annual


def build_annual_growth_insights(
    records: list[dict],
    annual: pd.DataFrame,
    current_year: int,
    previous_year: int,
    start_sort_order: int,
) -> int:
    current = annual[annual["year"] == current_year].set_index("product")
    previous = annual[annual["year"] == previous_year].set_index("product")
    sort_order = start_sort_order

    for product in CORE_PRODUCTS:
        if product not in current.index or product not in previous.index:
            continue

        current_exports = float(current.loc[product, "exports_tonnes"])
        previous_exports = float(previous.loc[product, "exports_tonnes"])
        export_change = current_exports - previous_exports
        export_change_pct = pct_change(current_exports, previous_exports)
        export_direction = direction_from_change(export_change_pct)
        export_label = product_label(product)

        add_insight(
            records,
            insight_id=f"{product}_exports_yoy_{current_year}",
            category="market_growth",
            metric="exports_yoy",
            product=product,
            period=str(current_year),
            comparison_period=str(previous_year),
            value=current_exports,
            comparison_value=previous_exports,
            change_value=export_change,
            change_pct=export_change_pct,
            unit="tonnes",
            direction=export_direction,
            business_signal=(
                f"{export_label} export demand changed {format_pct(export_change_pct)} "
                f"from {previous_year} to {current_year}."
            ),
            recommendation=(
                "Prioritise capacity planning and destination monitoring if growth is above production growth."
                if export_change > 0
                else "Investigate destination-level weakness before treating the decline as a category-wide issue."
            ),
            narrative=(
                f"{export_label} exports reached {format_tonnes(current_exports)} in "
                f"{current_year}, a {format_pct(export_change_pct)} change versus "
                f"{previous_year}."
            ),
            sort_order=sort_order,
        )
        sort_order += 1

        current_production = float(current.loc[product, "production_tonnes"])
        previous_production = float(previous.loc[product, "production_tonnes"])
        production_change = current_production - previous_production
        production_change_pct = pct_change(current_production, previous_production)
        production_direction = direction_from_change(production_change_pct)

        add_insight(
            records,
            insight_id=f"{product}_production_yoy_{current_year}",
            category="supply",
            metric="production_yoy",
            product=product,
            period=str(current_year),
            comparison_period=str(previous_year),
            value=current_production,
            comparison_value=previous_production,
            change_value=production_change,
            change_pct=production_change_pct,
            unit="tonnes",
            direction=production_direction,
            business_signal=(
                f"{export_label} production changed {format_pct(production_change_pct)} "
                f"from {previous_year} to {current_year}."
            ),
            recommendation=(
                "Use production growth as a supply-side anchor when interpreting export momentum."
            ),
            narrative=(
                f"{export_label} production was {format_tonnes(current_production)} in "
                f"{current_year}, compared with {format_tonnes(previous_production)} "
                f"in {previous_year}."
            ),
            sort_order=sort_order,
        )
        sort_order += 1

        current_share = float(current.loc[product, "export_share_pct"])
        previous_share = float(previous.loc[product, "export_share_pct"])
        share_change = current_share - previous_share

        add_insight(
            records,
            insight_id=f"{product}_export_share_{current_year}",
            category="supply_demand_balance",
            metric="export_share_of_production",
            product=product,
            period=str(current_year),
            comparison_period=str(previous_year),
            value=current_share,
            comparison_value=previous_share,
            change_value=share_change,
            change_pct=None,
            unit="percentage_points",
            direction=direction_from_point_change(share_change),
            business_signal=(
                f"{export_label} exports represented {current_share:.1f}% of production "
                f"in {current_year}."
            ),
            recommendation=(
                "Track this ratio as a pressure indicator: a rising share means more output is being pulled into export channels."
            ),
            narrative=(
                f"{export_label} export share of production moved from "
                f"{previous_share:.1f}% in {previous_year} to {current_share:.1f}% "
                f"in {current_year}."
            ),
            sort_order=sort_order,
        )
        sort_order += 1

    return sort_order


def build_destination_insights(
    records: list[dict],
    exports: pd.DataFrame,
    current_year: int,
    previous_year: int,
    start_sort_order: int,
) -> int:
    sort_order = start_sort_order
    destination_totals = (
        exports[exports["product"].isin(CORE_PRODUCTS)]
        .groupby(["year", "product", "destination"], as_index=False)["tonnes"]
        .sum()
    )

    current_destinations = destination_totals[
        destination_totals["year"] == current_year
    ].copy()

    for product in CORE_PRODUCTS:
        subset = current_destinations[current_destinations["product"] == product]
        if subset.empty:
            continue

        total_tonnes = float(subset["tonnes"].sum())
        top4 = subset.sort_values("tonnes", ascending=False).head(4)
        top4_tonnes = float(top4["tonnes"].sum())
        top4_share = top4_tonnes / total_tonnes * 100 if total_tonnes else None
        destinations = ", ".join(top4["destination"].astype(str).tolist())
        label = product_label(product)

        add_insight(
            records,
            insight_id=f"{product}_top4_destination_share_{current_year}",
            category="destination_portfolio",
            metric="top4_destination_share",
            product=product,
            period=str(current_year),
            comparison_period=None,
            value=top4_share,
            comparison_value=None,
            change_value=None,
            change_pct=None,
            unit="percent",
            direction="high_concentration" if top4_share and top4_share >= 60 else "balanced",
            business_signal=(
                f"The top four {label} destinations represented {format_pct(top4_share)} "
                f"of {current_year} export volume."
            ),
            recommendation=(
                "Treat the top destinations as priority account markets, while monitoring concentration risk."
            ),
            narrative=(
                f"{label} export demand was concentrated in {destinations}, which "
                f"together accounted for {format_pct(top4_share)} of {current_year} "
                f"export volume."
            ),
            sort_order=sort_order,
        )
        sort_order += 1

    yearly = destination_totals[
        destination_totals["year"].isin([previous_year, current_year])
    ]
    pivot = (
        yearly.pivot_table(
            index=["product", "destination"],
            columns="year",
            values="tonnes",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )

    if previous_year not in pivot.columns or current_year not in pivot.columns:
        return sort_order

    pivot["change_value"] = pivot[current_year] - pivot[previous_year]
    pivot["change_pct"] = pivot.apply(
        lambda row: pct_change(row[current_year], row[previous_year]),
        axis=1,
    )

    for product in CORE_PRODUCTS:
        subset = pivot[pivot["product"] == product].copy()
        if subset.empty:
            continue

        label = product_label(product)
        for rank, (_, row) in enumerate(
            subset.sort_values("change_value", ascending=False).head(3).iterrows(),
            start=1,
        ):
            destination = row["destination"]
            change_value = float(row["change_value"])
            change_pct = row["change_pct"]
            add_insight(
                records,
                insight_id=f"{product}_destination_gain_{rank}_{current_year}",
                category="destination_portfolio",
                metric="destination_yoy_gain",
                product=product,
                period=str(current_year),
                comparison_period=str(previous_year),
                value=float(row[current_year]),
                comparison_value=float(row[previous_year]),
                change_value=change_value,
                change_pct=change_pct,
                unit="tonnes",
                direction=direction_from_change(change_pct),
                business_signal=(
                    f"{destination} added {format_tonnes(change_value)} of {label} "
                    f"export volume versus {previous_year}."
                ),
                recommendation=(
                    "Use high-growth destinations to explain the demand story and identify priority markets."
                ),
                narrative=(
                    f"{destination} was a major {label} growth destination in "
                    f"{current_year}, rising {format_pct(change_pct)} year on year."
                ),
                sort_order=sort_order,
            )
            sort_order += 1

        for rank, (_, row) in enumerate(
            subset.sort_values("change_value", ascending=True).head(3).iterrows(),
            start=1,
        ):
            destination = row["destination"]
            change_value = float(row["change_value"])
            change_pct = row["change_pct"]
            add_insight(
                records,
                insight_id=f"{product}_destination_decline_{rank}_{current_year}",
                category="destination_portfolio",
                metric="destination_yoy_decline",
                product=product,
                period=str(current_year),
                comparison_period=str(previous_year),
                value=float(row[current_year]),
                comparison_value=float(row[previous_year]),
                change_value=change_value,
                change_pct=change_pct,
                unit="tonnes",
                direction=direction_from_change(change_pct),
                business_signal=(
                    f"{destination} reduced {label} export volume by "
                    f"{format_tonnes(abs(change_value))} versus {previous_year}."
                ),
                recommendation=(
                    "Flag declining destinations as a portfolio risk or a shift in market allocation."
                ),
                narrative=(
                    f"{destination} was a material drag on {label} exports in "
                    f"{current_year}, changing {format_pct(change_pct)} year on year."
                ),
                sort_order=sort_order,
            )
            sort_order += 1

    return sort_order


def build_product_mix_insights(
    records: list[dict],
    exports: pd.DataFrame,
    current_year: int,
    previous_year: int,
    start_sort_order: int,
) -> int:
    sort_order = start_sort_order
    mix = (
        exports[exports["product"].isin(MIX_PRODUCTS)]
        .groupby(["year", "product"], as_index=False)["tonnes"]
        .sum()
    )
    totals = mix.groupby("year", as_index=False)["tonnes"].sum().rename(
        columns={"tonnes": "total_tonnes"}
    )
    mix = mix.merge(totals, on="year", how="left")
    mix["mix_share_pct"] = mix["tonnes"] / mix["total_tonnes"] * 100

    current = mix[mix["year"] == current_year].set_index("product")
    previous = mix[mix["year"] == previous_year].set_index("product")

    for product in MIX_PRODUCTS:
        if product not in current.index or product not in previous.index:
            continue

        label = product_label(product)
        current_share = float(current.loc[product, "mix_share_pct"])
        previous_share = float(previous.loc[product, "mix_share_pct"])
        share_change = current_share - previous_share

        add_insight(
            records,
            insight_id=f"{product}_export_mix_share_{current_year}",
            category="product_mix",
            metric="export_mix_share",
            product=product,
            period=str(current_year),
            comparison_period=str(previous_year),
            value=current_share,
            comparison_value=previous_share,
            change_value=share_change,
            change_pct=None,
            unit="percentage_points",
            direction=direction_from_point_change(share_change),
            business_signal=(
                f"{label} represented {current_share:.1f}% of beef, lamb, and "
                f"mutton export volume in {current_year}."
            ),
            recommendation=(
                "Use mix-share movement to explain whether the market story is broad based or led by one category."
            ),
            narrative=(
                f"{label} mix share moved from {previous_share:.1f}% in "
                f"{previous_year} to {current_share:.1f}% in {current_year}."
            ),
            sort_order=sort_order,
        )
        sort_order += 1

    return sort_order


def build_insights(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> pd.DataFrame:
    """
    Build a structured insight table from processed market outputs.
    """
    validate_release_mode(release_month, start_release_month, end_release_month)

    exports, summary = load_inputs(
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    annual = annual_market_totals(summary)
    available_years = sorted(annual["year"].dropna().unique())
    if len(available_years) < 2:
        raise ValueError("At least two years of market summary data are required.")

    current_year = int(available_years[-1])
    previous_year = int(current_year - 1)
    if previous_year not in available_years:
        raise ValueError(
            f"Previous year {previous_year} is required to build year-on-year insights."
        )

    records: list[dict] = []
    sort_order = 1
    sort_order = build_annual_growth_insights(
        records,
        annual,
        current_year,
        previous_year,
        sort_order,
    )
    sort_order = build_destination_insights(
        records,
        exports,
        current_year,
        previous_year,
        sort_order,
    )
    build_product_mix_insights(
        records,
        exports,
        current_year,
        previous_year,
        sort_order,
    )

    result = pd.DataFrame(records).sort_values("sort_order").reset_index(drop=True)

    output_file_name = build_file_name(
        OUTPUT_SINGLE,
        OUTPUT_RANGE,
        OUTPUT_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    output_path = PROCESSED_DIR / output_file_name
    result.to_csv(output_path, index=False)

    print(f"Saved market insights to: {output_path}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build business insight records from processed market data."
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

    build_insights(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )


if __name__ == "__main__":
    main()
