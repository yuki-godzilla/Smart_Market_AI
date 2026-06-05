from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

from backend.symbols.cache import (
    SYMBOL_CACHE_DIR,
    cleanup_symbol_refresh_artifacts,
    load_symbol_refresh_queue,
    load_symbol_refresh_status,
)
from backend.symbols.contracts import (
    SymbolImportanceMeta,
    SymbolRecord,
    SymbolRefreshTask,
    SymbolStartupRefreshSummary,
)
from backend.symbols.metrics_repository import load_symbol_metric_records
from backend.symbols.refresh_manager import refresh_symbols_if_needed
from backend.symbols.refresh_priority import (
    MAX_SYMBOL_REFRESH_PER_RUN,
    build_symbol_refresh_queue,
)
from backend.symbols.repository import load_symbol_records

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYMBOL_UNIVERSE_CSV = PROJECT_ROOT / "data" / "marketdata" / "symbol_universe.csv"
MIN_STARTUP_REFRESH_INTERVAL_HOURS = 24

SYMBOL_RECORD_FIELD_KEYS: Final[tuple[str, ...]] = (
    "name",
    "market",
    "asset_type",
    "currency",
    "theme",
    "sector",
    "dividend_category",
    "dividend_yield_pct",
    "market_cap_tier",
    "index_family",
    "expense_ratio_pct",
    "complexity",
    "tags",
    "aliases",
    "per",
    "pbr",
    "roe_pct",
    "consensus_rating",
    "forecast_agreement",
    "data_quality",
    "risk_band",
    "metadata_source",
    "metadata_as_of",
    "metadata_updated_at",
    "yahoo_symbol",
)


def run_symbol_database_startup_refresh(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    symbol_universe_csv: Path | str = SYMBOL_UNIVERSE_CSV,
    now: datetime | None = None,
    max_items: int = MAX_SYMBOL_REFRESH_PER_RUN,
    min_interval_hours: int = MIN_STARTUP_REFRESH_INTERVAL_HOURS,
    force: bool = False,
    currently_visible_symbols: Iterable[str] | None = None,
    ranking_candidates: Iterable[str] | None = None,
) -> SymbolStartupRefreshSummary:
    """Refresh a small local-first symbol DB slice during app startup."""

    current_time = now or datetime.utcnow()
    cleanup_symbol_refresh_artifacts(cache_dir=cache_dir, now=current_time)
    if not force and _startup_refresh_is_recent(
        cache_dir=cache_dir,
        now=current_time,
        min_interval_hours=min_interval_hours,
    ):
        queue = load_symbol_refresh_queue(cache_dir=cache_dir)
        return _summary_from_counts(
            attempted_count=0,
            succeeded_count=0,
            failed_count=0,
            skipped_count=1,
            queue=queue,
            cache_dir=cache_dir,
        )

    rows = _load_symbol_universe_rows(Path(symbol_universe_csv))
    if not rows:
        return SymbolStartupRefreshSummary(
            attempted_count=0,
            succeeded_count=0,
            failed_count=0,
            skipped_count=0,
            pending_like_count=0,
            record_count=len(load_symbol_records(cache_dir=cache_dir)),
        )

    row_by_symbol = {row["symbol"].strip().upper(): row for row in rows if row.get("symbol")}
    symbol_records = _refresh_reference_records(cache_dir=cache_dir)
    currently_visible_symbol_set = _normalize_symbol_set(currently_visible_symbols)
    ranking_candidate_set = _normalize_symbol_set(ranking_candidates)
    tasks = build_symbol_refresh_queue(
        row_by_symbol,
        symbol_records=symbol_records,
        importance_meta=_importance_meta_by_symbol(rows),
        now=current_time,
        reason="startup_refresh",
        currently_visible_symbols=currently_visible_symbol_set,
        ranking_candidates=ranking_candidate_set,
        max_items=max_items,
    )
    if not tasks:
        queue = load_symbol_refresh_queue(cache_dir=cache_dir)
        return _summary_from_counts(
            attempted_count=0,
            succeeded_count=0,
            failed_count=0,
            skipped_count=0,
            queue=queue,
            cache_dir=cache_dir,
        )

    result = refresh_symbols_if_needed(
        provider=lambda task: _record_from_symbol_row(task, row_by_symbol, current_time),
        tasks=tasks,
        cache_dir=cache_dir,
        now=current_time,
        max_items=max_items,
    )
    queue = load_symbol_refresh_queue(cache_dir=cache_dir)
    return _summary_from_counts(
        attempted_count=result.attempted_count,
        succeeded_count=result.succeeded_count,
        failed_count=result.failed_count,
        skipped_count=result.skipped_count,
        queue=queue,
        cache_dir=cache_dir,
        refreshed_symbols=[
            item.symbol for item in result.items if item.success and item.updated_fields
        ],
    )


def run_symbol_database_target_refresh(
    symbols: Iterable[str],
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
    symbol_universe_csv: Path | str = SYMBOL_UNIVERSE_CSV,
    now: datetime | None = None,
    max_items: int = 50,
    force: bool = False,
    currently_visible_symbols: Iterable[str] | None = None,
    ranking_candidates: Iterable[str] | None = None,
) -> SymbolStartupRefreshSummary:
    """Refresh only workflow-target symbols before an explicit user action."""

    current_time = now or datetime.utcnow()
    cleanup_symbol_refresh_artifacts(cache_dir=cache_dir, now=current_time)
    target_symbols = _normalize_symbol_list(symbols)
    queue = load_symbol_refresh_queue(cache_dir=cache_dir)
    if max_items <= 0 or not target_symbols:
        return _summary_from_counts(
            attempted_count=0,
            succeeded_count=0,
            failed_count=0,
            skipped_count=0,
            queue=queue,
            cache_dir=cache_dir,
        )

    rows = _load_symbol_universe_rows(Path(symbol_universe_csv))
    if not rows:
        return _summary_from_counts(
            attempted_count=0,
            succeeded_count=0,
            failed_count=0,
            skipped_count=len(target_symbols),
            queue=queue,
            cache_dir=cache_dir,
        )

    row_by_symbol = {row["symbol"].strip().upper(): row for row in rows if row.get("symbol")}
    known_target_symbols = [symbol for symbol in target_symbols if symbol in row_by_symbol]
    if not known_target_symbols:
        return _summary_from_counts(
            attempted_count=0,
            succeeded_count=0,
            failed_count=0,
            skipped_count=len(target_symbols),
            queue=queue,
            cache_dir=cache_dir,
        )

    known_target_symbol_set = set(known_target_symbols)
    symbol_records = {
        symbol: record
        for symbol, record in _refresh_reference_records(cache_dir=cache_dir).items()
        if symbol in known_target_symbol_set
    }
    currently_visible_symbol_set = _normalize_symbol_set(currently_visible_symbols)
    ranking_candidate_set = _normalize_symbol_set(ranking_candidates)
    tasks = build_symbol_refresh_queue(
        known_target_symbols,
        symbol_records=symbol_records,
        importance_meta=_importance_meta_by_symbol(rows),
        now=current_time,
        reason="target_preflight_refresh",
        force=force,
        currently_visible_symbols=currently_visible_symbol_set,
        ranking_candidates=ranking_candidate_set,
        max_items=max_items,
    )
    if not tasks:
        return _summary_from_counts(
            attempted_count=0,
            succeeded_count=0,
            failed_count=0,
            skipped_count=0,
            queue=load_symbol_refresh_queue(cache_dir=cache_dir),
            cache_dir=cache_dir,
        )

    result = refresh_symbols_if_needed(
        provider=lambda task: _record_from_symbol_row(task, row_by_symbol, current_time),
        tasks=tasks,
        cache_dir=cache_dir,
        now=current_time,
        max_items=max_items,
        force=force,
    )
    queue = load_symbol_refresh_queue(cache_dir=cache_dir)
    return _summary_from_counts(
        attempted_count=result.attempted_count,
        succeeded_count=result.succeeded_count,
        failed_count=result.failed_count,
        skipped_count=result.skipped_count,
        queue=queue,
        cache_dir=cache_dir,
        refreshed_symbols=[
            item.symbol for item in result.items if item.success and item.updated_fields
        ],
    )


def find_pending_symbol_refresh_tasks(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> list[SymbolRefreshTask]:
    """Return tasks that would indicate symbols are still stuck in the refresh queue."""

    return [
        task
        for task in load_symbol_refresh_queue(cache_dir=cache_dir)
        if task.status in {"pending", "retryable", "in_progress"}
    ]


def _startup_refresh_is_recent(
    *,
    cache_dir: Path | str,
    now: datetime,
    min_interval_hours: int,
) -> bool:
    if min_interval_hours <= 0:
        return False
    status = load_symbol_refresh_status(cache_dir=cache_dir)
    last_refresh_at = status.last_success_at or status.last_attempt_at
    if last_refresh_at is None:
        return False
    return now - last_refresh_at < timedelta(hours=min_interval_hours)


def _load_symbol_universe_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [
            {str(key): (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
            if (row.get("symbol") or "").strip()
        ]


def _refresh_reference_records(
    *,
    cache_dir: Path | str,
) -> dict[str, dict[str, datetime]]:
    records = {
        symbol: {"last_refreshed_at": record.updated_at}
        for symbol, record in load_symbol_records(cache_dir=cache_dir).items()
    }
    for symbol, record in load_symbol_metric_records(cache_dir=cache_dir).items():
        if record.source_updated_at is None or symbol in records:
            continue
        records[symbol] = {"last_refreshed_at": record.source_updated_at}
    return records


def _record_from_symbol_row(
    task: SymbolRefreshTask,
    row_by_symbol: dict[str, dict[str, str]],
    now: datetime,
) -> SymbolRecord | None:
    row = row_by_symbol.get(task.symbol)
    if row is None:
        return None
    return SymbolRecord(
        symbol=task.symbol,
        market=_optional_text(row.get("market")),
        provider=_optional_text(row.get("metadata_source")) or "symbol_universe",
        updated_at=now,
        last_price_updated_at=_datetime_value(row.get("metadata_updated_at")),
        last_fundamental_updated_at=_datetime_value(row.get("metadata_updated_at")),
        data_freshness_status="fresh",
        normalized_fields={
            key: value for key in SYMBOL_RECORD_FIELD_KEYS if (value := row.get(key, "").strip())
        },
    )


def _importance_meta_by_symbol(rows: Sequence[dict[str, str]]) -> dict[str, SymbolImportanceMeta]:
    result: dict[str, SymbolImportanceMeta] = {}
    for row in rows:
        symbol = row.get("symbol", "").strip().upper()
        if not symbol:
            continue
        asset_type = row.get("asset_type", "").strip().lower()
        market = row.get("market", "").strip().lower()
        tags = {tag.strip().lower() for tag in row.get("tags", "").split(",") if tag.strip()}
        result[symbol] = SymbolImportanceMeta(
            symbol=symbol,
            is_major_symbol=market in {"jp", "us"},
            is_core_etf=asset_type == "etf" and "low_cost" in tags,
            is_ranking_base_symbol=row.get("is_active", "").strip().lower() != "false",
        )
    return result


def _normalize_symbol_set(symbols: Iterable[str] | None) -> set[str]:
    if symbols is None:
        return set()
    return {symbol.strip().upper() for symbol in symbols if symbol.strip()}


def _normalize_symbol_list(symbols: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _summary_from_counts(
    *,
    attempted_count: int,
    succeeded_count: int,
    failed_count: int,
    skipped_count: int,
    queue: Sequence[SymbolRefreshTask],
    cache_dir: Path | str,
    refreshed_symbols: list[str] | None = None,
) -> SymbolStartupRefreshSummary:
    pending_like_tasks = [
        task for task in queue if task.status in {"pending", "retryable", "in_progress"}
    ]
    return SymbolStartupRefreshSummary(
        attempted_count=attempted_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        pending_like_count=len(pending_like_tasks),
        record_count=len(load_symbol_records(cache_dir=cache_dir)),
        queue_symbols=[task.symbol for task in pending_like_tasks],
        refreshed_symbols=refreshed_symbols or [],
    )


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _datetime_value(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
