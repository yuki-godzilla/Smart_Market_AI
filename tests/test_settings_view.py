from __future__ import annotations

from ui.views.settings import SYMBOL_TABLE_PREVIEW_LIMIT, _symbol_table_preview_rows


def test_symbol_table_preview_rows_bounds_large_universe() -> None:
    rows = [{"symbol": f"TEST{index:05d}"} for index in range(11_096)]

    preview = _symbol_table_preview_rows(rows)

    assert len(preview) == SYMBOL_TABLE_PREVIEW_LIMIT
    assert preview[0] == {"symbol": "TEST00000"}
    assert preview[-1] == {"symbol": "TEST00099"}


def test_symbol_table_preview_rows_handles_short_and_zero_limits() -> None:
    rows = [{"symbol": "7203.T"}]

    assert _symbol_table_preview_rows(rows) == rows
    assert _symbol_table_preview_rows(rows, limit=0) == []
