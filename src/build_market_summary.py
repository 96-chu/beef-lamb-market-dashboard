from pathlib import Path
from typing import Optional
import argparse

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

INPUT_EXPORTS_SINGLE = "exports_quarterly_{release_month}.csv"
INPUT_EXPORTS_RANGE = "exports_quarterly_{start_release_month}_to_{end_release_month}.csv"
INPUT_EXPORTS_ALL = "exports_quarterly_all.csv"

INPUT_PRODUCTION_SINGLE = "production_clean_latest_{release_month}.csv"
INPUT_PRODUCTION_RANGE = (
    "production_clean_latest_{start_release_month}_to_{end_release_month}.csv"
)
INPUT_PRODUCTION_ALL = "production_clean_latest_all.csv"

OUTPUT_SINGLE = "market_quarterly_summary_{release_month}.csv"
OUTPUT_RANGE = "market_quarterly_summary_{start_release_month}_to_{end_release_month}.csv"
OUTPUT_ALL = "market_quarterly_summary_all.csv"


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


def build_market_summary(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> pd.DataFrame:
    """
    Build a quarterly market summary for beef and lamb.

    The summary combines:
    1. quarterly export tonnes aggregated across destinations
    2. quarterly Australia production tonnes
    3. quarterly Australia slaughter values when available
    """
    exports_file_name = build_file_name(
        INPUT_EXPORTS_SINGLE,
        INPUT_EXPORTS_RANGE,
        INPUT_EXPORTS_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    production_file_name = build_file_name(
        INPUT_PRODUCTION_SINGLE,
        INPUT_PRODUCTION_RANGE,
        INPUT_PRODUCTION_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    exports_path = PROCESSED_DIR / exports_file_name
    production_path = PROCESSED_DIR / production_file_name

    if not exports_path.exists():
        raise FileNotFoundError(f"Quarterly exports file not found: {exports_path}")

    if not production_path.exists():
        raise FileNotFoundError(f"Cleaned production file not found: {production_path}")

    exports_q = pd.read_csv(exports_path)
    production = pd.read_csv(production_path)

    exports_summary = (
        exports_q[exports_q["product"].isin(["beef", "lamb"])]
        .groupby(["quarter", "product"], as_index=False)["tonnes"]
        .sum()
        .rename(columns={"tonnes": "exports_tonnes"})
    )

    production_summary = (
        production[
            (production["metric_group"] == "production")
            & (production["unit"] == "tonnes")
            & (production["state"] == "Australia")
            & (production["product"].isin(["beef", "lamb"]))
        ]
        .groupby(["quarter", "product"], as_index=False)["value"]
        .sum()
        .rename(columns={"value": "production_tonnes"})
    )

    slaughter_summary = (
        production[
            (production["metric_group"] == "slaughter")
            & (production["state"] == "Australia")
            & (production["product"].isin(["beef", "lamb"]))
        ]
        .groupby(["quarter", "product"], as_index=False)["value"]
        .sum()
        .rename(columns={"value": "slaughter_value"})
    )

    market_summary = (
        exports_summary.merge(
            production_summary,
            on=["quarter", "product"],
            how="outer",
        )
        .merge(
            slaughter_summary,
            on=["quarter", "product"],
            how="left",
        )
        .sort_values(["quarter", "product"])
        .reset_index(drop=True)
    )

    output_file_name = build_file_name(
        OUTPUT_SINGLE,
        OUTPUT_RANGE,
        OUTPUT_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    output_path = PROCESSED_DIR / output_file_name
    market_summary.to_csv(output_path, index=False)

    print(f"Saved market summary data to: {output_path}")
    return market_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a quarterly market summary from cleaned production and exports."
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

    build_market_summary(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )


if __name__ == "__main__":
    main()
