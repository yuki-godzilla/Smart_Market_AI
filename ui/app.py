from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import cast

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from backend.app.main import RebalanceCheckRequest
from backend.portfolio.workflow import PortfolioRiskResult
from ui.rebalance_app import (
    RebalanceScenarioError,
    build_market_data_preview,
    build_rebalance_report_context,
    build_rebalance_request,
    get_rebalance_sample,
    rebalance_sample_names,
    request_json_download,
    result_json_download,
    result_markdown_report_download,
    result_report_zip_download,
    run_rebalance_check,
    runtime_settings_summary,
    sample_widget_key,
    screening_score_csv_download,
    screening_score_json_download,
    symbol_reference_rows,
    table_csv_download,
    target_allocations_json,
)


def main() -> None:
    st.set_page_config(page_title="Smart Market AI", layout="wide")
    st.title("Smart Market AI")

    rebalance_tab, market_data_tab = st.tabs(["Rebalance", "Market Data"])

    with st.sidebar:
        _render_runtime_settings()
        _render_symbol_reference()
        try:
            sample_names = rebalance_sample_names()
            sample_name = cast(str, st.selectbox("Sample", sample_names))
            sample = get_rebalance_sample(sample_name)
        except RebalanceScenarioError as exc:
            st.error(str(exc))
            st.stop()
        if sample.description:
            st.caption(sample.description)

        account_id = st.text_input(
            "Account",
            value=sample.account_id,
            key=sample_widget_key(sample_name, "account"),
        )
        as_of = st.date_input(
            "As of",
            value=default_as_of_date(),
            key=sample_widget_key(sample_name, "as_of"),
        )
        cash_jpy_text = st.text_input(
            "Cash JPY",
            value=str(sample.cash_jpy),
            key=sample_widget_key(sample_name, "cash_jpy"),
        )
        apple_target_weight = cast(
            int,
            st.slider(
                "AAPL target weight",
                min_value=0,
                max_value=100,
                value=_default_apple_target_weight(sample.targets_json),
                step=5,
                format="%d%%",
                key=sample_widget_key(sample_name, "apple_target_weight"),
            ),
        )

    with rebalance_tab:
        col_positions, col_targets = st.columns(2)
        with col_positions:
            positions_json = st.text_area(
                "Positions",
                value=sample.positions_json,
                height=280,
                key=sample_widget_key(sample_name, "positions"),
            )
        with col_targets:
            generated_targets_json = target_allocations_json(
                toyota_weight=Decimal(100 - apple_target_weight) / Decimal("100"),
                apple_weight=Decimal(apple_target_weight) / Decimal("100"),
            )
            targets_json = st.text_area(
                "Targets",
                value=generated_targets_json,
                height=280,
                key=sample_widget_key(sample_name, "targets"),
            )

        if st.button("Run rebalance check", type="primary"):
            try:
                request = build_rebalance_request(
                    account_id=account_id,
                    as_of=_single_date_from_input(as_of),
                    cash_jpy=_decimal_from_text(cash_jpy_text),
                    positions_json=positions_json,
                    targets_json=targets_json,
                )
                result = asyncio.run(run_rebalance_check(request))
            except InvalidOperation:
                st.error("Cash JPY must be a decimal number.")
                return
            except ValueError as exc:
                st.error(str(exc))
                return
            except ValidationError as exc:
                st.error("Request validation failed.")
                st.json(exc.errors())
                return
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
                return

            _render_result(result, request)

    with market_data_tab:
        _render_market_data_preview()


def _decimal_from_text(value: str) -> Decimal:
    return Decimal(value.strip())


def _single_date_from_input(value: object) -> date:
    if isinstance(value, date):
        return value
    raise ValueError("As of must be a single date.")


def default_as_of_date() -> date:
    return date.today()


def default_market_data_start_date() -> date:
    return default_market_data_end_date() - timedelta(days=7)


def default_market_data_end_date() -> date:
    return date.today()


def _default_apple_target_weight(targets_json: str) -> int:
    if '"symbol": "AAPL"' not in targets_json:
        return 0
    if '"target_weight": "0.5"' in targets_json:
        return 50
    return 0


def _render_runtime_settings() -> None:
    settings = runtime_settings_summary()
    st.caption("Runtime")
    st.write(f"Provider: `{settings['provider']}`")
    st.write(f"Config: `{settings['config_file']}`")
    st.write(f"Scenarios: `{settings['scenario_dir']}`")
    if settings["provider"] == "csv":
        st.write(f"CSV data: `{settings['csv_data_dir']}`")


def _render_symbol_reference() -> None:
    st.caption("Sample Symbols")
    st.dataframe(symbol_reference_rows(), hide_index=True, use_container_width=True)


def _render_market_data_preview() -> None:
    st.subheader("Market Data")
    col_symbol, col_start, col_end = st.columns(3)
    with col_symbol:
        symbol = st.text_input("Symbol", value="AAPL", key="market_data_symbol")
    with col_start:
        start = st.date_input(
            "Start",
            value=default_market_data_start_date(),
            key="market_data_start",
        )
    with col_end:
        end = st.date_input("End", value=default_market_data_end_date(), key="market_data_end")

    if st.button("Fetch market data", key="fetch_market_data"):
        try:
            preview = asyncio.run(
                build_market_data_preview(
                    symbol=symbol.strip(),
                    start=_single_date_from_input(start),
                    end=_single_date_from_input(end),
                )
            )
        except ValueError as exc:
            st.error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))
            return

        if preview.status == "OK":
            st.success("Market data fetched.")
        else:
            st.error("Market data fetch failed.")

        st.subheader("Provider")
        _render_table(preview.provider_rows, "No provider metadata.")

        st.subheader("Quote")
        _render_table(preview.quote_rows, "No quote rows.")

        st.subheader("OHLCV Summary")
        _render_table(preview.ohlcv_rows, "No OHLCV rows.")

        st.subheader("Price And Forecast")
        _render_market_chart(preview.forecast_chart_rows)
        st.subheader("Forecast Metrics")
        _render_table(preview.forecast_metric_rows, "No forecast metrics.")

        st.subheader("FX")
        _render_table(preview.fx_rows, "No FX rows.")

        st.subheader("Feature Snapshot")
        _render_table(preview.feature_rows, "No feature snapshot rows.")

        st.subheader("Screening Score")
        _render_table(preview.screening_rows, "No screening score rows.")
        if preview.screening_rows:
            col_json, col_csv = st.columns(2)
            col_json.download_button(
                "Download screening JSON",
                data=screening_score_json_download(preview.screening_rows),
                file_name="screening_score.json",
                mime="application/json",
            )
            col_csv.download_button(
                "Download screening CSV",
                data=screening_score_csv_download(preview.screening_rows),
                file_name="screening_score.csv",
                mime="text/csv",
            )

        if preview.error_rows:
            st.subheader("Errors")
            st.dataframe(preview.error_rows, hide_index=True, use_container_width=True)


def _render_result(result: PortfolioRiskResult, request: RebalanceCheckRequest) -> None:
    context = build_rebalance_report_context(result)
    summary = context.summary
    status = summary["risk_status"]

    st.subheader("Summary")
    col_total, col_cash, col_trades, col_status = st.columns(4)
    col_total.metric("Total value JPY", summary["total_value_jpy"])
    col_cash.metric("Cash JPY", summary["cash_jpy"])
    col_trades.metric("Proposed trades", summary["trade_count"])
    col_status.metric("Risk status", status)

    if status == "ALLOW":
        st.success("Risk decision: ALLOW")
    elif status == "REVIEW":
        st.warning("Risk decision: REVIEW")
    elif status == "BLOCK":
        st.error("Risk decision: BLOCK")
    else:
        st.info("No trades were generated, so Risk was not evaluated.")

    current_rows = context.current_rows
    target_rows = context.target_rows
    allocation_rows = context.allocation_rows
    trade_rows = context.trade_rows
    breach_rows = context.breach_rows

    col_current, col_targets = st.columns(2)
    with col_current:
        st.subheader("Current Positions")
        _render_table(current_rows, "No current positions.")
    with col_targets:
        st.subheader("Target Allocations")
        _render_table(target_rows, "No target allocations.")

    st.subheader("Allocation Comparison")
    _render_table(
        allocation_rows,
        "No allocation comparison is available.",
    )

    st.subheader("Proposed Trades")
    _render_table(trade_rows, "No rebalance trades were proposed.")

    if breach_rows:
        st.subheader("Risk Breaches")
        st.dataframe(breach_rows, hide_index=True, use_container_width=True)

    with st.expander("Downloads"):
        st.json(result.model_dump(mode="json"))
        st.download_button(
            "Download JSON",
            data=result_json_download(result),
            file_name="rebalance_check_result.json",
            mime="application/json",
        )
        st.download_button(
            "Download request JSON",
            data=request_json_download(request),
            file_name="rebalance_request.json",
            mime="application/json",
        )
        st.download_button(
            "Download report Markdown",
            data=result_markdown_report_download(result, request=request),
            file_name="rebalance_report.md",
            mime="text/markdown",
        )
        st.download_button(
            "Download report ZIP",
            data=result_report_zip_download(result, request=request),
            file_name="rebalance_report.zip",
            mime="application/zip",
        )
        st.download_button(
            "Download summary CSV",
            data=table_csv_download([summary]),
            file_name="rebalance_summary.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download current positions CSV",
            data=table_csv_download(
                current_rows,
                fieldnames=["symbol", "qty", "currency", "last", "fx_rate_jpy", "value_jpy"],
            ),
            file_name="rebalance_current_positions.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download target allocations CSV",
            data=table_csv_download(
                target_rows,
                fieldnames=["symbol", "currency", "target_weight"],
            ),
            file_name="rebalance_target_allocations.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download allocation comparison CSV",
            data=table_csv_download(
                allocation_rows,
                fieldnames=["symbol", "current_weight", "target_weight", "drift"],
            ),
            file_name="rebalance_allocation_comparison.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download proposed trades CSV",
            data=table_csv_download(
                trade_rows,
                fieldnames=["symbol", "side", "qty", "price_hint", "currency"],
            ),
            file_name="rebalance_proposed_trades.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download risk breaches CSV",
            data=table_csv_download(breach_rows, fieldnames=["breach"]),
            file_name="rebalance_risk_breaches.csv",
            mime="text/csv",
        )


def _render_table(rows: list[dict[str, str]], empty_message: str) -> None:
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info(empty_message)


def _render_market_chart(rows: list[dict[str, str]]) -> None:
    if not rows:
        st.info("No chart rows.")
        return
    frame = pd.DataFrame(rows).set_index("ts")
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    st.line_chart(frame)


if __name__ == "__main__":
    main()
