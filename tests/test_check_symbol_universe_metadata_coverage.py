from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tools.check_symbol_universe_metadata_coverage import (
    _select_rows,
    build_metadata_coverage_report,
)


def test_select_rows_filters_metadata_coverage_scope():
    rows = [
        {
            "symbol": "1301.T",
            "asset_type": "stock",
            "market": "jp",
            "metadata_source": "jpx_listed_stock",
        },
        {
            "symbol": "AAPL",
            "asset_type": "stock",
            "market": "us",
            "metadata_source": "sbi_us_stock",
        },
    ]

    selected = _select_rows(
        rows,
        asset_type="stock",
        market="jp",
        metadata_source="jpx_listed_stock",
    )

    assert [row["symbol"] for row in selected] == ["1301.T"]


def test_build_metadata_coverage_report_counts_filled_values():
    rows = [
        {
            "symbol": "1301.T",
            "asset_type": "stock",
            "metadata_source": "jpx_listed_stock",
            "dividend_yield_pct": "",
            "market_cap_tier": "small",
            "per": "",
            "pbr": "",
            "roe_pct": "",
        },
        {
            "symbol": "AAPL",
            "asset_type": "stock",
            "metadata_source": "sbi_us_stock",
            "dividend_yield_pct": "0.5",
            "market_cap_tier": "mega",
            "per": "28",
            "pbr": "38",
            "roe_pct": "145",
        },
    ]

    report = build_metadata_coverage_report(
        rows,
        checked_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
        csv_path=Path("symbol_universe.csv"),
        filters={"asset_type": "stock"},
    )

    assert report["total_rows"] == 2
    assert report["overall"]["by_column"]["market_cap_tier"] == {
        "filled": 2,
        "missing": 0,
        "coverage": 1.0,
    }
    assert report["overall"]["by_column"]["per"] == {
        "filled": 1,
        "missing": 1,
        "coverage": 0.5,
    }
    by_source = report["by_metadata_source"]
    assert by_source["jpx_listed_stock"]["by_column"]["per"]["coverage"] == 0.0
    assert by_source["sbi_us_stock"]["by_column"]["per"]["coverage"] == 1.0
