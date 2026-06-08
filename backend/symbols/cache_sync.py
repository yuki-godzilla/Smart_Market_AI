from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from backend.symbols.cache import SYMBOL_CACHE_DIR
from backend.symbols.contracts import (
    SymbolCacheSyncResult,
    SymbolMetricPruneResult,
    SymbolMetricRecord,
    SymbolRecord,
)
from backend.symbols.metrics_repository import (
    SYMBOL_METRICS_DIR,
    delete_symbol_metric_records,
    load_symbol_metric_records,
    metric_fields_from_mapping,
    save_symbol_metric_records,
)
from backend.symbols.repository import delete_symbol_records, load_symbol_records

DEFAULT_SYMBOL_CACHE_SYNC_MAX_ITEMS = 100


def sync_symbol_cache_to_official_metrics(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    metrics_dir: Path | str | None = None,
    now: datetime | None = None,
    max_items: int = DEFAULT_SYMBOL_CACHE_SYNC_MAX_ITEMS,
    symbols: Sequence[str] | None = None,
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

    loaded_records = load_symbol_records(cache_dir=cache_dir)
    if symbols is None:
        records = _ordered_records(loaded_records)[:max_items]
    else:
        target_symbols = _normalize_symbols(symbols)
        records = [loaded_records[symbol] for symbol in target_symbols if symbol in loaded_records][
            :max_items
        ]
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
                source_as_of=record.source_as_of,
                source_updated_at=record.source_updated_at or record.updated_at,
                cached_at=record.cached_at or record.updated_at,
                promoted_at=current_time,
                fields=metric_fields,
            )
        )
        promoted_symbols.append(record.symbol)

    target_metrics_dir = _target_metrics_dir(cache_dir=cache_dir, metrics_dir=metrics_dir)
    saved_records = save_symbol_metric_records(metric_records, metrics_dir=target_metrics_dir)
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


def prune_symbol_metrics_against_universe(
    universe_rows: Sequence[dict[str, str]],
    *,
    metrics_dir: Path | str = SYMBOL_METRICS_DIR,
    remove_inactive: bool = True,
) -> SymbolMetricPruneResult:
    """Delete official metrics for symbols no longer present or active in the master."""

    records = load_symbol_metric_records(metrics_dir=metrics_dir)
    if not records:
        return SymbolMetricPruneResult(
            scanned_count=0,
            deleted_count=0,
            orphan_deleted_count=0,
            inactive_deleted_count=0,
        )

    active_symbols: set[str] = set()
    inactive_symbols: set[str] = set()
    known_symbols: set[str] = set()
    for row in universe_rows:
        symbol = row.get("symbol", "").strip().upper()
        if not symbol:
            continue
        known_symbols.add(symbol)
        is_active = row.get("is_active", "").strip().lower()
        if remove_inactive and is_active == "false":
            inactive_symbols.add(symbol)
        else:
            active_symbols.add(symbol)

    orphan_symbols = [symbol for symbol in records if symbol not in known_symbols]
    inactive_metric_symbols = [
        symbol for symbol in records if symbol in inactive_symbols and symbol not in active_symbols
    ]
    deleted_symbols = sorted({*orphan_symbols, *inactive_metric_symbols})
    deleted_count = delete_symbol_metric_records(deleted_symbols, metrics_dir=metrics_dir)

    return SymbolMetricPruneResult(
        scanned_count=len(records),
        deleted_count=deleted_count,
        orphan_deleted_count=len(orphan_symbols),
        inactive_deleted_count=len(inactive_metric_symbols),
        deleted_symbols=deleted_symbols,
    )


def _ordered_records(records: dict[str, SymbolRecord]) -> list[SymbolRecord]:
    return sorted(
        records.values(),
        key=lambda record: (record.cached_at or record.updated_at, record.symbol),
    )


def _target_metrics_dir(
    *,
    cache_dir: Path | str,
    metrics_dir: Path | str | None,
) -> Path | str:
    if metrics_dir is not None:
        return metrics_dir
    if Path(cache_dir) == Path(SYMBOL_CACHE_DIR):
        return SYMBOL_METRICS_DIR
    return cache_dir


def _normalize_symbols(symbols: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        normalized.append(normalized_symbol)
    return normalized
