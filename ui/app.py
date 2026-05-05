from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal, InvalidOperation

import streamlit as st
from pydantic import ValidationError

from ui.rebalance_app import (
    DEFAULT_POSITIONS_JSON,
    DEFAULT_TARGETS_JSON,
    build_rebalance_request,
    run_rebalance_check,
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

        st.subheader("Proposal")
        st.json(result.proposal.model_dump(mode="json"))
        st.subheader("Risk Decision")
        st.json(result.risk_decision.model_dump(mode="json") if result.risk_decision else None)


def _decimal_from_text(value: str) -> Decimal:
    return Decimal(value.strip())


if __name__ == "__main__":
    main()
