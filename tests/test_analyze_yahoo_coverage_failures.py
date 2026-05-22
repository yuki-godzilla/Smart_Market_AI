from __future__ import annotations

from pathlib import Path

from tools.analyze_yahoo_coverage_failures import (
    _rows_by_symbol_and_alias,
    analyze_failures,
    build_manifest,
    classify_failure,
)


def test_classify_failure_marks_policy_excluded_etf_types_first():
    assert (
        classify_failure(
            {"code": "YAHOO-NO-BARS"},
            {"asset_type": "etf", "is_leveraged": "true", "complexity": "leveraged"},
        )
        == "excluded_leveraged"
    )
    assert (
        classify_failure(
            {"code": "YAHOO-NO-BARS"},
            {"asset_type": "etf", "is_inverse": "true", "complexity": "inverse"},
        )
        == "excluded_inverse"
    )
    assert (
        classify_failure(
            {"code": "YAHOO-NO-BARS"},
            {"asset_type": "etf", "theme": "commodity", "complexity": "beginner"},
        )
        == "excluded_commodity"
    )
    assert (
        classify_failure(
            {"code": "YAHOO-NO-BARS"},
            {
                "asset_type": "etf",
                "theme": "index",
                "complexity": "beginner",
                "broker": "sbi_securities",
                "is_sbi_supported": "true",
                "is_active": "true",
            },
        )
        == "etf_market_mapping_or_yahoo_unsupported"
    )


def test_analyze_failures_adds_symbol_universe_context():
    coverage_rows = [
        {
            "symbol": "UOBA",
            "status": "no_bars",
            "code": "YAHOO-NO-BARS",
            "message": "Yahoo returned no OHLCV bars.",
        },
        {
            "symbol": "AAPL",
            "status": "ok",
            "code": "",
            "message": "",
        },
    ]
    universe_rows = [
        {
            "symbol": "UOBA",
            "name": "United Overseas Bank",
            "asset_type": "stock",
            "market": "us",
            "metadata_source": "sbi_us_stock",
            "broker": "sbi_securities",
            "tradability": "tradable",
            "is_sbi_supported": "true",
            "is_active": "true",
            "is_leveraged": "false",
            "is_inverse": "false",
        }
    ]

    rows = analyze_failures(coverage_rows, universe_rows)

    assert rows == [
        {
            "symbol": "UOBA",
            "canonical_symbol": "UOBA",
            "name": "United Overseas Bank",
            "asset_type": "stock",
            "market": "us",
            "metadata_source": "sbi_us_stock",
            "yahoo_symbol": "",
            "status": "no_bars",
            "code": "YAHOO-NO-BARS",
            "reason": "no_bars_short_window_or_yahoo_unsupported",
            "recommended_action": "review_symbol_status_or_provider_support",
            "policy_allowed": "true",
            "complexity": "",
            "theme": "",
            "is_leveraged": "false",
            "is_inverse": "false",
            "message": "Yahoo returned no OHLCV bars.",
        }
    ]


def test_analyze_failures_resolves_old_symbol_by_alias():
    coverage_rows = [
        {
            "symbol": "BRKB",
            "status": "no_bars",
            "code": "YAHOO-NO-BARS",
            "message": "Yahoo returned no OHLCV bars.",
        },
    ]
    universe_rows = [
        {
            "symbol": "BRK-B",
            "name": "Berkshire Hathaway",
            "asset_type": "stock",
            "market": "us",
            "metadata_source": "yahoo",
            "aliases": "berkshire BRKB",
        }
    ]

    rows = analyze_failures(coverage_rows, universe_rows)

    assert rows[0]["canonical_symbol"] == "BRK-B"
    assert rows[0]["reason"] == "resolved_by_symbol_alias"
    assert _rows_by_symbol_and_alias(universe_rows)["BRKB"]["symbol"] == "BRK-B"


def test_classify_failure_uses_yahoo_symbol_mapping_when_available():
    row = {
        "symbol": "CSOP",
        "asset_type": "etf",
        "theme": "reit",
        "complexity": "beginner",
        "broker": "sbi_securities",
        "is_sbi_supported": "true",
        "is_active": "true",
        "is_leveraged": "false",
        "is_inverse": "false",
        "yahoo_symbol": "SRU.SI",
    }

    reason = classify_failure({"code": "YAHOO-NO-BARS", "symbol": "CSOP"}, row)

    assert reason == "mapped_yahoo_symbol_available"


def test_build_manifest_summarizes_failure_analysis():
    rows = [
        {
            "symbol": "A",
            "asset_type": "stock",
            "reason": "no_bars_short_window_or_yahoo_unsupported",
        },
        {"symbol": "B", "asset_type": "etf", "reason": "excluded_leveraged"},
    ]

    manifest = build_manifest(
        rows,
        coverage_csv=Path("coverage.csv"),
        symbol_universe_csv=Path("symbol_universe.csv"),
    )

    assert manifest["failed_symbols"] == 2
    assert manifest["reason_counts"] == {
        "no_bars_short_window_or_yahoo_unsupported": 1,
        "excluded_leveraged": 1,
    }
    assert manifest["asset_type_counts"] == {"stock": 1, "etf": 1}
