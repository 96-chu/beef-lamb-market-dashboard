from pathlib import Path
from typing import Optional

import pandas as pd


# Define project level paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_BASE_DIR = PROJECT_ROOT / "data" / "raw" / "production"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

# Map each ABS file to business metadata
# 7215003 and 7215006 are slaughter related files
# 7215009 and 7215012 are meat production related files
FILE_META_MAP = {
    "7215003": {
        "product": "beef",
        "metric_group": "slaughter",
        "unit": "head",
    },
    "7215006": {
        "product": "lamb",
        "metric_group": "slaughter",
        "unit": "head",
    },
    "7215009": {
        "product": "beef",
        "metric_group": "production",
        "unit": "tonnes",
    },
    "7215012": {
        "product": "lamb",
        "metric_group": "production",
        "unit": "tonnes",
    },
}

OUTPUT_FILE_NAME_SINGLE = "production_clean_{month}.csv"
OUTPUT_FILE_NAME_ALL = "production_clean_all.csv"


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


def parse_description(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Split the ABS description string into measure, animal, and state.

    Example input:
    'Meat Produced; CATTLE (excl. calves); Queensland'

    Example output:
    ('Meat Produced', 'CATTLE (excl. calves)', 'Queensland')
    """
    parts = [part.strip() for part in str(text).split(";") if str(part).strip()]
    measure = parts[0] if len(parts) > 0 else None
    animal = parts[1] if len(parts) > 1 else None
    state = parts[2] if len(parts) > 2 else None
    return measure, animal, state


def clean_one_file(file_path: Path, file_meta: dict, folder_month: str) -> pd.DataFrame:
    """
    Clean a single ABS production workbook.

    Processing steps:
    1. Read the workbook from the Data1 sheet.
    2. Extract metadata rows such as description, series type, and series ID.
    3. Convert the wide table into a long table.
    4. Keep only Original series values.
    5. Add business metadata such as product, metric group, and unit.
    6. Standardize date and numeric columns.
    7. Return a cleaned DataFrame.
    """
    # Read the full sheet without assuming a fixed header
    raw = pd.read_excel(file_path, sheet_name="Data1", header=None)

    # ABS metadata is stored in specific rows
    # Row 0 contains description
    # Row 2 contains series type
    # Row 9 contains series ID
    descriptions = raw.iloc[0, 1:].to_dict()
    series_types = raw.iloc[2, 1:].to_dict()
    series_ids = raw.iloc[9, 1:].to_dict()

    # Actual time series data starts from row 10
    # Column 0 is the date column
    data = raw.iloc[10:].copy()
    data = data.rename(columns={0: "date"})
    data = data[data["date"].notna()].copy()

    # Convert the wide table into a long table
    # Each original data column becomes one row group
    long_df = data.melt(
        id_vars="date",
        var_name="column_index",
        value_name="value",
    )

    # Attach metadata back to each melted row
    long_df["description"] = long_df["column_index"].map(descriptions)
    long_df["series_type"] = long_df["column_index"].map(series_types)
    long_df["series_id"] = long_df["column_index"].map(series_ids)

    # Keep only Original series to avoid duplicate business values
    long_df = long_df[long_df["series_type"] == "Original"].copy()

    # Split description into business dimensions
    parsed = long_df["description"].apply(parse_description)
    long_df["measure"] = parsed.apply(lambda x: x[0])
    long_df["animal"] = parsed.apply(lambda x: x[1])
    long_df["state"] = parsed.apply(lambda x: x[2])

    # Standardize state naming
    long_df["state"] = long_df["state"].replace({"Total (State)": "Australia"})

    # Add file level business metadata
    long_df["product"] = file_meta["product"]
    long_df["metric_group"] = file_meta["metric_group"]
    long_df["unit"] = file_meta["unit"]
    long_df["folder_month"] = folder_month
    long_df["source_file"] = file_path.name

    # Convert date and numeric values into standard types
    long_df["date"] = pd.to_datetime(long_df["date"], errors="coerce")
    long_df["year"] = long_df["date"].dt.year
    long_df["quarter"] = long_df["date"].dt.to_period("Q").astype(str)

    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")

    # Remove rows with missing critical fields
    long_df = long_df.dropna(subset=["date", "value", "state"]).copy()

    # Select final columns and sort output for stable downstream processing
    result = long_df[
        [
            "folder_month",
            "date",
            "quarter",
            "year",
            "product",
            "metric_group",
            "unit",
            "measure",
            "animal",
            "state",
            "series_type",
            "series_id",
            "value",
            "source_file",
        ]
    ].sort_values(["folder_month", "date", "product", "metric_group", "state"])

    return result


def clean_production(month: Optional[str] = None) -> pd.DataFrame:
    """
    Clean production data for one month or all available months.

    If month is provided, only that month folder is processed.
    If month is None, all month folders are processed.

    The final cleaned data is saved into the processed folder.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    frames = []
    month_dirs = get_month_dirs(RAW_BASE_DIR, month=month)

    for month_dir in month_dirs:
        for file_path in sorted(month_dir.glob("*.xlsx")):
            file_meta = FILE_META_MAP.get(file_path.stem)
            if file_meta is None:
                print(f"Skip unsupported file: {file_path.name}")
                continue

            cleaned = clean_one_file(
                file_path=file_path,
                file_meta=file_meta,
                folder_month=month_dir.name,
            )
            frames.append(cleaned)

    if not frames:
        raise ValueError("No supported production files were found.")

    final_df = pd.concat(frames, ignore_index=True)

    output_file_name = (
        OUTPUT_FILE_NAME_SINGLE.format(month=month.replace("-", "_"))
        if month
        else OUTPUT_FILE_NAME_ALL
    )
    output_path = OUTPUT_DIR / output_file_name
    final_df.to_csv(output_path, index=False)

    print(f"Saved production data to: {output_path}")
    return final_df


if __name__ == "__main__":
    clean_production()