from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

import streamlit as st


def _single_date_from_input(value: object) -> date:
    if isinstance(value, date):
        return value
    raise ValueError("As of must be a single date.")


def default_as_of_date() -> date:
    return date.today()


def _optional_decimal_from_text(value: str) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace("%", ""))
    except InvalidOperation:
        return None


def _render_table(rows: list[dict[str, str]], empty_message: str) -> None:
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info(empty_message)
