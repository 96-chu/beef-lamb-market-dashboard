from pathlib import Path
from typing import Optional
import argparse

import pandas as pd


# Define project level paths.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

INPUT_FILE_NAME_SINGLE = "exports_clean_{release_month}.csv"
INPUT_FILE_NAME_RANGE = "exports_clean_{start_release_month}_to_{end_release_month}.csv"
INPUT_FILE_NAME_ALL = "exports_clean_all.csv"

OUTPUT_FILE_NAME_SINGLE = "exports_quarterly_{release_month}.csv"
OUTPUT_FILE_NAME_RANGE = "exports_quarterly_{start_release_month}_to_{end_release_month}.csv"
OUTPUT_FILE_NAME_ALL = "exports_quarterly_all.csv"


def build_input_file_name(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> str:
    """
    Build the cleaned monthly export input file name.

    The input file must already exist in the processed folder.
    """
    if release_month:
        return INPUT_FILE_NAME_SINGLE.format(
            release_month=release_month.replace("-", "_")
        )

    if start_release_month and end_release_month:
        return INPUT_FILE_NAME_RANGE.format(
            start_release_month=start_release_month.replace("-", "_"),
            end_release_month=end_release_month.replace("-", "_"),
        )

    return INPUT_FILE_NAME_ALL


def build_output_file_name(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> str:
    """
    Build the quarterly export output file name.
    """
    if release_month:
        return OUTPUT_FILE_NAME_SINGLE.format(
            release_month=release_month.replace("-", "_")
        )

    if start_release_month and end_release_month:
        return OUTPUT_FILE_NAME_RANGE.format(
            start_release_month=start_release_month.replace("-", "_"),
            end_release_month=end_release_month.replace("-", "_"),
        )

    return OUTPUT_FILE_NAME_ALL


def validate_required_columns(df: pd.DataFrame) -> None:
    """
    Validate that the cleaned export file contains the required columns.
    """
    required_columns = {
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
    }

    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in cleaned exports file: {sorted(missing_columns)}"
        )


def build_exports_quarterly(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> pd.DataFrame:
    """
    Aggregate cleaned monthly export data into quarterly export data.

    Business rules:
    1. Only monthly flow data is used.
    2. Cumulative YTD data is excluded.
    3. Quarterly totals are grouped by destination, product, metric group, and unit.
    4. The output includes month coverage fields to show whether a quarter is complete.
    """
    input_file_name = build_input_file_name(
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    input_path = PROCESSED_DIR / input_file_name

    if not input_path.exists():
        raise FileNotFoundError(f"Cleaned export file not found: {input_path}")

    df = pd.read_csv(input_path)
    validate_required_columns(df)

    # Convert report month into a true datetime field.
    df["report_month"] = pd.to_datetime(df["report_month"], errors="coerce")
    df["tonnes"] = pd.to_numeric(df["tonnes"], errors="coerce")
    df["is_cumulative"] = pd.to_numeric(df["is_cumulative"], errors="coerce")

    # Keep only valid monthly flow records for quarterly aggregation.
    df = df.dropna(subset=["report_month", "tonnes"]).copy()
    df = df[df["report_scope"] == "monthly_flow"].copy()
    df = df[df["is_cumulative"] == 0].copy()

    if df.empty:
        raise ValueError(
            "No monthly flow export records were found. "
            "Make sure the cleaned export file was built from monthly export data."
        )

    # Rebuild time attributes from report_month to ensure consistency.
    quarter_period = df["report_month"].dt.to_period("Q")
    df["year"] = df["report_month"].dt.year
    df["quarter"] = quarter_period.astype(str)
    df["quarter_start_date"] = quarter_period.dt.start_time.dt.strftime("%Y-%m-%d")
    df["quarter_end_date"] = quarter_period.dt.end_time.dt.strftime("%Y-%m-%d")
    df["report_month_str"] = df["report_month"].dt.strftime("%Y-%m-%d")

    # Aggregate monthly rows into quarterly totals.
    grouped = (
        df.groupby(
            [
                "year",
                "quarter",
                "quarter_start_date",
                "quarter_end_date",
                "destination",
                "product",
                "metric_group",
                "unit",
            ],
            as_index=False,
        )
        .agg(
            tonnes=("tonnes", "sum"),
            min_report_month=("report_month_str", "min"),
            max_report_month=("report_month_str", "max"),
            months_included=("report_month_str", "nunique"),
            source_file_count=("source_file", "nunique"),
        )
    )

    # Add quarterly metadata fields for downstream reporting.
    grouped["period_type"] = "quarterly"
    grouped["report_scope"] = "quarterly_sum_from_monthly_flow"
    grouped["is_cumulative"] = 0
    grouped["is_complete_quarter"] = (grouped["months_included"] == 3).astype(int)

    result = grouped[
        [
            "year",
            "quarter",
            "quarter_start_date",
            "quarter_end_date",
            "destination",
            "product",
            "metric_group",
            "unit",
            "period_type",
            "report_scope",
            "is_cumulative",
            "months_included",
            "is_complete_quarter",
            "min_report_month",
            "max_report_month",
            "source_file_count",
            "tonnes",
        ]
    ].sort_values(["quarter", "product", "destination"]).reset_index(drop=True)

    output_file_name = build_output_file_name(
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    output_path = PROCESSED_DIR / output_file_name
    result.to_csv(output_path, index=False)

    print(f"Saved quarterly export data to: {output_path}")
    return result


def main() -> None:
    """
    Build quarterly export data from cleaned monthly export data.

    Supported modes:
    1. Single release month
    2. Release month range
    3. All available cleaned data
    """
    parser = argparse.ArgumentParser(
        description="Aggregate cleaned monthly export data into quarterly export data."
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
        help="Start release month for a range, for example 2025-07",
    )
    parser.add_argument(
        "--end-release-month",
        type=str,
        default=None,
        help="End release month for a range, for example 2025-12",
    )

    args = parser.parse_args()

    if args.release_month and (
        args.start_release_month or args.end_release_month
    ):
        raise ValueError(
            "Use either --release-month or a start and end release month range, not both."
        )

    if (args.start_release_month and not args.end_release_month) or (
        args.end_release_month and not args.start_release_month
    ):
        raise ValueError(
            "Both --start-release-month and --end-release-month must be provided together."
        )

    build_exports_quarterly(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )


if __name__ == "__main__":
    main()