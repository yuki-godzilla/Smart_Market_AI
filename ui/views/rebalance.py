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
from ui.components.downloads import render_csv_download_button
from ui.components.mascot import render_page_title
from ui.content.common_texts import (
    DECISION_REPORT_DOWNLOAD_GUIDE,
    DECISION_REPORT_JSON_DOWNLOAD_HELP,
    DECISION_REPORT_JSON_DOWNLOAD_LABEL,
    DECISION_REPORT_MANIFEST_DOWNLOAD_HELP,
    DECISION_REPORT_MANIFEST_DOWNLOAD_LABEL,
    DECISION_REPORT_MARKDOWN_DOWNLOAD_HELP,
    DECISION_REPORT_MARKDOWN_DOWNLOAD_LABEL,
    DECISION_REPORT_SUPPORT_MESSAGE,
    DECISION_REPORT_ZIP_DOWNLOAD_HELP,
    DECISION_REPORT_ZIP_DOWNLOAD_LABEL,
    EMPTY_STATE_MESSAGES,
)
from ui.rebalance_app import (
    RebalanceScenarioError,
    build_rebalance_decision_report_context,
    build_rebalance_report_context,
    build_rebalance_request,
    get_rebalance_sample,
    rebalance_decision_report_json_download,
    rebalance_decision_report_manifest_download,
    rebalance_decision_report_markdown_download,
    rebalance_decision_report_zip_download,
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
    render_page_title(
        "リバランス",
        "現在の保有、目標配分、配分見直し候補、リスク判定を確認します。売買送信は行いません。",
        "rebalance",
    )

    try:
        sample_names = rebalance_sample_names()
        sample_name = cast(str, st.selectbox("シナリオ", sample_names))
        sample = get_rebalance_sample(sample_name)
    except RebalanceScenarioError as exc:
        st.error(str(exc))
        st.stop()

    if sample.description:
        st.caption(sample.description)

    col_account, col_as_of, col_cash = st.columns([1.2, 1.0, 1.0])
    with col_account:
        account_id = st.text_input(
            "口座ID",
            value=sample.account_id,
            key=sample_widget_key(sample_name, "account"),
        )
    with col_as_of:
        as_of = st.date_input(
            "基準日",
            value=default_as_of_date(),
            key=sample_widget_key(sample_name, "as_of"),
        )
    with col_cash:
        cash_jpy_text = st.text_input(
            "現金(円)",
            value=str(sample.cash_jpy),
            key=sample_widget_key(sample_name, "cash_jpy"),
        )

    apple_target_weight = cast(
        int,
        st.slider(
            "AAPL目標比率",
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
    with st.expander("詳細入力(JSON)", expanded=False):
        col_positions, col_targets = st.columns(2)
        with col_positions:
            positions_json = st.text_area(
                "現在保有(JSON)",
                value=sample.positions_json,
                height=280,
                key=sample_widget_key(sample_name, "positions"),
            )
        with col_targets:
            targets_json = st.text_area(
                "目標配分(JSON)",
                value=generated_targets_json,
                height=280,
                key=sample_widget_key(sample_name, "targets"),
            )

    if st.button("配分見直しを確認", type="primary"):
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
            st.error("現金(円)は数値で入力してください。")
            return
        except ValueError as exc:
            st.error(str(exc))
            return
        except ValidationError as exc:
            st.error("入力内容を確認してください。")
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


def _risk_status_display(status: str) -> str:
    return {
        "ALLOW": "大きな制約違反なし",
        "REVIEW": "確認が必要",
        "BLOCK": "見直し優先",
    }.get(status, status or "未判定")


def _render_result(result: PortfolioRiskResult, request: RebalanceCheckRequest) -> None:
    context = build_rebalance_report_context(result)
    summary = context.summary
    status = summary["risk_status"]
    status_label = _risk_status_display(status)

    st.subheader("サマリー")
    col_total, col_cash, col_trades, col_status = st.columns(4)
    col_total.metric("現在資産", f"{summary['total_value_jpy']} JPY")
    col_cash.metric("現金", f"{summary['cash_jpy']} JPY")
    col_trades.metric("見直し候補", summary["trade_count"])
    col_status.metric("リスク判定", status_label)
    _render_rebalance_flow(summary)

    if status == "ALLOW":
        st.success(
            "リスク判定: 大きな制約違反はありません。今回の条件では配分見直し候補を確認できます。"
        )
    elif status == "REVIEW":
        st.warning("リスク判定: 確認が必要です。配分見直し候補の前提と制約を確認してください。")
    elif status == "BLOCK":
        st.error("リスク判定: 見直し優先です。主な理由を確認し、目標配分や制約を見直してください。")
    else:
        st.info("配分見直し候補がないため、リスク判定は行われていません。")

    _render_rebalance_decision_report(result, request)

    current_rows = context.current_rows
    target_rows = context.target_rows
    allocation_rows = context.allocation_rows
    trade_rows = context.trade_rows
    breach_rows = context.breach_rows

    col_current, col_targets = st.columns(2)
    with col_current:
        st.subheader("現在の保有")
        _render_table(current_rows, EMPTY_STATE_MESSAGES["current_positions"])
    with col_targets:
        st.subheader("目標配分")
        _render_table(target_rows, EMPTY_STATE_MESSAGES["target_allocations"])

    st.subheader("配分比較")
    _render_allocation_comparison_chart(allocation_rows)
    _render_table(
        allocation_rows,
        EMPTY_STATE_MESSAGES["allocation_comparison"],
    )

    st.subheader("配分見直し候補")
    _render_table(trade_rows, EMPTY_STATE_MESSAGES["rebalance_candidates"])

    if breach_rows:
        st.subheader("リスク確認事項")
        st.dataframe(
            risk_breach_display_rows(breach_rows),
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("ダウンロード", expanded=False):
        st.caption("詳細JSONやCSVは確認・保存が必要な場合だけ使います。")
        st.json(result.model_dump(mode="json"))
        st.download_button(
            "結果JSONをダウンロード",
            data=result_json_download(result),
            file_name="rebalance_check_result.json",
            mime="application/json",
        )
        st.download_button(
            "入力JSONをダウンロード",
            data=request_json_download(request),
            file_name="rebalance_request.json",
            mime="application/json",
        )
        st.download_button(
            "レポートMarkdownをダウンロード",
            data=result_markdown_report_download(result, request=request),
            file_name="rebalance_report.md",
            mime="text/markdown",
        )
        st.download_button(
            "レポート一式ZIPをダウンロード",
            data=result_report_zip_download(result, request=request),
            file_name="rebalance_report.zip",
            mime="application/zip",
        )
        _render_table_csv_download_button(
            label="サマリーCSVをダウンロード",
            rows=[summary],
            file_name="rebalance_summary.csv",
        )
        _render_table_csv_download_button(
            label="現在保有CSVをダウンロード",
            rows=current_rows,
            fieldnames=["symbol", "qty", "currency", "last", "fx_rate_jpy", "value_jpy"],
            file_name="rebalance_current_positions.csv",
        )
        _render_table_csv_download_button(
            label="目標配分CSVをダウンロード",
            rows=target_rows,
            fieldnames=["symbol", "currency", "target_weight"],
            file_name="rebalance_target_allocations.csv",
        )
        _render_table_csv_download_button(
            label="配分比較CSVをダウンロード",
            rows=allocation_rows,
            fieldnames=["symbol", "current_weight", "target_weight", "drift"],
            file_name="rebalance_allocation_comparison.csv",
        )
        _render_table_csv_download_button(
            label="見直し候補CSVをダウンロード",
            rows=trade_rows,
            fieldnames=["symbol", "side", "qty", "price_hint", "currency"],
            file_name="rebalance_proposed_trades.csv",
        )
        _render_table_csv_download_button(
            label="リスク確認事項CSVをダウンロード",
            rows=breach_rows,
            fieldnames=["breach"],
            file_name="rebalance_risk_breaches.csv",
        )


def _render_table_csv_download_button(
    *,
    label: str,
    rows: list[dict[str, str]],
    file_name: str,
    fieldnames: list[str] | None = None,
) -> None:
    if not rows:
        render_csv_download_button(
            label=label,
            data=None,
            file_name=file_name,
            empty_message=f"{label}: CSVに出力できるデータがありません。",
        )
        return
    render_csv_download_button(
        label=label,
        data=table_csv_download(rows, fieldnames=fieldnames),
        file_name=file_name,
    )


def _render_rebalance_decision_report(
    result: PortfolioRiskResult,
    request: RebalanceCheckRequest,
) -> None:
    context = build_rebalance_decision_report_context(result, request=request)
    markdown = rebalance_decision_report_markdown_download(context)
    st.markdown("### 投資判断レポート")
    st.info(
        "現在保有、目標配分、配分見直し候補、リスク判定、確認ポイントを保存する分析メモです。"
        "売買指示ではありません。"
    )
    st.caption(DECISION_REPORT_SUPPORT_MESSAGE)
    st.caption(DECISION_REPORT_DOWNLOAD_GUIDE)
    col_markdown, col_json, col_manifest, col_zip = st.columns(4)
    col_markdown.download_button(
        DECISION_REPORT_MARKDOWN_DOWNLOAD_LABEL,
        data=markdown,
        file_name="decision_report_rebalance.md",
        mime="text/markdown",
        help=DECISION_REPORT_MARKDOWN_DOWNLOAD_HELP,
    )
    col_json.download_button(
        DECISION_REPORT_JSON_DOWNLOAD_LABEL,
        data=rebalance_decision_report_json_download(context),
        file_name="decision_report_rebalance.json",
        mime="application/json",
        help=DECISION_REPORT_JSON_DOWNLOAD_HELP,
    )
    col_manifest.download_button(
        DECISION_REPORT_MANIFEST_DOWNLOAD_LABEL,
        data=rebalance_decision_report_manifest_download(context),
        file_name="decision_report_manifest.json",
        mime="application/json",
        help=DECISION_REPORT_MANIFEST_DOWNLOAD_HELP,
    )
    col_zip.download_button(
        DECISION_REPORT_ZIP_DOWNLOAD_LABEL,
        data=rebalance_decision_report_zip_download(context),
        file_name="decision_report_rebalance_package.zip",
        mime="application/zip",
        help=DECISION_REPORT_ZIP_DOWNLOAD_HELP,
    )
    with st.expander("レポート本文を表示", expanded=False):
        st.markdown(markdown)


def rebalance_result_from_state() -> tuple[PortfolioRiskResult, RebalanceCheckRequest] | None:
    result = st.session_state.get(REBALANCE_RESULT_STATE_KEY)
    request = st.session_state.get(REBALANCE_REQUEST_STATE_KEY)
    if isinstance(result, PortfolioRiskResult) and isinstance(request, RebalanceCheckRequest):
        return result, request
    return None


def rebalance_flow_rows(summary: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"step": "現在", "value": f"{summary.get('total_value_jpy', '')} JPY"},
        {"step": "目標", "value": "目標配分"},
        {"step": "見直し候補", "value": f"{summary.get('trade_count', '0')}件"},
        {"step": "リスク判定", "value": _risk_status_display(summary.get("risk_status", ""))},
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
                alt.Tooltip("weight:Q", title="比率(%)"),
            ],
        )
        .properties(height=max(120, 54 * len(rows)))
    )
    st.altair_chart(chart, use_container_width=True)


def risk_breach_display_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        {
            "確認事項": row.get("breach", ""),
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
    return "リスクルールに抵触しています。条件と入力を確認してください。"
