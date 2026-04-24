from pathlib import Path
from typing import Callable, Optional
import argparse

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

EXPORTS_CLEAN_SINGLE = "exports_clean_{release_month}.csv"
EXPORTS_CLEAN_RANGE = "exports_clean_{start_release_month}_to_{end_release_month}.csv"
EXPORTS_CLEAN_ALL = "exports_clean_all.csv"

MARKET_SUMMARY_SINGLE = "market_quarterly_summary_{release_month}.csv"
MARKET_SUMMARY_RANGE = "market_quarterly_summary_{start_release_month}_to_{end_release_month}.csv"
MARKET_SUMMARY_ALL = "market_quarterly_summary_all.csv"

OUTPUT_SINGLE = "market_forecast_{release_month}_for_{forecast_year}.csv"
OUTPUT_RANGE = "market_forecast_{start_release_month}_to_{end_release_month}_for_{forecast_year}.csv"
OUTPUT_ALL = "market_forecast_all_for_{forecast_year}.csv"

CORE_PRODUCTS = ["beef", "lamb"]
SCENARIOS = ["conservative", "base", "high"]
MODEL_NAME = "linear_trend_seasonality"
MODEL_DETAIL = (
    "OLS trend model with month or quarter fixed effects; scenario bands use "
    "the larger of model residual error and the configured percentage band."
)


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


def build_output_file_name(
    forecast_year: int,
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> str:
    if release_month:
        return OUTPUT_SINGLE.format(
            release_month=release_month.replace("-", "_"),
            forecast_year=forecast_year,
        )

    if start_release_month and end_release_month:
        return OUTPUT_RANGE.format(
            start_release_month=start_release_month.replace("-", "_"),
            end_release_month=end_release_month.replace("-", "_"),
            forecast_year=forecast_year,
        )

    return OUTPUT_ALL.format(forecast_year=forecast_year)


def validate_release_mode(
    release_month: Optional[str],
    start_release_month: Optional[str],
    end_release_month: Optional[str],
) -> None:
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


def validate_exports(df: pd.DataFrame) -> None:
    required_columns = {
        "report_month",
        "product",
        "tonnes",
    }
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in cleaned exports file: {sorted(missing_columns)}"
        )


def validate_summary(df: pd.DataFrame) -> None:
    required_columns = {
        "quarter",
        "product",
        "exports_tonnes",
        "production_tonnes",
    }
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns in market summary file: {sorted(missing_columns)}"
        )


def load_inputs(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exports_path = PROCESSED_DIR / build_file_name(
        EXPORTS_CLEAN_SINGLE,
        EXPORTS_CLEAN_RANGE,
        EXPORTS_CLEAN_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    summary_path = PROCESSED_DIR / build_file_name(
        MARKET_SUMMARY_SINGLE,
        MARKET_SUMMARY_RANGE,
        MARKET_SUMMARY_ALL,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    if not exports_path.exists():
        raise FileNotFoundError(f"Cleaned export file not found: {exports_path}")

    if not summary_path.exists():
        raise FileNotFoundError(f"Market summary file not found: {summary_path}")

    exports = pd.read_csv(exports_path)
    summary = pd.read_csv(summary_path)

    validate_exports(exports)
    validate_summary(summary)

    exports["report_month"] = pd.to_datetime(exports["report_month"], errors="coerce")
    exports["tonnes"] = pd.to_numeric(exports["tonnes"], errors="coerce")
    exports = exports.dropna(subset=["report_month", "tonnes"]).copy()

    summary["exports_tonnes"] = pd.to_numeric(
        summary["exports_tonnes"], errors="coerce"
    )
    summary["production_tonnes"] = pd.to_numeric(
        summary["production_tonnes"], errors="coerce"
    )
    summary = summary.dropna(subset=["quarter", "production_tonnes"]).copy()

    return exports, summary


def month_distance(period: pd.Period, base_period: pd.Period) -> int:
    return (period.year - base_period.year) * 12 + period.month - base_period.month


def quarter_distance(period: pd.Period, base_period: pd.Period) -> int:
    return (period.year - base_period.year) * 4 + period.quarter - base_period.quarter


def design_matrix(
    time_index: np.ndarray,
    seasons: np.ndarray,
    season_order: list[int],
) -> np.ndarray:
    columns = [np.ones(len(time_index)), time_index.astype(float)]
    for season in season_order[1:]:
        columns.append((seasons == season).astype(float))
    return np.column_stack(columns)


def predict_seasonal_trend(
    history: pd.DataFrame,
    future_periods: list[pd.Period],
    value_col: str,
    period_col: str,
    season_col: str,
    season_order: list[int],
    distance_fn: Callable[[pd.Period, pd.Period], int],
) -> tuple[np.ndarray, float]:
    if len(history) < 6:
        raise ValueError("At least six historical periods are required for forecasting.")

    base_period = history[period_col].min()
    history_time_index = np.array(
        [distance_fn(period, base_period) for period in history[period_col]]
    )
    history_seasons = history[season_col].to_numpy()
    y = history[value_col].to_numpy(dtype=float)

    x = design_matrix(history_time_index, history_seasons, season_order)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]

    fitted = x @ beta
    residuals = y - fitted
    degrees_of_freedom = max(len(y) - x.shape[1], 1)
    residual_std = float(np.sqrt(np.sum(residuals**2) / degrees_of_freedom))

    future_time_index = np.array(
        [distance_fn(period, base_period) for period in future_periods]
    )
    future_seasons = np.array([period.month for period in future_periods])
    if season_order == [1, 2, 3, 4]:
        future_seasons = np.array([period.quarter for period in future_periods])

    future_x = design_matrix(future_time_index, future_seasons, season_order)
    predictions = future_x @ beta
    predictions = np.clip(predictions, a_min=0, a_max=None)

    return predictions, residual_std


def backtest_mape(
    history: pd.DataFrame,
    value_col: str,
    period_col: str,
    season_col: str,
    season_order: list[int],
    distance_fn: Callable[[pd.Period, pd.Period], int],
) -> Optional[float]:
    latest_year = max(period.year for period in history[period_col])
    train = history[history[period_col].map(lambda period: period.year < latest_year)]
    test = history[history[period_col].map(lambda period: period.year == latest_year)]

    if len(train) < 6 or test.empty:
        return None

    predictions, _ = predict_seasonal_trend(
        train,
        list(test[period_col]),
        value_col,
        period_col,
        season_col,
        season_order,
        distance_fn,
    )
    actual = test[value_col].to_numpy(dtype=float)
    valid = actual != 0

    if not valid.any():
        return None

    return float(np.mean(np.abs((actual[valid] - predictions[valid]) / actual[valid])) * 100)


def scenario_values(
    base_prediction: float,
    residual_std: float,
    scenario_pct: float,
) -> dict[str, float]:
    band = max(abs(base_prediction) * scenario_pct, residual_std)
    return {
        "conservative": max(0.0, base_prediction - band),
        "base": max(0.0, base_prediction),
        "high": max(0.0, base_prediction + band),
    }


def build_volume_records(
    *,
    product: str,
    target_metric: str,
    period_type: str,
    future_periods: list[pd.Period],
    predictions: np.ndarray,
    residual_std: float,
    scenario_pct: float,
    training_start: str,
    training_end: str,
    training_points: int,
    backtest_value: Optional[float],
) -> list[dict]:
    records = []
    for period, prediction in zip(future_periods, predictions):
        values = scenario_values(float(prediction), residual_std, scenario_pct)
        for scenario, forecast_value in values.items():
            records.append(
                {
                    "forecast_year": period.year,
                    "target_metric": target_metric,
                    "product": product,
                    "period_type": period_type,
                    "period": str(period),
                    "scenario": scenario,
                    "forecast_value": forecast_value,
                    "unit": "tonnes",
                    "model_name": MODEL_NAME,
                    "model_detail": MODEL_DETAIL,
                    "training_start": training_start,
                    "training_end": training_end,
                    "training_points": training_points,
                    "residual_std": residual_std,
                    "backtest_mape_pct": backtest_value,
                }
            )
    return records


def forecast_monthly_exports(
    exports: pd.DataFrame,
    forecast_year: int,
    scenario_pct: float,
) -> pd.DataFrame:
    monthly = (
        exports[exports["product"].isin(CORE_PRODUCTS)]
        .groupby(["report_month", "product"], as_index=False)["tonnes"]
        .sum()
    )
    future_periods = list(
        pd.period_range(f"{forecast_year}-01", f"{forecast_year}-12", freq="M")
    )
    records: list[dict] = []

    for product in CORE_PRODUCTS:
        history = monthly[monthly["product"] == product].sort_values("report_month")
        if history.empty:
            continue

        history = history.copy()
        history["period"] = history["report_month"].dt.to_period("M")
        history["season"] = history["period"].map(lambda period: period.month)

        predictions, residual_std = predict_seasonal_trend(
            history,
            future_periods,
            "tonnes",
            "period",
            "season",
            list(range(1, 13)),
            month_distance,
        )
        backtest_value = backtest_mape(
            history,
            "tonnes",
            "period",
            "season",
            list(range(1, 13)),
            month_distance,
        )

        records.extend(
            build_volume_records(
                product=product,
                target_metric="exports_tonnes",
                period_type="monthly",
                future_periods=future_periods,
                predictions=predictions,
                residual_std=residual_std,
                scenario_pct=scenario_pct,
                training_start=str(history["period"].min()),
                training_end=str(history["period"].max()),
                training_points=len(history),
                backtest_value=backtest_value,
            )
        )

    return pd.DataFrame(records)


def forecast_quarterly_production(
    summary: pd.DataFrame,
    forecast_year: int,
    scenario_pct: float,
) -> pd.DataFrame:
    production = (
        summary[summary["product"].isin(CORE_PRODUCTS)]
        .groupby(["quarter", "product"], as_index=False)["production_tonnes"]
        .sum()
    )
    future_periods = list(
        pd.period_range(f"{forecast_year}Q1", f"{forecast_year}Q4", freq="Q")
    )
    records: list[dict] = []

    for product in CORE_PRODUCTS:
        history = production[production["product"] == product].sort_values("quarter")
        if history.empty:
            continue

        history = history.copy()
        history["period"] = pd.PeriodIndex(history["quarter"], freq="Q")
        history["season"] = history["period"].map(lambda period: period.quarter)

        predictions, residual_std = predict_seasonal_trend(
            history,
            future_periods,
            "production_tonnes",
            "period",
            "season",
            [1, 2, 3, 4],
            quarter_distance,
        )
        backtest_value = backtest_mape(
            history,
            "production_tonnes",
            "period",
            "season",
            [1, 2, 3, 4],
            quarter_distance,
        )

        records.extend(
            build_volume_records(
                product=product,
                target_metric="production_tonnes",
                period_type="quarterly",
                future_periods=future_periods,
                predictions=predictions,
                residual_std=residual_std,
                scenario_pct=scenario_pct,
                training_start=str(history["period"].min()),
                training_end=str(history["period"].max()),
                training_points=len(history),
                backtest_value=backtest_value,
            )
        )

    return pd.DataFrame(records)


def first_non_null(series: pd.Series) -> object:
    values = series.dropna()
    if values.empty:
        return None
    return values.iloc[0]


def aggregate_forecast(
    df: pd.DataFrame,
    target_metric: str,
    source_period_type: str,
    output_period_type: str,
    period_builder: Callable[[pd.Series], pd.Series],
) -> pd.DataFrame:
    subset = df[
        (df["target_metric"] == target_metric)
        & (df["period_type"] == source_period_type)
    ].copy()

    if subset.empty:
        return subset

    subset["period"] = period_builder(subset["period"])
    grouped = (
        subset.groupby(
            [
                "forecast_year",
                "target_metric",
                "product",
                "period_type",
                "period",
                "scenario",
            ],
            as_index=False,
        )
        .agg(
            forecast_value=("forecast_value", "sum"),
            unit=("unit", first_non_null),
            model_name=("model_name", first_non_null),
            model_detail=("model_detail", first_non_null),
            training_start=("training_start", first_non_null),
            training_end=("training_end", first_non_null),
            training_points=("training_points", "max"),
            residual_std=("residual_std", first_non_null),
            backtest_mape_pct=("backtest_mape_pct", first_non_null),
        )
    )
    grouped["period_type"] = output_period_type
    return grouped


def build_export_share_records(forecasts: pd.DataFrame) -> pd.DataFrame:
    exports = forecasts[
        forecasts["target_metric"].eq("exports_tonnes")
        & forecasts["period_type"].isin(["quarterly", "annual"])
    ].copy()
    production = forecasts[
        forecasts["target_metric"].eq("production_tonnes")
        & forecasts["period_type"].isin(["quarterly", "annual"])
    ].copy()

    scenario_pairs = {
        "conservative": ("conservative", "high"),
        "base": ("base", "base"),
        "high": ("high", "conservative"),
    }
    frames = []

    for output_scenario, (export_scenario, production_scenario) in scenario_pairs.items():
        export_subset = exports[exports["scenario"] == export_scenario]
        production_subset = production[production["scenario"] == production_scenario]
        merged = export_subset.merge(
            production_subset,
            on=["forecast_year", "product", "period_type", "period"],
            suffixes=("_exports", "_production"),
            how="inner",
        )

        if merged.empty:
            continue

        frame = pd.DataFrame(
            {
                "forecast_year": merged["forecast_year"],
                "target_metric": "export_share_pct",
                "product": merged["product"],
                "period_type": merged["period_type"],
                "period": merged["period"],
                "scenario": output_scenario,
                "forecast_value": (
                    merged["forecast_value_exports"]
                    / merged["forecast_value_production"]
                    * 100
                ),
                "unit": "percent",
                "model_name": "derived_ratio",
                "model_detail": (
                    "Exports forecast divided by production forecast. Conservative "
                    "uses low exports and high production; high uses high exports "
                    "and low production."
                ),
                "training_start": merged["training_start_exports"],
                "training_end": merged["training_end_exports"],
                "training_points": merged["training_points_exports"],
                "residual_std": np.nan,
                "backtest_mape_pct": np.nan,
            }
        )
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result["forecast_value"] = result["forecast_value"].replace(
        [np.inf, -np.inf], np.nan
    )
    return result


def month_to_quarter(periods: pd.Series) -> pd.Series:
    return pd.PeriodIndex(periods, freq="M").asfreq("Q").astype(str)


def period_to_year(periods: pd.Series) -> pd.Series:
    return periods.astype(str).str[:4]


def sort_forecast(forecasts: pd.DataFrame) -> pd.DataFrame:
    metric_order = {
        "exports_tonnes": 1,
        "production_tonnes": 2,
        "export_share_pct": 3,
    }
    period_order = {
        "monthly": 1,
        "quarterly": 2,
        "annual": 3,
    }
    scenario_order = {
        "conservative": 1,
        "base": 2,
        "high": 3,
    }

    result = forecasts.copy()
    result["_metric_order"] = result["target_metric"].map(metric_order)
    result["_period_order"] = result["period_type"].map(period_order)
    result["_scenario_order"] = result["scenario"].map(scenario_order)

    result = result.sort_values(
        [
            "_metric_order",
            "product",
            "_period_order",
            "period",
            "_scenario_order",
        ]
    ).drop(
        columns=["_metric_order", "_period_order", "_scenario_order"]
    )
    return result.reset_index(drop=True)


def build_forecast(
    release_month: Optional[str] = None,
    start_release_month: Optional[str] = None,
    end_release_month: Optional[str] = None,
    forecast_year: Optional[int] = None,
    scenario_pct: float = 0.10,
) -> pd.DataFrame:
    """
    Build volume and export-share forecasts for beef and lamb.
    """
    validate_release_mode(release_month, start_release_month, end_release_month)

    exports, summary = load_inputs(
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )

    latest_export_year = int(exports["report_month"].dt.year.max())
    latest_summary_year = int(summary["quarter"].astype(str).str[:4].astype(int).max())
    latest_history_year = max(latest_export_year, latest_summary_year)

    if forecast_year is None:
        forecast_year = latest_history_year + 1

    if forecast_year <= latest_history_year:
        raise ValueError(
            f"Forecast year must be later than the latest history year "
            f"({latest_history_year})."
        )

    monthly_exports = forecast_monthly_exports(exports, forecast_year, scenario_pct)
    quarterly_production = forecast_quarterly_production(
        summary,
        forecast_year,
        scenario_pct,
    )

    forecasts = pd.concat([monthly_exports, quarterly_production], ignore_index=True)

    quarterly_exports = aggregate_forecast(
        forecasts,
        "exports_tonnes",
        "monthly",
        "quarterly",
        month_to_quarter,
    )
    annual_exports = aggregate_forecast(
        forecasts,
        "exports_tonnes",
        "monthly",
        "annual",
        period_to_year,
    )
    annual_production = aggregate_forecast(
        forecasts,
        "production_tonnes",
        "quarterly",
        "annual",
        period_to_year,
    )

    forecasts = pd.concat(
        [
            forecasts,
            quarterly_exports,
            annual_exports,
            annual_production,
        ],
        ignore_index=True,
    )
    export_share = build_export_share_records(forecasts)
    forecasts = pd.concat([forecasts, export_share], ignore_index=True)
    forecasts = sort_forecast(forecasts)

    for numeric_col in ["forecast_value", "residual_std", "backtest_mape_pct"]:
        forecasts[numeric_col] = pd.to_numeric(
            forecasts[numeric_col],
            errors="coerce",
        ).round(2)

    output_file_name = build_output_file_name(
        forecast_year=forecast_year,
        release_month=release_month,
        start_release_month=start_release_month,
        end_release_month=end_release_month,
    )
    output_path = PROCESSED_DIR / output_file_name
    forecasts.to_csv(output_path, index=False)

    print(f"Saved market forecast to: {output_path}")
    return forecasts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build beef and lamb forecast records from processed market data."
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
        "--forecast-year",
        type=int,
        default=None,
        help="Forecast year. Defaults to the year after the latest historical data.",
    )
    parser.add_argument(
        "--scenario-pct",
        type=float,
        default=0.10,
        help="Minimum scenario band around the base forecast, for example 0.10 for 10 percent.",
    )
    args = parser.parse_args()

    build_forecast(
        release_month=args.release_month,
        start_release_month=args.start_release_month,
        end_release_month=args.end_release_month,
        forecast_year=args.forecast_year,
        scenario_pct=args.scenario_pct,
    )


if __name__ == "__main__":
    main()
