from __future__ import annotations

from datetime import date, datetime, timezone

from backend.marketdata.symbol_universe_import import (
    merge_symbol_universe_source_rows,
    symbol_universe_import_fieldnames,
)


def test_merge_symbol_universe_source_rows_imports_new_rows_with_inferred_fields():
    result = merge_symbol_universe_source_rows(
        [{"symbol": "AAPL", "name": "Apple Inc."}],
        [
            {
                "symbol": "1306.T",
                "name": "NEXT FUNDS TOPIX ETF",
                "asset_type": "etf",
                "index_family": "topix",
                "expense_ratio_pct": "0.06",
            }
        ],
        source_name="jpx",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    imported_row = result.rows[1]
    assert imported_row["symbol"] == "1306.T"
    assert imported_row["market"] == "jp"
    assert imported_row["currency"] == "JPY"
    assert imported_row["theme"] == "index"
    assert imported_row["sector"] == "index"
    assert imported_row["complexity"] == "beginner"
    assert imported_row["tags"] == "low_cost"
    assert imported_row["metadata_source"] == "jpx"
    assert imported_row["metadata_as_of"] == "2026-05-18"
    assert result.manifest["imported_symbols"] == ["1306.T"]
    assert result.manifest["imported_rows"] == 1


def test_merge_symbol_universe_source_rows_skips_existing_by_default():
    result = merge_symbol_universe_source_rows(
        [{"symbol": "AAPL", "name": "Apple Inc.", "sector": "technology"}],
        [{"symbol": "aapl", "name": "Apple updated", "sector": "consumer"}],
        source_name="curated_csv",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert result.rows[0]["name"] == "Apple Inc."
    assert result.rows[0]["sector"] == "technology"
    assert result.manifest["skipped_existing_symbols"] == ["AAPL"]
    assert result.manifest["updated_rows"] == 0


def test_merge_symbol_universe_source_rows_updates_existing_when_enabled():
    result = merge_symbol_universe_source_rows(
        [{"symbol": "AAPL", "name": "Apple Inc.", "sector": "technology"}],
        [{"symbol": "AAPL", "name": "Apple updated", "sector": "consumer"}],
        source_name="curated_csv",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
        update_existing=True,
    )

    assert result.rows[0]["name"] == "Apple updated"
    assert result.rows[0]["sector"] == "consumer"
    assert result.rows[0]["metadata_source"] == "curated_csv"
    assert result.manifest["updated_symbols"] == ["AAPL"]
    assert "name" in result.manifest["changed_columns"]


def test_merge_symbol_universe_source_rows_records_missing_name_failure():
    result = merge_symbol_universe_source_rows(
        [],
        [{"symbol": "1306.T"}],
        source_name="jpx",
        as_of=date(2026, 5, 18),
        updated_at=datetime(2026, 5, 18, 0, 0, tzinfo=timezone.utc),
    )

    assert result.rows == []
    assert result.manifest["failed_rows"] == 1
    assert result.manifest["failures"][0]["code"] == "SYMBOL-UNIVERSE-IMPORT-MISSING-NAME"


def test_symbol_universe_import_fieldnames_include_operational_metadata():
    assert set(symbol_universe_import_fieldnames()) >= {
        "symbol",
        "name",
        "market",
        "asset_type",
        "currency",
        "metadata_source",
        "metadata_as_of",
        "metadata_updated_at",
    }
