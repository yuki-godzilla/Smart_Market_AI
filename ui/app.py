from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal, InvalidOperation

import streamlit as st
from pydantic import ValidationError

from backend.portfolio.workflow import PortfolioRiskResult
from ui.rebalance_app import (
    DEFAULT_POSITIONS_JSON,
    DEFAULT_TARGETS_JSON,
    build_rebalance_request,
    current_position_rows,
    proposed_trade_rows,
    result_summary,
    risk_breach_rows,
    run_rebalance_check,
    target_allocation_rows,
)


def main() -> None:
    st.set_page_config(page_title="Smart Market AI", layout="wide")
    st.title("Smart Market AI")

    with st.sidebar:
        account_id = st.text_input("Account", value="acct-1")
        as_of = st.date_input("As of", value=date(2026, 4, 9))
        cash_jpy_text = st.text_input("Cash JPY", value="29000")

    col_positions, col_targets = st.columns(2)
    with col_positions:
        positions_json = st.text_area("Positions", value=DEFAULT_POSITIONS_JSON, height=280)
    with col_targets:
        targets_json = st.text_area("Targets", value=DEFAULT_TARGETS_JSON, height=280)

    if st.button("Run rebalance check", type="primary"):
        try:
            request = build_rebalance_request(
                account_id=account_id,
                as_of=as_of,
                cash_jpy=_decimal_from_text(cash_jpy_text),
                positions_json=positions_json,
                targets_json=targets_json,
            )
            result = asyncio.run(run_rebalance_check(request))
        except (InvalidOperation, ValueError, ValidationError) as exc:
            st.error(str(exc))
            return

        _render_result(result)


def _decimal_from_text(value: str) -> Decimal:
    return Decimal(value.strip())


def _render_result(result: PortfolioRiskResult) -> None:
    summary = result_summary(result)
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

    proposal = result.proposal
    col_current, col_targets = st.columns(2)
    with col_current:
        st.subheader("Current Positions")
        _render_table(current_position_rows(proposal), "No current positions.")
    with col_targets:
        st.subheader("Target Allocations")
        _render_table(target_allocation_rows(proposal), "No target allocations.")

    st.subheader("Proposed Trades")
    _render_table(proposed_trade_rows(proposal), "No rebalance trades were proposed.")

    breaches = risk_breach_rows(result)
    if breaches:
        st.subheader("Risk Breaches")
        st.dataframe(breaches, hide_index=True, use_container_width=True)

    with st.expander("Raw JSON"):
        st.json(result.model_dump(mode="json"))


def _render_table(rows: list[dict[str, str]], empty_message: str) -> None:
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info(empty_message)


if __name__ == "__main__":
    main()
