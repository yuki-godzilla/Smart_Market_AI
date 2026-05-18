from __future__ import annotations

from datetime import date

from ui.symbol_universe import (
    SYMBOL_UNIVERSE_REQUIRED_COLUMNS,
    symbol_universe_csv_metadata_summary,
    symbol_universe_csv_rows,
    symbol_universe_csv_validation_issues,
    symbol_universe_metadata_summary,
    validate_symbol_universe_rows,
)


def test_symbol_universe_csv_matches_schema():
    rows = symbol_universe_csv_rows()

    assert rows
    assert rows[0]["metadata_source"] == "curated_csv"
    assert rows[0]["metadata_as_of"] == "2026-05-18"
    assert symbol_universe_csv_validation_issues() == []


def test_symbol_universe_csv_metadata_summary_counts_source_and_freshness():
    summary = symbol_universe_csv_metadata_summary(today=date(2026, 5, 18))

    assert summary["total_rows"] >= 80
    assert summary["source_counts"] == {"curated_csv": summary["total_rows"]}
    assert summary["metadata_period"] == "2026-05-18"
    assert summary["missing_metadata_count"] == 0
    assert summary["stale_metadata_count"] == 0
    assert summary["validation_summary"] == "OK"


def test_validate_symbol_universe_rows_reports_missing_required_column():
    issues = validate_symbol_universe_rows(
        [{"symbol": "AAPL", "name": "Apple Inc."}],
        fieldnames=["symbol", "name"],
    )

    assert "market" in SYMBOL_UNIVERSE_REQUIRED_COLUMNS
    assert any(issue["code"] == "SYMBOL-UNIVERSE-MISSING-COLUMN" for issue in issues)
    assert any(issue["column"] == "market" for issue in issues)


def test_validate_symbol_universe_rows_reports_duplicate_symbol():
    rows = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
        },
        {
            "symbol": "aapl",
            "name": "Apple duplicate",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
        },
    ]

    issues = validate_symbol_universe_rows(rows)

    assert any(issue["code"] == "SYMBOL-UNIVERSE-DUPLICATE-SYMBOL" for issue in issues)


def test_validate_symbol_universe_rows_warns_when_metadata_is_missing():
    rows = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
        }
    ]

    issues = validate_symbol_universe_rows(rows)

    assert [issue for issue in issues if issue["code"] == "SYMBOL-UNIVERSE-MISSING-METADATA"] == [
        {
            "severity": "warning",
            "row": "1",
            "symbol": "AAPL",
            "column": "metadata_source",
            "code": "SYMBOL-UNIVERSE-MISSING-METADATA",
            "message": "metadata_source is not set.",
        },
        {
            "severity": "warning",
            "row": "1",
            "symbol": "AAPL",
            "column": "metadata_as_of",
            "code": "SYMBOL-UNIVERSE-MISSING-METADATA",
            "message": "metadata_as_of is not set.",
        },
    ]


def test_symbol_universe_metadata_summary_counts_stale_rows():
    summary = symbol_universe_metadata_summary(
        [
            {
                "symbol": "AAPL",
                "metadata_source": "curated_csv",
                "metadata_as_of": "2025-01-01",
            }
        ],
        validation_issues=[{"severity": "warning", "code": "SYMBOL-UNIVERSE-MISSING-METADATA"}],
        today=date(2026, 5, 18),
        stale_after_days=180,
    )

    assert summary["source_summary"] == "curated_csv: 1"
    assert summary["metadata_period"] == "2025-01-01"
    assert summary["stale_metadata_count"] == 1
    assert summary["validation_warnings"] == 1


def test_validate_symbol_universe_rows_warns_for_stale_ranking_metadata():
    rows = [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "us",
            "asset_type": "stock",
            "currency": "USD",
            "dividend_yield_pct": "0.5",
            "metadata_source": "curated_csv",
            "metadata_as_of": "2025-01-01",
        }
    ]

    issues = validate_symbol_universe_rows(rows, today=date(2026, 5, 18))

    assert any(
        issue["code"] == "SYMBOL-UNIVERSE-STALE-METADATA"
        and issue["column"] == "dividend_yield_pct"
        for issue in issues
    )


def test_validate_symbol_universe_rows_reports_invalid_values():
    rows = [
        {
            "symbol": "BAD",
            "name": "Invalid row",
            "market": "moon",
            "asset_type": "stock",
            "currency": "USD",
            "dividend_yield_pct": "not-a-number",
            "consensus_rating": "6",
            "tags": "balanced,unknown_tag",
            "metadata_as_of": "2026/05/18",
        }
    ]

    issues = validate_symbol_universe_rows(rows)
    codes = {issue["code"] for issue in issues}

    assert "SYMBOL-UNIVERSE-INVALID-VALUE" in codes
    assert "SYMBOL-UNIVERSE-INVALID-DECIMAL" in codes
    assert "SYMBOL-UNIVERSE-RATING-RANGE" in codes
    assert "SYMBOL-UNIVERSE-INVALID-TAG" in codes
    assert "SYMBOL-UNIVERSE-INVALID-DATE" in codes
