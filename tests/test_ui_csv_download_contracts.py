from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ui.components.downloads import (
    CSV_MIME,
    csv_download_contract,
    render_csv_download_button,
)

CSV_UI_FILES = (
    Path("ui/app.py"),
    Path("ui/views/rebalance.py"),
)


def test_all_literal_csv_download_calls_use_csv_filename() -> None:
    csv_calls = []
    for path in CSV_UI_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not _is_csv_download_call(node):
                continue
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            file_name = _literal_text(keywords.get("file_name"))
            if file_name is None or not file_name.endswith(".csv"):
                continue
            csv_calls.append((path, node.lineno, keywords))

    assert csv_calls
    for path, line, keywords in csv_calls:
        assert _literal_text(keywords.get("file_name", None)).endswith(".csv"), (
            path,
            line,
        )
        assert "data" in keywords, (path, line)


def test_csv_download_contract_requires_bytes_csv_name_and_mime() -> None:
    contract = csv_download_contract(
        data=b"\xef\xbb\xbfsymbol\n7203.T\n",
        file_name="symbols.csv",
    )

    assert isinstance(contract["data"], bytes)
    assert contract["file_name"] == "symbols.csv"
    assert contract["mime"] == CSV_MIME == "text/csv"


def test_csv_download_contract_rejects_invalid_data_or_filename() -> None:
    with pytest.raises(TypeError):
        csv_download_contract(data="not-bytes", file_name="symbols.csv")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        csv_download_contract(data=b"symbols", file_name="symbols.htm")


def test_csv_download_fragment_renders_bytes_contract(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        "ui.components.downloads.st.download_button",
        lambda label, **kwargs: calls.append((label, kwargs)),
    )

    render_csv_download_button.__wrapped__(
        label="CSV保存",
        data=b"\xef\xbb\xbfsymbol\n7203.T\n",
        file_name="symbols.csv",
    )

    assert calls == [
        (
            "CSV保存",
            {
                "data": b"\xef\xbb\xbfsymbol\n7203.T\n",
                "file_name": "symbols.csv",
                "mime": "text/csv",
            },
        )
    ]


def test_csv_download_fragment_warns_instead_of_rendering_empty(monkeypatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(
        "ui.components.downloads.st.warning",
        lambda message: warnings.append(str(message)),
    )
    monkeypatch.setattr(
        "ui.components.downloads.st.download_button",
        lambda *_args, **_kwargs: pytest.fail("empty CSV must not render a button"),
    )

    render_csv_download_button.__wrapped__(
        label="CSV保存",
        data=None,
        file_name="symbols.csv",
    )

    assert warnings == ["CSVに出力できるデータがありません。"]


def _is_csv_download_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id == "render_csv_download_button"
    return isinstance(node.func, ast.Attribute) and node.func.attr == "render_csv_download_button"


def _literal_text(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None
