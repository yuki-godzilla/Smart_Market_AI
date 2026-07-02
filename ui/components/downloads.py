from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

import streamlit as st

CSV_MIME = "text/csv"
JSON_MIME = "application/json"
MARKDOWN_MIME = "text/markdown"
PDF_MIME = "application/pdf"
ZIP_MIME = "application/zip"


class DownloadContract(TypedDict):
    data: bytes
    file_name: str
    mime: str


CsvDownloadContract = DownloadContract


def download_contract(
    *,
    data: bytes | str,
    file_name: str,
    mime: str,
    extension: str,
) -> DownloadContract:
    payload = data.encode("utf-8") if isinstance(data, str) else data
    if not isinstance(payload, bytes):
        raise TypeError("Download data must be bytes or text")
    if not file_name.lower().endswith(extension):
        raise ValueError(f"Download file_name must end with {extension}")
    return {"data": payload, "file_name": file_name, "mime": mime}


def csv_download_contract(*, data: bytes, file_name: str) -> CsvDownloadContract:
    if not isinstance(data, bytes):
        raise TypeError("CSV download data must be bytes")
    return download_contract(
        data=data,
        file_name=file_name,
        mime=CSV_MIME,
        extension=".csv",
    )


def json_download_contract(*, data: bytes | str, file_name: str) -> DownloadContract:
    return download_contract(
        data=data,
        file_name=file_name,
        mime=JSON_MIME,
        extension=".json",
    )


def markdown_download_contract(*, data: bytes | str, file_name: str) -> DownloadContract:
    return download_contract(
        data=data,
        file_name=file_name,
        mime=MARKDOWN_MIME,
        extension=".md",
    )


def pdf_download_contract(*, data: bytes, file_name: str) -> DownloadContract:
    return download_contract(
        data=data,
        file_name=file_name,
        mime=PDF_MIME,
        extension=".pdf",
    )


def zip_download_contract(*, data: bytes, file_name: str) -> DownloadContract:
    return download_contract(
        data=data,
        file_name=file_name,
        mime=ZIP_MIME,
        extension=".zip",
    )


def _render_download(
    *,
    label: str,
    contract: DownloadContract | None,
    key: str | None = None,
    empty_message: str,
    use_container_width: bool = True,
) -> None:
    if contract is None or not contract["data"]:
        st.warning(empty_message)
        return
    options: dict[str, Any] = dict(contract)
    if key is not None:
        options["key"] = key
    if use_container_width:
        options["use_container_width"] = True
    st.download_button(label, **options)


def _render_csv_download_button_body(
    *,
    label: str,
    data: bytes | None,
    file_name: str,
    empty_message: str = "CSVに出力できるデータがありません。",
    key: str | None = None,
    use_container_width: bool = False,
) -> None:
    _render_download(
        label=label,
        contract=csv_download_contract(data=data, file_name=file_name) if data else None,
        key=key,
        empty_message=empty_message,
        use_container_width=use_container_width,
    )


def _render_json_download_body(
    *,
    label: str,
    data: bytes | str | None,
    file_name: str,
    key: str | None = None,
    use_container_width: bool = True,
) -> None:
    _render_download(
        label=label,
        contract=json_download_contract(data=data, file_name=file_name) if data else None,
        key=key,
        empty_message="JSONに出力できるデータがありません。",
        use_container_width=use_container_width,
    )


def _render_markdown_download_body(
    *,
    label: str,
    data: bytes | str | None,
    file_name: str,
    key: str | None = None,
    use_container_width: bool = True,
) -> None:
    _render_download(
        label=label,
        contract=markdown_download_contract(data=data, file_name=file_name) if data else None,
        key=key,
        empty_message="Markdownに出力できる内容がありません。",
        use_container_width=use_container_width,
    )


def _render_pdf_download_body(
    *,
    label: str,
    data: bytes | None,
    file_name: str,
    key: str | None = None,
    use_container_width: bool = True,
) -> None:
    _render_download(
        label=label,
        contract=pdf_download_contract(data=data, file_name=file_name) if data else None,
        key=key,
        empty_message="PDFに出力できる内容がありません。",
        use_container_width=use_container_width,
    )


def _render_zip_download_body(
    *,
    label: str,
    data: bytes | None,
    file_name: str,
    key: str | None = None,
    use_container_width: bool = True,
) -> None:
    _render_download(
        label=label,
        contract=zip_download_contract(data=data, file_name=file_name) if data else None,
        key=key,
        empty_message="ZIPに出力できる内容がありません。",
        use_container_width=use_container_width,
    )


render_csv_download_button = st.fragment(_render_csv_download_button_body)
render_json_download = st.fragment(_render_json_download_body)
render_markdown_download = st.fragment(_render_markdown_download_body)
render_pdf_download = st.fragment(_render_pdf_download_body)
render_zip_download = st.fragment(_render_zip_download_body)


def render_json_preview(data: str | Mapping[str, Any] | Sequence[Any]) -> None:
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            st.code(data, language="json")
            return
        st.json(parsed, expanded=False)
        return
    st.json(data, expanded=False)


def render_json_copy(data: str | Mapping[str, Any] | Sequence[Any]) -> None:
    text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2)
    st.caption("コード欄右上のコピー操作を利用できます。")
    st.code(text, language="json")


def render_csv_preview(rows: Sequence[Mapping[str, Any]], *, max_rows: int = 50) -> None:
    st.dataframe(list(rows[:max_rows]), hide_index=True, use_container_width=True)
    if len(rows) > max_rows:
        st.caption(f"先頭{max_rows}件を表示しています。全件はCSVでダウンロードできます。")


def render_markdown_preview(data: str) -> None:
    st.markdown(data)


def render_markdown_copy(data: str) -> None:
    st.caption("コード欄右上のコピー操作を利用できます。")
    st.code(data, language="markdown")


def render_pdf_inline_preview(data: bytes, *, height: int = 720) -> None:
    """Render PDF inside SMAI only after the caller explicitly requests a preview."""

    encoded = base64.b64encode(data).decode("ascii")
    st.markdown(
        (
            f'<iframe title="PDFプレビュー" src="data:{PDF_MIME};base64,{encoded}" '
            f'width="100%" height="{max(320, height)}" style="border:0"></iframe>'
        ),
        unsafe_allow_html=True,
    )
