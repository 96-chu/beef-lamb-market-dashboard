from __future__ import annotations

from pathlib import Path
import json

import pandas as pd
import streamlit as st

from src.services.report_service import ReportRequest, generate_market_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_EXPORTS = PROCESSED_DIR / "exports_clean_2024_01_to_2025_12.csv"
DEFAULT_SUMMARY = PROCESSED_DIR / "market_quarterly_summary_2024_01_to_2025_12.csv"


def read_uploaded_or_sample(uploaded_file, sample_path: Path) -> pd.DataFrame:
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)

    if not sample_path.exists():
        raise FileNotFoundError(f"Sample file not found: {sample_path}")

    return pd.read_csv(sample_path)


def main() -> None:
    st.set_page_config(
        page_title="Beef & Lamb Report Generator",
        page_icon=":material/analytics:",
        layout="wide",
    )
    st.title("Beef & Lamb Report Generator")
    st.caption("Upload processed market CSVs and generate insights, forecast scenarios, and a business report.")

    with st.sidebar:
        st.header("Inputs")
        exports_file = st.file_uploader(
            "Exports clean CSV",
            type=["csv"],
            help="Expected columns include report_month, destination, product, and tonnes.",
        )
        summary_file = st.file_uploader(
            "Market quarterly summary CSV",
            type=["csv"],
            help="Expected columns include quarter, product, exports_tonnes, production_tonnes, and slaughter_value.",
        )
        use_sample = st.checkbox(
            "Use bundled sample processed files when uploads are empty",
            value=True,
        )
        forecast_year = st.number_input(
            "Forecast year",
            min_value=2026,
            max_value=2035,
            value=2026,
            step=1,
        )
        scenario_pct = st.slider(
            "Scenario band",
            min_value=0.05,
            max_value=0.30,
            value=0.10,
            step=0.01,
            format="%.2f",
        )
        generate = st.button("Generate report", type="primary")

    if not generate:
        st.info("Upload the two processed CSVs, or keep the sample option enabled, then generate the report.")
        return

    if not use_sample and (exports_file is None or summary_file is None):
        st.error("Please upload both CSV files, or enable the bundled sample option.")
        return

    try:
        exports = read_uploaded_or_sample(exports_file, DEFAULT_EXPORTS)
        summary = read_uploaded_or_sample(summary_file, DEFAULT_SUMMARY)
        result = generate_market_report(
            exports,
            summary,
            ReportRequest(
                forecast_year=int(forecast_year),
                scenario_pct=float(scenario_pct),
            ),
        )
    except Exception as exc:
        st.exception(exc)
        return

    st.success(
        f"Generated {len(result['insights'])} insights and "
        f"{len(result['forecasts'])} forecast records for {result['forecast_year']}."
    )

    report_tab, insights_tab, forecast_tab, download_tab = st.tabs(
        ["Report", "Insights", "Forecast", "Downloads"]
    )

    with report_tab:
        st.markdown(result["report_markdown"])

    with insights_tab:
        st.dataframe(pd.DataFrame(result["insights"]), use_container_width=True)

    with forecast_tab:
        summary_df = pd.DataFrame(result["forecast_summary"])
        if not summary_df.empty:
            st.subheader("Annual base forecast")
            st.dataframe(summary_df, use_container_width=True)
        st.subheader("Scenario records")
        st.dataframe(pd.DataFrame(result["forecasts"]), use_container_width=True)

    with download_tab:
        insight_csv = pd.DataFrame(result["insights"]).to_csv(index=False)
        forecast_csv = pd.DataFrame(result["forecasts"]).to_csv(index=False)
        st.download_button(
            "Download insights CSV",
            insight_csv,
            file_name="uploaded_market_insights.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download forecast CSV",
            forecast_csv,
            file_name="uploaded_market_forecast.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download report JSON",
            json.dumps(result, indent=2, default=str),
            file_name="uploaded_market_report.json",
            mime="application/json",
        )


if __name__ == "__main__":
    main()
