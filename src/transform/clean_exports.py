from pathlib import Path
from typing import Optional
import re

import pandas as pd


# Define project level paths.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_BASE_DIR = PROJECT_ROOT / "data" / "raw" / "exports"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

# Keep only the main metrics needed for the current dashboard version.
KEEP_METRICS = [
    "Beef & Veal Total",
    "Total Lamb",
    "Total Mutton",
    "Total Meats",
]

EXCLUDED_DESTINATION_PATTERNS = (
    r"^Total\s+",
    r"^Other\s+",
)
EXCLUDED_DESTINATION_VALUES = {
    "All Other Countries",
}
# Map report columns to business metadata.
METRIC_META_MAP = {
    "Beef & Veal Total": {
        "product": "beef",
        "metric_group": "export_volume",
        "unit": "tonnes",
    },
    "Total Lamb": {
        "product": "lamb",
        "metric_group": "export_volume",
        "unit": "tonnes",
    },
    "Total Mutton": {
        "product": "mutton",
        "metric_group": "export_volume",
        "unit": "tonnes",
    },
    "Total Meats": {
        "product": "all_meat",
        "metric_group": "export_volume",
        "unit": "tonnes",
    },
}

OUTPUT_FILE_NAME_SINGLE = "exports_clean_{release_month}.csv"
OUTPUT_FILE_NAME_RANGE = "exports_clean_{start_release_month}_to_{end_release_month}.csv"
OUTPUT_FILE_NAME_ALL = "exports_clean_all.csv"


def parse_release_month(token: str) -> pd.Timestamp:
    """
    Parse a release month token such as 2025-12.

    The function returns a normalized month start timestamp.
    """
    try:
        return pd.to_datetime(token, format="%Y-%m")
    except ValueError as exc:
        raise ValueError(
            f"Invalid release month format: {token}. Expected YYYY-MM."
        ) from exc


def parse_data_month(token: str) -> pd.Timestamp:
    """
    Parse a business data month token such as 2025-12.

    The function returns the normalized first day of the month.
    """
    try:
        return pd.to_datetime(token, format="%Y-%m")
    except ValueError as exc:
        raise ValueError(
            f"Invalid data month format: {token}. Expected YYYY-MM."
        ) from exc


def get_release_dirs(
    base_dir: Path,
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> list[Path]:
    """
    Return release folders based on one of three modes.

    Mode 1:
    A single release month is provided.

    Mode 2:
    A start and end release month are provided.

    Mode 3:
    No release filters are provided, so all folders are returned.
    """
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

    if release_month:
        target_dir = base_dir / release_month
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(f"Release folder not found: {target_dir}")
        return [target_dir]

    all_release_dirs = sorted([path for path in base_dir.iterdir() if path.is_dir()])
    if not all_release_dirs:
        raise FileNotFoundError(f"No release folders found under: {base_dir}")

    if start_release_month and end_release_month:
        start_ts = parse_release_month(start_release_month)
        end_ts = parse_release_month(end_release_month)

        if start_ts > end_ts:
            raise ValueError("Start release month must be earlier than or equal to end release month.")

        selected_dirs = []
        for release_dir in all_release_dirs:
            release_ts = parse_release_month(release_dir.name)
            if start_ts <= release_ts <= end_ts:
                selected_dirs.append(release_dir)

        if not selected_dirs:
            raise FileNotFoundError(
                "No export release folders were found within the requested range."
            )

        return selected_dirs

    return all_release_dirs


def extract_report_month(title: str) -> pd.Timestamp:
    """
    Extract the business report month from the workbook title row.

    Example title:
    '57 Destination Report December 2025'

    Returns:
    Timestamp('2025-12-01 00:00:00')
    """
    match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})",
        str(title),
    )
    if not match:
        raise ValueError(f"Could not parse report month from title: {title}")

    month_text = match.group(1)
    year_text = match.group(2)
    return pd.to_datetime(f"01 {month_text} {year_text}", format="%d %B %Y")


def infer_report_scope(file_name: str) -> tuple[str, int, str]:
    """
    Infer the report scope from the DAFF file name.

    Common file patterns:
    1. m57dest: monthly flow
    2. c57dest: calendar year to date
    3. f57dest: fiscal year to date

    Returns:
    report_scope, is_cumulative, period_type
    """
    lower_name = file_name.lower()

    if "m57dest" in lower_name:
        return "monthly_flow", 0, "monthly"

    if "c57dest" in lower_name:
        return "calendar_ytd", 1, "monthly_release"

    if "f57dest" in lower_name:
        return "fiscal_ytd", 1, "monthly_release"

    return "unknown", 0, "unknown"


def resolve_report_sheet_name(file_path: Path) -> str:
    """
    Resolve the worksheet that contains the destination report.

    Most files use a sheet named Report. A small number of older files use
    a single generic sheet name such as Sheet1, so we fall back to the only
    available worksheet when Report is missing.
    """
    workbook = pd.ExcelFile(file_path)
    sheet_names = workbook.sheet_names

    if "Report" in sheet_names:
        return "Report"

    if len(sheet_names) == 1:
        return sheet_names[0]

    raise ValueError(
        f"Could not resolve report worksheet for {file_path.name}. "
        f"Available sheets: {sheet_names}"
    )


def clean_one_file(file_path: Path, release_month: str) -> pd.DataFrame:
    """
    Clean a single DAFF export workbook.

    Processing steps:
    1. Read the title row to extract the business report month.
    2. Infer the report scope from the file name.
    3. Read the main report table.
    4. Keep required metric columns.
    5. Convert the wide table into a long table.
    6. Add business metadata used in downstream analysis.
    """
    sheet_name = resolve_report_sheet_name(file_path)

    # Read the workbook without headers first to inspect the title row.
    raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    title = raw.iloc[0, 0]
    report_month = extract_report_month(title)

    # Infer whether the file is monthly flow or cumulative YTD.
    report_scope, is_cumulative, period_type = infer_report_scope(file_path.name)

    # Read the report table using the second row as the header row.
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=1)
    df = df.dropna(how="all").copy()
    df.columns = [
        re.sub(r"\s+", " ", str(col)).strip()
        for col in df.columns
    ]

    # Rename the first column to destination.
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "destination"})

    # Standardize destination values.
    df["destination"] = df["destination"].astype(str).str.strip()

    # Remove empty rows and the total Australia row.
    df = df[df["destination"] != ""].copy()
    df = df[df["destination"] != "Total Aus"].copy()
    df = df[~df["destination"].isin(EXCLUDED_DESTINATION_VALUES)].copy()
    df = df[
        ~df["destination"].str.contains(
            "|".join(EXCLUDED_DESTINATION_PATTERNS),
            case=False,
            regex=True,
            na=False,
        )
    ].copy()

    # Keep only the selected metric columns.
    available_metrics = [col for col in KEEP_METRICS if col in df.columns]
    if not available_metrics:
        raise ValueError(f"No expected metrics found in: {file_path.name}")

    df = df[["destination"] + available_metrics].copy()

    # Convert the wide table into a long table.
    long_df = df.melt(
        id_vars="destination",
        var_name="metric_name",
        value_name="tonnes",
    )

    # Convert values to numeric and remove invalid rows.
    long_df["tonnes"] = pd.to_numeric(long_df["tonnes"], errors="coerce")
    long_df = long_df.dropna(subset=["tonnes"]).copy()
    long_df = long_df[long_df["tonnes"] > 0].copy()

    # Add release month and business period fields.
    long_df["release_month"] = release_month
    long_df["report_month"] = report_month.strftime("%Y-%m-%d")
    long_df["year"] = report_month.year
    long_df["quarter"] = f"{report_month.year}Q{report_month.quarter}"
    long_df["period_type"] = period_type
    long_df["report_scope"] = report_scope
    long_df["is_cumulative"] = is_cumulative
    long_df["source_file"] = file_path.name

    # Map business metadata from metric columns.
    long_df["product"] = long_df["metric_name"].map(
        lambda x: METRIC_META_MAP[x]["product"]
    )
    long_df["metric_group"] = long_df["metric_name"].map(
        lambda x: METRIC_META_MAP[x]["metric_group"]
    )
    long_df["unit"] = long_df["metric_name"].map(
        lambda x: METRIC_META_MAP[x]["unit"]
    )

    # Select final output columns.
    result = long_df[
        [
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
    ].sort_values(["report_month", "product", "destination"])

    return result


def build_output_file_name(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> str:
    """
    Build the output file name based on the selected release mode.
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


def deduplicate_exports_to_latest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep the latest release for each export record.

    A business record is identified by report_month, destination, and metric_name.
    If the same report month appears in multiple release folders, the row from the
    latest release month is kept.
    """
    deduped = df.copy()
    deduped["release_month_ts"] = pd.to_datetime(
        deduped["release_month"],
        format="%Y-%m",
        errors="coerce",
    )
    deduped["report_month_ts"] = pd.to_datetime(
        deduped["report_month"],
        errors="coerce",
    )

    deduped = deduped.sort_values(
        ["report_month_ts", "destination", "metric_name", "release_month_ts"]
    )

    deduped = deduped.drop_duplicates(
        subset=["report_month", "destination", "metric_name"],
        keep="last",
    ).copy()

    deduped = deduped.drop(columns=["release_month_ts", "report_month_ts"])
    deduped = deduped.sort_values(
        ["report_month", "product", "destination", "metric_name"]
    ).reset_index(drop=True)
    return deduped


def filter_exports_to_data_window(
    df: pd.DataFrame,
    start_data_month: Optional[str] = None,
    end_data_month: Optional[str] = None,
) -> pd.DataFrame:
    """
    Filter cleaned export rows to the requested business data month window.
    """
    if start_data_month is None and end_data_month is None:
        return df

    if (start_data_month and not end_data_month) or (
        end_data_month and not start_data_month
    ):
        raise ValueError(
            "Both --start-data-month and --end-data-month must be provided together."
        )

    start_ts = parse_data_month(start_data_month)
    end_ts = parse_data_month(end_data_month)

    if start_ts > end_ts:
        raise ValueError("Start data month must be earlier than or equal to end data month.")

    filtered = df.copy()
    filtered["report_month_ts"] = pd.to_datetime(
        filtered["report_month"],
        errors="coerce",
    )
    end_month_ts = end_ts + pd.offsets.MonthEnd(1)

    filtered = filtered[
        filtered["report_month_ts"].between(start_ts, end_month_ts)
    ].copy()

    filtered = filtered.drop(columns=["report_month_ts"])
    filtered = filtered.sort_values(
        ["report_month", "product", "destination", "metric_name"]
    ).reset_index(drop=True)
    return filtered


def clean_exports(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
    start_data_month: Optional[str] = None,
    end_data_month: Optional[str] = None,
) -> pd.DataFrame:
    """
    Clean export data for one release month, a release range, or all available releases.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    frames = []
    release_dirs = get_release_dirs(
        RAW_BASE_DIR,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    for release_dir in release_dirs:
        for file_path in sorted(release_dir.glob("*.xlsx")):
            cleaned = clean_one_file(
                file_path=file_path,
                release_month=release_dir.name,
            )
            frames.append(cleaned)

    if not frames:
        raise ValueError("No export files were found.")

    final_df = pd.concat(frames, ignore_index=True)
    final_df = deduplicate_exports_to_latest(final_df)
    final_df = filter_exports_to_data_window(
        final_df,
        start_data_month=start_data_month,
        end_data_month=end_data_month,
    )

    output_file_name = build_output_file_name(
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    output_path = OUTPUT_DIR / output_file_name
    final_df.to_csv(output_path, index=False)

    print(f"Saved export data to: {output_path}")
    return final_df


if __name__ == "__main__":
    clean_exports()
