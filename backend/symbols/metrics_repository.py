from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Final, Iterator

from backend.symbols.cache import SYMBOL_CACHE_DIR
from backend.symbols.contracts import SymbolMetricRecord

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
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> dict[str, SymbolMetricRecord]:
    """Load official lightweight metrics used for search/filter UI paths."""

    cache_root = Path(cache_dir)
    try:
        _ensure_metrics_store(cache_root)
        with _connect(cache_root) as connection:
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
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> dict[str, dict[str, str]]:
    """Load only metric fields keyed by symbol."""

    return {
        symbol: dict(record.fields)
        for symbol, record in load_symbol_metric_records(cache_dir=cache_dir).items()
    }


def save_symbol_metric_records(
    records: Sequence[SymbolMetricRecord],
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> list[SymbolMetricRecord]:
    """Upsert official lightweight metrics."""

    normalized_records = [_normalize_metric_record(record) for record in records]
    normalized_records = [record for record in normalized_records if record.fields]
    if not normalized_records:
        return []

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    _ensure_metrics_store(cache_root)
    with _connect(cache_root) as connection:
        connection.executemany(
            f"""
            INSERT INTO {SYMBOL_METRICS_TABLE} (
                symbol,
                payload_json,
                source,
                source_updated_at,
                promoted_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                payload_json = excluded.payload_json,
                source = excluded.source,
                source_updated_at = excluded.source_updated_at,
                promoted_at = excluded.promoted_at
            """,
            [
                (
                    record.symbol,
                    record.model_dump_json(),
                    record.source,
                    (
                        record.source_updated_at.isoformat()
                        if record.source_updated_at is not None
                        else None
                    ),
                    record.promoted_at.isoformat(),
                )
                for record in normalized_records
            ],
        )
    return normalized_records


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
        source_updated_at=record.source_updated_at,
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
                source_updated_at TEXT,
                promoted_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{SYMBOL_METRICS_TABLE}_source_updated_at
            ON {SYMBOL_METRICS_TABLE}(source_updated_at)
            """
        )


def _cache_path(cache_dir: Path | str, filename: str) -> Path:
    return Path(cache_dir) / filename
