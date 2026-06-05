from __future__ import annotations

from datetime import datetime
from pathlib import Path

from backend.symbols.cache import SYMBOL_CACHE_DIR
from backend.symbols.contracts import (
    SymbolCacheSyncResult,
    SymbolMetricRecord,
    SymbolRecord,
)
from backend.symbols.metrics_repository import (
    metric_fields_from_mapping,
    save_symbol_metric_records,
)
from backend.symbols.repository import delete_symbol_records, load_symbol_records

DEFAULT_SYMBOL_CACHE_SYNC_MAX_ITEMS = 100


def sync_symbol_cache_to_official_metrics(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    now: datetime | None = None,
    max_items: int = DEFAULT_SYMBOL_CACHE_SYNC_MAX_ITEMS,
) -> SymbolCacheSyncResult:
    """Promote usable runtime cache fields to official metrics and remove processed cache."""

    current_time = now or datetime.utcnow()
    if max_items <= 0:
        return SymbolCacheSyncResult(
            scanned_count=0,
            promoted_count=0,
            deleted_count=0,
            missing_deleted_count=0,
            skipped_count=0,
        )

    records = _ordered_records(load_symbol_records(cache_dir=cache_dir))[:max_items]
    metric_records: list[SymbolMetricRecord] = []
    promoted_symbols: list[str] = []
    missing_symbols: list[str] = []
    skipped_count = 0

    for record in records:
        if record.data_freshness_status == "missing":
            missing_symbols.append(record.symbol)
            continue
        metric_fields = metric_fields_from_mapping(record.normalized_fields)
        if not metric_fields:
            skipped_count += 1
            continue
        metric_records.append(
            SymbolMetricRecord(
                symbol=record.symbol,
                source=record.provider,
                source_updated_at=record.updated_at,
                promoted_at=current_time,
                fields=metric_fields,
            )
        )
        promoted_symbols.append(record.symbol)

    saved_records = save_symbol_metric_records(metric_records, cache_dir=cache_dir)
    saved_symbols = [record.symbol for record in saved_records]
    deleted_symbols = [*saved_symbols, *missing_symbols]
    deleted_count = delete_symbol_records(deleted_symbols, cache_dir=cache_dir)

    return SymbolCacheSyncResult(
        scanned_count=len(records),
        promoted_count=len(saved_symbols),
        deleted_count=deleted_count,
        missing_deleted_count=len(missing_symbols),
        skipped_count=skipped_count,
        promoted_symbols=saved_symbols,
        deleted_symbols=deleted_symbols,
    )


def _ordered_records(records: dict[str, SymbolRecord]) -> list[SymbolRecord]:
    return sorted(records.values(), key=lambda record: (record.updated_at, record.symbol))
