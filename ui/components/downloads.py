from __future__ import annotations

from typing import TypedDict

import streamlit as st

CSV_MIME = "text/csv"


class CsvDownloadContract(TypedDict):
    data: bytes
    file_name: str
    mime: str


def csv_download_contract(*, data: bytes, file_name: str) -> CsvDownloadContract:
    if not isinstance(data, bytes):
        raise TypeError("CSV download data must be bytes")
    if not file_name.lower().endswith(".csv"):
        raise ValueError("CSV download file_name must end with .csv")
    return {
        "data": data,
        "file_name": file_name,
        "mime": CSV_MIME,
    }


def _render_csv_download_button_body(
    *,
    label: str,
    data: bytes | None,
    file_name: str,
    empty_message: str = "CSVに出力できるデータがありません。",
) -> None:
    """Render a CSV download without rerunning and invalidating its media URL."""

    if not data:
        st.warning(empty_message)
        return
    st.download_button(
        label,
        **csv_download_contract(data=data, file_name=file_name),
    )


render_csv_download_button = st.fragment(_render_csv_download_button_body)
