from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from typing import cast

import altair as alt
import pandas as pd
import streamlit as st
from pydantic import ValidationError

from backend.app.main import RebalanceCheckRequest
from backend.portfolio.workflow import PortfolioRiskResult
from ui.rebalance_app import (
    RebalanceScenarioError,
    build_rebalance_report_context,
    build_rebalance_request,
    get_rebalance_sample,
    rebalance_sample_names,
    request_json_download,
    result_json_download,
    result_markdown_report_download,
    result_report_zip_download,
    run_rebalance_check,
    sample_widget_key,
    table_csv_download,
    target_allocations_json,
)
from ui.views.common import (
    _optional_decimal_from_text,
    _render_table,
    _single_date_from_input,
    default_as_of_date,
)

REBALANCE_RESULT_STATE_KEY = "rebalance_result"
REBALANCE_REQUEST_STATE_KEY = "rebalance_request"


def render_rebalance_page() -> None:
    st.subheader("Rebalance Cockpit")
    st.caption("現在の保有、目標配分、必要な売買、Risk 判定を確認します。売買送信は行いません。")

    try:
        sample_names = rebalance_sample_names()
        sample_name = cast(str, st.selectbox("Sample", sample_names))
        sample = get_rebalance_sample(sample_name)
    except RebalanceScenarioError as exc:
        st.error(str(exc))
        st.stop()

    if sample.description:
        st.caption(sample.description)

    col_account, col_as_of, col_cash = st.columns([1.2, 1.0, 1.0])
    with col_account:
        account_id = st.text_input(
            "Account",
            value=sample.account_id,
            key=sample_widget_key(sample_name, "account"),
        )
    with col_as_of:
        as_of = st.date_input(
            "As of",
            value=default_as_of_date(),
            key=sample_widget_key(sample_name, "as_of"),
        )
    with col_cash:
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
    generated_targets_json = target_allocations_json(
        toyota_weight=Decimal(100 - apple_target_weight) / Decimal("100"),
        apple_weight=Decimal(apple_target_weight) / Decimal("100"),
    )
    with st.expander("Advanced JSON input"):
        col_positions, col_targets = st.columns(2)
        with col_positions:
            positions_json = st.text_area(
                "Positions",
                value=sample.positions_json,
                height=280,
                key=sample_widget_key(sample_name, "positions"),
            )
        with col_targets:
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
            st.session_state[REBALANCE_RESULT_STATE_KEY] = result
            st.session_state[REBALANCE_REQUEST_STATE_KEY] = request
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

    stored_rebalance = rebalance_result_from_state()
    if stored_rebalance is not None:
        result, request = stored_rebalance
        _render_result(result, request)


def _decimal_from_text(value: str) -> Decimal:
    return Decimal(value.strip())


def _default_apple_target_weight(targets_json: str) -> int:
    if '"symbol": "AAPL"' not in targets_json:
        return 0
    if '"target_weight": "0.5"' in targets_json:
        return 50
    return 0


def _render_result(result: PortfolioRiskResult, request: RebalanceCheckRequest) -> None:
    context = build_rebalance_report_context(result)
    summary = context.summary
    status = summary["risk_status"]

    st.subheader("Summary")
    col_total, col_cash, col_trades, col_status = st.columns(4)
    col_total.metric("現在資産", f"{summary['total_value_jpy']} JPY")
    col_cash.metric("現金", f"{summary['cash_jpy']} JPY")
    col_trades.metric("必要な売買", summary["trade_count"])
    col_status.metric("Risk 判定", status)
    _render_rebalance_flow(summary)

    if status == "ALLOW":
        st.success("Risk 判定: ALLOW。今回の条件では大きな制約違反はありません。")
    elif status == "REVIEW":
        st.warning("Risk 判定: REVIEW。売買案の前提と制約を確認してください。")
    elif status == "BLOCK":
        st.error("Risk 判定: BLOCK。主な理由を確認し、目標配分や制約を見直してください。")
    else:
        st.info("売買案がないため、Risk 判定は行われていません。")

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
    _render_allocation_comparison_chart(allocation_rows)
    _render_table(
        allocation_rows,
        "No allocation comparison is available.",
    )

    st.subheader("Proposed Trades")
    _render_table(trade_rows, "No rebalance trades were proposed.")

    if breach_rows:
        st.subheader("Risk Breaches")
        st.dataframe(
            risk_breach_display_rows(breach_rows),
            hide_index=True,
            use_container_width=True,
        )

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


def rebalance_result_from_state() -> tuple[PortfolioRiskResult, RebalanceCheckRequest] | None:
    result = st.session_state.get(REBALANCE_RESULT_STATE_KEY)
    request = st.session_state.get(REBALANCE_REQUEST_STATE_KEY)
    if isinstance(result, PortfolioRiskResult) and isinstance(request, RebalanceCheckRequest):
        return result, request
    return None


def rebalance_flow_rows(summary: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"step": "現在", "value": f"{summary.get('total_value_jpy', '')} JPY"},
        {"step": "目標", "value": "target allocations"},
        {"step": "売買案", "value": f"{summary.get('trade_count', '0')} trades"},
        {"step": "Risk", "value": summary.get("risk_status", "")},
    ]


def _render_rebalance_flow(summary: dict[str, str]) -> None:
    step_cols = st.columns(4)
    for col, row in zip(step_cols, rebalance_flow_rows(summary), strict=True):
        col.caption(row["step"])
        col.write(row["value"])


def allocation_chart_frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in rows:
        symbol = row.get("symbol", "")
        for field, label in (
            ("current_weight", "現在"),
            ("target_weight", "目標"),
        ):
            value = _optional_decimal_from_text(row.get(field, ""))
            if value is None:
                continue
            records.append(
                {
                    "symbol": symbol,
                    "type": label,
                    "weight": float(value),
                }
            )
    return pd.DataFrame(records)


def _render_allocation_comparison_chart(rows: list[dict[str, str]]) -> None:
    frame = allocation_chart_frame(rows)
    if frame.empty:
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadius=3)
        .encode(
            x=alt.X("weight:Q", title="Weight (%)"),
            y=alt.Y("symbol:N", title=None, sort=None),
            color=alt.Color("type:N", title="配分"),
            yOffset="type:N",
            tooltip=[
                alt.Tooltip("symbol:N", title="銘柄"),
                alt.Tooltip("type:N", title="配分"),
                alt.Tooltip("weight:Q", title="Weight (%)"),
            ],
        )
        .properties(height=max(120, 54 * len(rows)))
    )
    st.altair_chart(chart, use_container_width=True)


def risk_breach_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "breach": row.get("breach", ""),
            "確認ポイント": risk_breach_message(row.get("breach", "")),
        }
        for row in rows
    ]


def risk_breach_message(breach: str) -> str:
    if breach.startswith("R5:min_dividend_yield:"):
        symbol = breach.rsplit(":", maxsplit=1)[-1]
        return f"{symbol} は配当利回りの条件を満たしていない可能性があります。"
    if breach == "R3:max_concentration":
        return "1銘柄への集中度が高くなっています。目標配分を確認してください。"
    if breach.startswith("R2:cash"):
        return "現金残高に関する制約を確認してください。"
    return "Risk ルールに抵触しています。条件と入力を確認してください。"
