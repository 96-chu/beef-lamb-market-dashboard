from pathlib import Path
from typing import Optional

import pandas as pd


# Define project level paths.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_BASE_DIR = PROJECT_ROOT / "data" / "raw" / "production"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

# Map each ABS workbook to business metadata.
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

OUTPUT_FILE_NAME_SINGLE_ARCHIVE = "production_clean_archive_{release_month}.csv"
OUTPUT_FILE_NAME_RANGE_ARCHIVE = (
    "production_clean_archive_{start_release_month}_to_{end_release_month}.csv"
)
OUTPUT_FILE_NAME_ALL_ARCHIVE = "production_clean_archive_all.csv"

OUTPUT_FILE_NAME_SINGLE_LATEST = "production_clean_latest_{release_month}.csv"
OUTPUT_FILE_NAME_RANGE_LATEST = (
    "production_clean_latest_{start_release_month}_to_{end_release_month}.csv"
)
OUTPUT_FILE_NAME_ALL_LATEST = "production_clean_latest_all.csv"


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
            raise ValueError(
                "Start release month must be earlier than or equal to end release month."
            )

        selected_dirs = []
        for release_dir in all_release_dirs:
            release_ts = parse_release_month(release_dir.name)
            if start_ts <= release_ts <= end_ts:
                selected_dirs.append(release_dir)

        if not selected_dirs:
            raise FileNotFoundError(
                "No production release folders were found within the requested range."
            )

        return selected_dirs

    return all_release_dirs


def parse_description(text: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Split the ABS description string into measure, animal, and state.

    Example input:
    'Meat Produced; CATTLE (excl. calves); Queensland'
    """
    parts = [part.strip() for part in str(text).split(";") if str(part).strip()]
    measure = parts[0] if len(parts) > 0 else None
    animal = parts[1] if len(parts) > 1 else None
    state = parts[2] if len(parts) > 2 else None
    return measure, animal, state


def clean_one_file(file_path: Path, file_meta: dict, release_month: str) -> pd.DataFrame:
    """
    Clean a single ABS production workbook.

    Processing steps:
    1. Read the workbook from the Data1 sheet.
    2. Extract metadata rows such as description, series type, and series ID.
    3. Convert the wide table into a long table.
    4. Keep only Original series values.
    5. Add business metadata and quarter boundaries.
    """
    # Read the full sheet without assuming a fixed header.
    raw = pd.read_excel(file_path, sheet_name="Data1", header=None)

    # ABS metadata is stored in specific rows.
    descriptions = raw.iloc[0, 1:].to_dict()
    series_types = raw.iloc[2, 1:].to_dict()
    series_ids = raw.iloc[9, 1:].to_dict()

    # Actual time series data starts from row 10.
    data = raw.iloc[10:].copy()
    data = data.rename(columns={0: "date"})
    data = data[data["date"].notna()].copy()

    # Convert the wide table into a long table.
    long_df = data.melt(
        id_vars="date",
        var_name="column_index",
        value_name="value",
    )

    # Attach metadata back to each melted row.
    long_df["description"] = long_df["column_index"].map(descriptions)
    long_df["series_type"] = long_df["column_index"].map(series_types)
    long_df["series_id"] = long_df["column_index"].map(series_ids)

    # Keep only Original series to avoid duplicate business values.
    long_df = long_df[long_df["series_type"] == "Original"].copy()

    # Split description into business dimensions.
    parsed = long_df["description"].apply(parse_description)
    long_df["measure"] = parsed.apply(lambda x: x[0])
    long_df["animal"] = parsed.apply(lambda x: x[1])
    long_df["state"] = parsed.apply(lambda x: x[2])

    # Standardize state naming.
    long_df["state"] = long_df["state"].replace({"Total (State)": "Australia"})

    # Add file level business metadata.
    long_df["product"] = file_meta["product"]
    long_df["metric_group"] = file_meta["metric_group"]
    long_df["unit"] = file_meta["unit"]
    long_df["release_month"] = release_month
    long_df["period_type"] = "quarterly"
    long_df["source_file"] = file_path.name

    # Convert date and numeric values into standard types.
    long_df["date"] = pd.to_datetime(long_df["date"], errors="coerce")
    long_df["year"] = long_df["date"].dt.year

    quarter_period = long_df["date"].dt.to_period("Q")
    long_df["quarter"] = quarter_period.astype(str)
    long_df["quarter_start_date"] = quarter_period.dt.start_time.dt.strftime("%Y-%m-%d")
    long_df["quarter_end_date"] = quarter_period.dt.end_time.dt.strftime("%Y-%m-%d")

    long_df["value"] = pd.to_numeric(long_df["value"], errors="coerce")

    # Remove rows with missing critical fields.
    long_df = long_df.dropna(subset=["date", "value", "state"]).copy()
    long_df["date"] = long_df["date"].dt.strftime("%Y-%m-%d")

    # Select final columns and sort output for stable downstream processing.
    result = long_df[
        [
            "release_month",
            "date",
            "quarter",
            "quarter_start_date",
            "quarter_end_date",
            "year",
            "product",
            "metric_group",
            "unit",
            "period_type",
            "measure",
            "animal",
            "state",
            "series_type",
            "series_id",
            "value",
            "source_file",
        ]
    ].sort_values(
        ["release_month", "date", "product", "metric_group", "state", "series_id"]
    )

    return result


def deduplicate_production_to_latest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only the latest release for each production record.

    A production record is identified by date and series_id.
    When the same record appears in multiple release months,
    the row from the latest release month is kept.
    """
    deduped = df.copy()

    deduped["release_month_ts"] = pd.to_datetime(
        deduped["release_month"],
        format="%Y-%m",
        errors="coerce",
    )

    deduped = deduped.sort_values(
        ["date", "series_id", "release_month_ts"]
    )

    deduped = deduped.drop_duplicates(
        subset=["date", "series_id"],
        keep="last",
    ).copy()

    deduped = deduped.drop(columns=["release_month_ts"])

    deduped = deduped.sort_values(
        ["date", "product", "metric_group", "state", "series_id"]
    ).reset_index(drop=True)

    return deduped


def build_output_file_names(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> tuple[str, str]:
    """
    Build archive and latest output file names based on the selected release mode.
    """
    if release_month:
        token = release_month.replace("-", "_")
        return (
            OUTPUT_FILE_NAME_SINGLE_ARCHIVE.format(release_month=token),
            OUTPUT_FILE_NAME_SINGLE_LATEST.format(release_month=token),
        )

    if start_release_month and end_release_month:
        start_token = start_release_month.replace("-", "_")
        end_token = end_release_month.replace("-", "_")
        return (
            OUTPUT_FILE_NAME_RANGE_ARCHIVE.format(
                start_release_month=start_token,
                end_release_month=end_token,
            ),
            OUTPUT_FILE_NAME_RANGE_LATEST.format(
                start_release_month=start_token,
                end_release_month=end_token,
            ),
        )

    return OUTPUT_FILE_NAME_ALL_ARCHIVE, OUTPUT_FILE_NAME_ALL_LATEST


def clean_production(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> pd.DataFrame:
    """
    Clean production data for one release month, a release range, or all available releases.

    Two outputs are written:
    1. archive: all cleaned rows from all selected releases
    2. latest: deduplicated rows that keep only the latest release per record

    The function returns the latest deduplicated DataFrame because
    that is the dataset intended for downstream analysis.
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
            file_meta = FILE_META_MAP.get(file_path.stem)
            if file_meta is None:
                print(f"Skip unsupported file: {file_path.name}")
                continue

            cleaned = clean_one_file(
                file_path=file_path,
                file_meta=file_meta,
                release_month=release_dir.name,
            )
            frames.append(cleaned)

    if not frames:
        raise ValueError("No supported production files were found.")

    archive_df = pd.concat(frames, ignore_index=True)
    latest_df = deduplicate_production_to_latest(archive_df)

    archive_file_name, latest_file_name = build_output_file_names(
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    archive_output_path = OUTPUT_DIR / archive_file_name
    latest_output_path = OUTPUT_DIR / latest_file_name

    archive_df.to_csv(archive_output_path, index=False)
    latest_df.to_csv(latest_output_path, index=False)

    print(f"Saved production archive data to: {archive_output_path}")
    print(f"Saved production latest data to: {latest_output_path}")

    return latest_df


if __name__ == "__main__":
    clean_production()