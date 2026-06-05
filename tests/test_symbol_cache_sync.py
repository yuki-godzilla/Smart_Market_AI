from __future__ import annotations

from datetime import datetime

from backend.symbols.cache_sync import sync_symbol_cache_to_official_metrics
from backend.symbols.contracts import SymbolRecord
from backend.symbols.metrics_repository import load_symbol_metric_records
from backend.symbols.repository import load_symbol_records, save_symbol_records


def test_sync_symbol_cache_promotes_metrics_and_deletes_processed_cache(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    save_symbol_records(
        [
            SymbolRecord(
                symbol="AAPL",
                provider="fake",
                updated_at=now,
                normalized_fields={
                    "per": "18.2",
                    "pbr": "5.1",
                    "name": "Apple",
                    "raw_response": "ignored",
                },
            ),
            SymbolRecord(
                symbol="MISS",
                provider="fake",
                updated_at=now,
                data_freshness_status="missing",
            ),
            SymbolRecord(
                symbol="NAMEONLY",
                provider="fake",
                updated_at=now,
                normalized_fields={"name": "No metric"},
            ),
        ],
        cache_dir=tmp_path,
    )

    result = sync_symbol_cache_to_official_metrics(
        cache_dir=tmp_path,
        now=datetime(2026, 6, 3, 12, 5, 0),
    )

    metrics = load_symbol_metric_records(cache_dir=tmp_path)
    cache_records = load_symbol_records(cache_dir=tmp_path)

    assert result.scanned_count == 3
    assert result.promoted_count == 1
    assert result.missing_deleted_count == 1
    assert result.skipped_count == 1
    assert sorted(result.deleted_symbols) == ["AAPL", "MISS"]
    assert metrics["AAPL"].fields == {"per": "18.2", "pbr": "5.1"}
    assert metrics["AAPL"].source_updated_at == now
    assert sorted(cache_records) == ["NAMEONLY"]


def test_sync_symbol_cache_respects_max_items(tmp_path) -> None:
    now = datetime(2026, 6, 3, 12, 0, 0)
    save_symbol_records(
        [
            SymbolRecord(
                symbol="AAA",
                provider="fake",
                updated_at=now,
                normalized_fields={"per": 1},
            ),
            SymbolRecord(
                symbol="BBB",
                provider="fake",
                updated_at=now,
                normalized_fields={"pbr": 2},
            ),
        ],
        cache_dir=tmp_path,
    )

    result = sync_symbol_cache_to_official_metrics(cache_dir=tmp_path, max_items=1)

    assert result.scanned_count == 1
    assert result.promoted_count == 1
    assert len(load_symbol_records(cache_dir=tmp_path)) == 1
    assert len(load_symbol_metric_records(cache_dir=tmp_path)) == 1
