import argparse

from build_forecast import build_forecast
from build_insights import build_insights
from build_market_summary import build_market_summary
from build_report_charts import build_report_charts
from export_dashboard_assets import export_dashboard_assets
from transform.build_exports_quarterly import build_exports_quarterly
from transform.clean_exports import clean_exports
from transform.clean_production import clean_production


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the reporting pipeline from raw files through cleaned outputs, "
            "quarterly summary tables, and final PNG charts."
        )
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
    parser.add_argument(
        "--forecast-year",
        type=int,
        default=None,
        help="Forecast year for the business outlook. Defaults to the next year after the latest data.",
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
    build_exports_quarterly(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )
    build_market_summary(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )
    build_report_charts(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )
    build_insights(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
    )
    build_forecast(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
        forecast_year=args.forecast_year,
    )
    if args.start_release_month and args.end_release_month:
        export_dashboard_assets(
            start_release_month=args.start_release_month,
            end_release_month=args.end_release_month,
            forecast_year=args.forecast_year,
        )


if __name__ == "__main__":
    main()
