from __future__ import annotations

from datetime import date

from tools.check_symbol_universe_yahoo_coverage import (
    _even_sample,
    _manifest,
    _select_rows,
)


def test_select_rows_filters_added_jpx_stock_rows():
    rows = [
        {
            "symbol": "1301.T",
            "metadata_source": "jpx_listed_stock",
            "asset_type": "stock",
            "market": "jp",
        },
        {
            "symbol": "AAPL",
            "metadata_source": "sbi_us_stock",
            "asset_type": "stock",
            "market": "us",
        },
        {
            "symbol": "1306.T",
            "metadata_source": "jpx",
            "asset_type": "etf",
            "market": "jp",
        },
    ]

    selected = _select_rows(
        rows,
        metadata_source="jpx_listed_stock",
        asset_type="stock",
        market="jp",
    )

    assert [row["symbol"] for row in selected] == ["1301.T"]


def test_even_sample_spreads_across_symbols():
    symbols = [f"{index}.T" for index in range(10)]

    assert _even_sample(symbols, 4) == ["0.T", "3.T", "6.T", "9.T"]


def test_manifest_summarizes_success_and_failures():
    manifest = _manifest(
        [
            {
                "symbol": "1301.T",
                "status": "ok",
                "bar_count": "5",
                "code": "",
                "message": "",
                "batch_index": "1",
            },
            {
                "symbol": "130A.T",
                "status": "no_bars",
                "bar_count": "0",
                "code": "YAHOO-NO-BARS",
                "message": "missing",
                "batch_index": "1",
            },
        ],
        selected_rows=2,
        metadata_source="jpx_listed_stock",
        asset_type="stock",
        market="jp",
        sample_size=2,
        limit=0,
        batch_size=20,
        timeout_ms=15000,
        start=date(2026, 5, 12),
        end=date(2026, 5, 20),
    )

    assert manifest["checked_symbols"] == 2
    assert manifest["ok_symbols"] == 1
    assert manifest["failed_symbols"] == 1
    assert manifest["success_rate"] == 0.5
    assert manifest["failure_code_counts"] == {"YAHOO-NO-BARS": 1}
    assert manifest["failed_symbol_sample"] == ["130A.T"]
