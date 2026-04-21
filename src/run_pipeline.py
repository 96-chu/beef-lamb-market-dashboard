import argparse

from transform.clean_exports import clean_exports
from transform.clean_production import clean_production


def main() -> None:
    """
    Run the data cleaning pipeline.

    If a month is provided, only that month folder is processed.
    If no month is provided, all month folders are processed.
    """
    parser = argparse.ArgumentParser(
        description="Run the data cleaning pipeline for production and export data."
    )
    parser.add_argument(
        "--month",
        type=str,
        default=None,
        help="Month folder to process, for example 2025-12",
    )
    args = parser.parse_args()

    clean_production(month=args.month)
    clean_exports(month=args.month)


if __name__ == "__main__":
    main()