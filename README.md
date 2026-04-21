# Australian Beef and Lamb Market Dashboard

## Project Overview

This project builds a small business intelligence pipeline for the Australian beef and lamb market.

The pipeline does four things:

1. Read official raw Excel files
2. Clean and standardize production and export data with Python
3. Load cleaned data into SQLite
4. Prepare the dataset for downstream SQL analysis and Power BI dashboards

The current project focuses on a simple first version that is easy to run, inspect, and extend.

## Project Structure

```text
data/
  raw/
    exports/
      2025-12/
        2512_c57dest.xlsx
    production/
      2025-12/
        7215003.xlsx
        7215006.xlsx
        7215009.xlsx
        7215012.xlsx
  processed/

src/
  load/
    load_to_sqlite.py
  transform/
    __init__.py
    clean_exports.py
    clean_production.py
  run_pipeline.py

sql/
  schema.sql

dashboard/
docs/
README.md
environment.yml
```

## Environment Setup

Create the conda environment:

```bash
conda env create -f environment.yml
conda activate meat-bi
```

## Run the Cleaning Pipeline

Run one month only:

```bash
python src/run_pipeline.py --month 2025-12
```

Run all available month folders:

```bash
python src/run_pipeline.py
```

## Load Cleaned Data into SQLite

Load one month only:

```bash
python src/load/load_to_sqlite.py --month 2025-12
```

Load all cleaned files:

```bash
python src/load/load_to_sqlite.py
```

The default database file is:

```text
data/processed/meat_market.db
```

## Raw Data Sources

### 1. ABS production and slaughter data

The production raw files come from the Australian Bureau of Statistics release **Livestock Products, Australia**.

This release provides quarterly time series spreadsheets for livestock slaughtered and meat produced.

The first version of this project uses the following ABS tables:

- Table 3. Livestock slaughtered, cattle excluding calves
- Table 6. Livestock slaughtered, lambs
- Table 9. Red meat produced, beef
- Table 12. Red meat produced, lamb

These workbooks include multiple series types such as Original, Seasonally Adjusted, and Trend.
This project keeps only the **Original** series.

These files are stored under:

```text
data/raw/production/YYYY-MM/
```

### 2. DAFF export data

The export raw files come from the Department of Agriculture, Fisheries and Forestry page **Australian red meat export statistics**.

The DAFF site publishes monthly Excel reports in several formats, including:

- Exports by State of Production
- 57 Destination Report
- Exports by Load Port
- Comparison Table
- Air Freight
- Processed Meat Exports

The first version of this project uses the **57 Destination Report** file:

```text
2512_c57dest.xlsx
```

This file is stored under:

```text
data/raw/exports/YYYY-MM/
```

## Raw File Interpretation

### ABS workbook interpretation

The ABS files used in this project are structured as time series spreadsheets.

Important notes:

- The `Data1` sheet contains the main time series table
- Metadata rows include description, series type, and series ID
- Actual data starts below the metadata rows
- Each workbook contains multiple states and an Australia total
- Production files and slaughter files use different business units

In this project:

- `7215003.xlsx` is treated as beef slaughter
- `7215006.xlsx` is treated as lamb slaughter
- `7215009.xlsx` is treated as beef production
- `7215012.xlsx` is treated as lamb production

### DAFF workbook interpretation

The DAFF export workbook used in this project is a destination level export report.

Important notes:

- The `Report` sheet contains the report table
- The first row contains the title, which includes the report month
- The second row contains the column headers
- The first column is the export destination
- The report includes a `Total Aus` row, which should be removed during cleaning

For the first project version, the pipeline keeps only these columns:

- `Beef & Veal Total`
- `Total Lamb`
- `Total Mutton`
- `Total Meats`

## Important Reporting Note

The current export file:

```text
2512_c57dest.xlsx
```

is a **Calendar YTD** report, not a single month flow report.

This means the values represent cumulative exports for the calendar year up to December 2025.

If you want to build a dashboard for month by month export movement, you should switch to the `m57dest.xlsx` files instead of `c57dest.xlsx`.

## Output Files

After running the cleaning pipeline, the project writes cleaned CSV files into:

```text
data/processed/
```

Examples:

```text
production_clean_2025_12.csv
exports_clean_2025_12.csv
production_clean_all.csv
exports_clean_all.csv
```

After loading into SQLite, the database file is:

```text
data/processed/meat_market.db
```

## Current Design Choices

This first version keeps the model simple.

Main choices:

1. Keep only the Original ABS series
2. Keep only a small set of export columns for the first dashboard version
3. Store cleaned outputs as CSV before loading to SQLite
4. Use SQLite as a lightweight local analytical database
5. Keep product, state, and destination dimensions simple for easy Power BI use

## Main Scripts

### `src/run_pipeline.py`

This file is the main pipeline entry point.

Responsibilities:

- Accept an optional `--month` argument
- Run production and export cleaning in sequence
- Support both single month processing and full historical processing

### `src/transform/clean_production.py`

This file cleans ABS production and slaughter data.

Responsibilities:

- Scan month folders under `data/raw/production/`
- Read the `Data1` sheet from each ABS workbook
- Extract metadata such as description, series type, and series ID
- Convert the wide table into a long table
- Keep only the `Original` series
- Add `product`, `metric_group`, and `unit`
- Export standardized CSV files into `data/processed/`

### `src/transform/clean_exports.py`

This file cleans DAFF export data.

Responsibilities:

- Scan month folders under `data/raw/exports/`
- Read the `Report` sheet from each DAFF workbook
- Extract the report month from the title row
- Keep only the required columns for the first dashboard version
- Convert the wide table into a long table
- Add `product`, `metric_group`, and `unit`
- Export standardized CSV files into `data/processed/`

### `src/load/load_to_sqlite.py`

This file loads cleaned CSV data into SQLite.

Responsibilities:

- Read cleaned CSV files from `data/processed/`
- Execute the SQL schema in `sql/schema.sql`
- Build dimension tables
- Load fact tables
- Save a local database file for SQL checks and Power BI usage

### `sql/schema.sql`

This file defines the SQLite schema.

Responsibilities:

- Create dimension tables
- Create fact tables
- Add basic indexes for common analytical queries
- Reset tables for repeatable local reloads

## Next Steps

Planned next steps include:

1. Add more months of raw data
2. Add more DAFF report types such as state and load port
3. Expand product coverage
4. Build SQL validation queries
5. Connect SQLite tables to Power BI
6. Add dashboard screenshots and business insights
