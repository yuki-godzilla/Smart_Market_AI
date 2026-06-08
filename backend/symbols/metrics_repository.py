from __future__ import annotations

import os
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Final, Iterator

from backend.core.runtime_paths import CACHE_DIR_ENV
from backend.symbols.contracts import SymbolMetricRecord

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYMBOL_METRICS_DIR_ENV: Final[str] = "SMAI_SYMBOL_METRICS_DIR"
SYMBOL_METRICS_DIR: Final[Path] = Path(
    os.environ.get(
        SYMBOL_METRICS_DIR_ENV,
        os.environ.get(CACHE_DIR_ENV, str(PROJECT_ROOT / "data" / "cache")),
    )
)
SYMBOL_METRICS_DB_FILENAME: Final[str] = "symbol_metrics.sqlite"
SYMBOL_METRICS_TABLE: Final[str] = "symbol_metrics"
SQLITE_TIMEOUT_SECONDS = 5.0

OFFICIAL_SYMBOL_METRIC_FIELDS: Final[tuple[str, ...]] = (
    "dividend_category",
    "dividend_yield_pct",
    "market_cap_tier",
    "expense_ratio_pct",
    "trust_fee_pct",
    "aum",
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
)


def load_symbol_metric_records(
    *,
    metrics_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
) -> dict[str, SymbolMetricRecord]:
    """Load official lightweight metrics used for search/filter UI paths."""

    metrics_root = _metrics_root(metrics_dir=metrics_dir, cache_dir=cache_dir)
    try:
        _ensure_metrics_store(metrics_root)
        with _connect(metrics_root) as connection:
            rows = connection.execute(
                f"""
                SELECT symbol, payload_json
                FROM {SYMBOL_METRICS_TABLE}
                ORDER BY symbol
                """
            ).fetchall()
    except (OSError, sqlite3.Error, ValueError):
        return {}

    records: dict[str, SymbolMetricRecord] = {}
    for row in rows:
        try:
            record = SymbolMetricRecord.model_validate_json(str(row["payload_json"]))
        except ValueError:
            continue
        records[record.symbol] = record
    return records


def load_symbol_metric_fields(
    *,
    metrics_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
) -> dict[str, dict[str, str]]:
    """Load only metric fields keyed by symbol."""

    return {
        symbol: dict(record.fields)
        for symbol, record in load_symbol_metric_records(
            metrics_dir=metrics_dir,
            cache_dir=cache_dir,
        ).items()
    }


def save_symbol_metric_records(
    records: Sequence[SymbolMetricRecord],
    *,
    metrics_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
) -> list[SymbolMetricRecord]:
    """Upsert official lightweight metrics."""

    normalized_records = [_normalize_metric_record(record) for record in records]
    normalized_records = [record for record in normalized_records if record.fields]
    if not normalized_records:
        return []

    metrics_root = _metrics_root(metrics_dir=metrics_dir, cache_dir=cache_dir)
    metrics_root.mkdir(parents=True, exist_ok=True)
    _ensure_metrics_store(metrics_root)
    with _connect(metrics_root) as connection:
        connection.executemany(
            f"""
            INSERT INTO {SYMBOL_METRICS_TABLE} (
                symbol,
                payload_json,
                source,
                source_as_of,
                source_updated_at,
                cached_at,
                promoted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                payload_json = excluded.payload_json,
                source = excluded.source,
                source_as_of = excluded.source_as_of,
                source_updated_at = excluded.source_updated_at,
                cached_at = excluded.cached_at,
                promoted_at = excluded.promoted_at
            """,
            [
                (
                    record.symbol,
                    record.model_dump_json(),
                    record.source,
                    (record.source_as_of.isoformat() if record.source_as_of is not None else None),
                    (
                        record.source_updated_at.isoformat()
                        if record.source_updated_at is not None
                        else None
                    ),
                    record.cached_at.isoformat() if record.cached_at is not None else None,
                    record.promoted_at.isoformat(),
                )
                for record in normalized_records
            ],
        )
    return normalized_records


def delete_symbol_metric_records(
    symbols: Sequence[str],
    *,
    metrics_dir: Path | str | None = None,
    cache_dir: Path | str | None = None,
) -> int:
    """Delete official metric records by symbol and return the deleted row count."""

    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return 0
    metrics_root = _metrics_root(metrics_dir=metrics_dir, cache_dir=cache_dir)
    try:
        _ensure_metrics_store(metrics_root)
        with _connect(metrics_root) as connection:
            cursor = connection.executemany(
                f"DELETE FROM {SYMBOL_METRICS_TABLE} WHERE symbol = ?",
                [(symbol,) for symbol in normalized_symbols],
            )
            return cursor.rowcount if cursor.rowcount != -1 else 0
    except (OSError, sqlite3.Error, ValueError):
        return 0


def metric_fields_from_mapping(
    fields: Mapping[str, object],
) -> dict[str, str]:
    """Return official metric fields from a raw field mapping."""

    result: dict[str, str] = {}
    for key in OFFICIAL_SYMBOL_METRIC_FIELDS:
        value = fields.get(key)
        normalized = _field_text(value)
        if normalized:
            result[key] = normalized
    return result


def _normalize_metric_record(record: SymbolMetricRecord) -> SymbolMetricRecord:
    return SymbolMetricRecord(
        symbol=record.symbol.strip().upper(),
        source=_optional_text(record.source),
        source_as_of=record.source_as_of,
        source_updated_at=record.source_updated_at,
        cached_at=record.cached_at,
        promoted_at=record.promoted_at,
        fields=metric_fields_from_mapping(record.fields),
    )


def _field_text(value: object) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().split())
    return text


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _field_text(value)
    return normalized or None


@contextmanager
def _connect(cache_dir: Path | str) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(
        _cache_path(cache_dir, SYMBOL_METRICS_DB_FILENAME),
        timeout=SQLITE_TIMEOUT_SECONDS,
    )
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _ensure_metrics_store(cache_dir: Path | str) -> None:
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    with _connect(cache_root) as connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {SYMBOL_METRICS_TABLE} (
                symbol TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                source TEXT,
                source_as_of TEXT,
                source_updated_at TEXT,
                cached_at TEXT,
                promoted_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(connection, "source_as_of", "TEXT")
        _ensure_column(connection, "cached_at", "TEXT")
        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{SYMBOL_METRICS_TABLE}_source_updated_at
            ON {SYMBOL_METRICS_TABLE}(source_updated_at)
            """
        )


def _cache_path(cache_dir: Path | str, filename: str) -> Path:
    return Path(cache_dir) / filename


def _ensure_column(connection: sqlite3.Connection, column: str, column_type: str) -> None:
    existing_columns = {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({SYMBOL_METRICS_TABLE})").fetchall()
    }
    if column in existing_columns:
        return
    connection.execute(f"ALTER TABLE {SYMBOL_METRICS_TABLE} ADD COLUMN {column} {column_type}")


def _metrics_root(
    *,
    metrics_dir: Path | str | None,
    cache_dir: Path | str | None,
) -> Path:
    if metrics_dir is not None:
        return Path(metrics_dir)
    if cache_dir is not None:
        return Path(cache_dir)
    return SYMBOL_METRICS_DIR


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
