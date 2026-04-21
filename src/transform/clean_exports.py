from pathlib import Path
from typing import Optional
import re

import pandas as pd


# Define project level paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_BASE_DIR = PROJECT_ROOT / "data" / "raw" / "exports"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

# Keep only the main business metrics needed for the first dashboard version
KEEP_METRICS = [
    "Beef & Veal Total",
    "Total Lamb",
    "Total Mutton",
    "Total Meats",
]

# Map export columns to business metadata
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

OUTPUT_FILE_NAME_SINGLE = "exports_clean_{month}.csv"
OUTPUT_FILE_NAME_ALL = "exports_clean_all.csv"


def get_month_dirs(base_dir: Path, month: Optional[str] = None) -> list[Path]:
    """
    Return a list of month folders to process.

    If a month is provided, only that folder is returned.
    If no month is provided, all month folders under the base directory are returned.
    """
    if month:
        target_dir = base_dir / month
        if not target_dir.exists() or not target_dir.is_dir():
            raise FileNotFoundError(f"Month folder not found: {target_dir}")
        return [target_dir]

    month_dirs = sorted([path for path in base_dir.iterdir() if path.is_dir()])
    if not month_dirs:
        raise FileNotFoundError(f"No month folders found under: {base_dir}")
    return month_dirs


def extract_report_month(title: str) -> pd.Timestamp:
    """
    Extract the report month from the first title row.

    Example title:
    '57 Destination Report December 2025'

    The function returns:
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


def clean_one_file(file_path: Path, folder_month: str) -> pd.DataFrame:
    """
    Clean a single DAFF export workbook.

    Processing steps:
    1. Read the title row to extract the report month.
    2. Read the main report table.
    3. Standardize the destination column.
    4. Keep only selected metric columns.
    5. Convert the wide table into a long table.
    6. Add product, metric group, and unit metadata.
    7. Return a cleaned DataFrame.
    """
    # Read the raw sheet first so the title row can be inspected
    raw = pd.read_excel(file_path, sheet_name="Report", header=None)
    title = raw.iloc[0, 0]
    report_month = extract_report_month(title)

    # Read the report table with the second row as header
    df = pd.read_excel(file_path, sheet_name="Report", header=1)
    df = df.dropna(how="all").copy()

    # Rename the first column as destination
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "destination"})

    # Standardize destination values
    df["destination"] = df["destination"].astype(str).str.strip()

    # Remove empty rows and country total rows
    df = df[df["destination"] != ""].copy()
    df = df[df["destination"] != "Total Aus"].copy()

    # Keep only the metric columns needed for the first version
    available_metrics = [col for col in KEEP_METRICS if col in df.columns]
    if not available_metrics:
        raise ValueError(f"No expected metrics found in: {file_path.name}")

    df = df[["destination"] + available_metrics].copy()

    # Convert the wide table into a long table
    long_df = df.melt(
        id_vars="destination",
        var_name="metric_name",
        value_name="tonnes",
    )

    # Convert tonnage to numeric values and remove invalid rows
    long_df["tonnes"] = pd.to_numeric(long_df["tonnes"], errors="coerce")
    long_df = long_df.dropna(subset=["tonnes"]).copy()
    long_df = long_df[long_df["tonnes"] > 0].copy()

    # Add common metadata fields
    long_df["folder_month"] = folder_month
    long_df["report_month"] = report_month
    long_df["source_file"] = file_path.name

    # Map each metric column to product level metadata
    long_df["product"] = long_df["metric_name"].map(
        lambda x: METRIC_META_MAP[x]["product"]
    )
    long_df["metric_group"] = long_df["metric_name"].map(
        lambda x: METRIC_META_MAP[x]["metric_group"]
    )
    long_df["unit"] = long_df["metric_name"].map(
        lambda x: METRIC_META_MAP[x]["unit"]
    )

    # Select final columns and sort output for stable downstream processing
    result = long_df[
        [
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
    ].sort_values(["folder_month", "report_month", "product", "destination"])

    return result


def clean_exports(month: Optional[str] = None) -> pd.DataFrame:
    """
    Clean export data for one month or all available months.

    If month is provided, only that month folder is processed.
    If month is None, all month folders are processed.

    The final cleaned data is saved into the processed folder.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    frames = []
    month_dirs = get_month_dirs(RAW_BASE_DIR, month=month)

    for month_dir in month_dirs:
        for file_path in sorted(month_dir.glob("*.xlsx")):
            cleaned = clean_one_file(
                file_path=file_path,
                folder_month=month_dir.name,
            )
            frames.append(cleaned)

    if not frames:
        raise ValueError("No export files were found.")

    final_df = pd.concat(frames, ignore_index=True)

    output_file_name = (
        OUTPUT_FILE_NAME_SINGLE.format(month=month.replace("-", "_"))
        if month
        else OUTPUT_FILE_NAME_ALL
    )
    output_path = OUTPUT_DIR / output_file_name
    final_df.to_csv(output_path, index=False)

    print(f"Saved export data to: {output_path}")
    return final_df


if __name__ == "__main__":
    clean_exports()