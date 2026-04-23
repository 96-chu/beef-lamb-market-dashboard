import argparse

from transform.clean_exports import clean_exports
from transform.clean_production import clean_production


def main() -> None:
    """
    Run the data cleaning pipeline.

    Supported modes:
    1. Single release month
    2. Release month range
    3. All available release folders
    """
    parser = argparse.ArgumentParser(
        description="Run the data cleaning pipeline for production and export data."
    )

    parser.add_argument(
        "--release-month",
        type=str,
        default=None,
        help="Single release month to process, for example 2025-12",
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
    parser.add_argument(
        "--start-data-month",
        type=str,
        default=None,
        help="Start business data month to keep after cleaning, for example 2024-01",
    )
    parser.add_argument(
        "--end-data-month",
        type=str,
        default=None,
        help="End business data month to keep after cleaning, for example 2025-12",
    )

    args = parser.parse_args()

    clean_production(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
        start_data_month=args.start_data_month,
        end_data_month=args.end_data_month,
    )
    clean_exports(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
        start_data_month=args.start_data_month,
        end_data_month=args.end_data_month,
    )


if __name__ == "__main__":
    main()
