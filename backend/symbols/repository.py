from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Final, Iterator

from pydantic import TypeAdapter

from backend.symbols.cache import SYMBOL_CACHE_DIR
from backend.symbols.contracts import SymbolRecord

SYMBOL_RECORDS_FILENAME: Final[str] = "symbols_cache.json"
SYMBOL_RECORDS_DB_FILENAME: Final[str] = "symbols_cache.sqlite"
SYMBOL_RECORDS_TABLE: Final[str] = "symbol_records"

MAX_NORMALIZED_FIELDS = 80
MAX_FIELD_TEXT_CHARS = 300
SQLITE_TIMEOUT_SECONDS = 5.0

_SYMBOL_RECORD_MAP_ADAPTER = TypeAdapter(dict[str, SymbolRecord])
_RAW_FIELD_KEYWORDS = (
    "raw",
    "html",
    "body",
    "full_text",
    "debug",
    "dump",
    "api_key",
    "token",
    "secret",
)


def load_symbol_records(
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> dict[str, SymbolRecord]:
    """Load normalized latest-only symbol records from the runtime cache DB."""

    cache_root = Path(cache_dir)
    try:
        _ensure_sqlite_store(cache_root)
        with _connect(cache_root) as connection:
            rows = connection.execute(
                f"SELECT symbol, payload_json FROM {SYMBOL_RECORDS_TABLE} ORDER BY symbol"
            ).fetchall()
    except (OSError, sqlite3.Error, ValueError):
        return {}
    try:
        return {
            str(row["symbol"]): SymbolRecord.model_validate_json(str(row["payload_json"]))
            for row in rows
        }
    except ValueError:
        return {}


def load_symbol_record(
    symbol: str,
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> SymbolRecord | None:
    """Load one normalized symbol record if present without scanning all records."""

    cache_root = Path(cache_dir)
    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return None
    try:
        _ensure_sqlite_store(cache_root)
        with _connect(cache_root) as connection:
            row = connection.execute(
                f"SELECT payload_json FROM {SYMBOL_RECORDS_TABLE} WHERE symbol = ?",
                (normalized_symbol,),
            ).fetchone()
    except (OSError, sqlite3.Error, ValueError):
        return None
    if row is None:
        return None
    try:
        return SymbolRecord.model_validate_json(str(row["payload_json"]))
    except ValueError:
        return None


def save_symbol_record(
    record: SymbolRecord,
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> SymbolRecord:
    """Normalize and atomically upsert one symbol record."""

    return save_symbol_records([record], cache_dir=cache_dir)[0]


def save_symbol_records(
    records: Sequence[SymbolRecord],
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> list[SymbolRecord]:
    """Normalize and atomically upsert symbol records into the runtime cache DB."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    normalized_records = [normalize_symbol_record(record) for record in records]
    if not normalized_records:
        return []

    _ensure_sqlite_store(cache_root)
    with _connect(cache_root) as connection:
        connection.executemany(
            f"""
            INSERT INTO {SYMBOL_RECORDS_TABLE} (
                symbol,
                payload_json,
                updated_at,
                provider,
                data_freshness_status
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at,
                provider = excluded.provider,
                data_freshness_status = excluded.data_freshness_status
            """,
            [
                (
                    record.symbol,
                    record.model_dump_json(),
                    record.updated_at.isoformat(),
                    record.provider,
                    record.data_freshness_status,
                )
                for record in normalized_records
            ],
        )
    return normalized_records


def normalize_symbol_record(record: SymbolRecord) -> SymbolRecord:
    """Remove raw/debug fields and bound text before persistence."""

    normalized_fields: dict[str, str | int | float | bool | None] = {}
    for key, value in record.normalized_fields.items():
        normalized_key = key.strip()
        if not normalized_key or _looks_like_raw_field(normalized_key):
            continue
        normalized_fields[normalized_key] = _normalize_field_value(value)
        if len(normalized_fields) >= MAX_NORMALIZED_FIELDS:
            break

    return SymbolRecord(
        schema_version=record.schema_version,
        symbol=_normalize_symbol(record.symbol),
        market=_normalize_optional_text(record.market),
        provider=_normalize_optional_text(record.provider),
        updated_at=record.updated_at,
        last_price_updated_at=record.last_price_updated_at,
        last_fundamental_updated_at=record.last_fundamental_updated_at,
        data_freshness_status=record.data_freshness_status,
        normalized_fields=normalized_fields,
    )


def _looks_like_raw_field(key: str) -> bool:
    normalized = key.lower()
    return any(keyword in normalized for keyword in _RAW_FIELD_KEYWORDS)


def _normalize_field_value(
    value: str | int | float | bool | None,
) -> str | int | float | bool | None:
    if isinstance(value, str):
        return _truncate_text(" ".join(value.strip().split()), MAX_FIELD_TEXT_CHARS)
    return value


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    return normalized or None


def _truncate_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return f"{value[: max_chars - 3]}..."


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _cache_path(cache_dir: Path | str, filename: str) -> Path:
    return Path(cache_dir) / filename


@contextmanager
def _connect(cache_dir: Path | str) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(
        _cache_path(cache_dir, SYMBOL_RECORDS_DB_FILENAME),
        timeout=SQLITE_TIMEOUT_SECONDS,
    )
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _ensure_sqlite_store(cache_dir: Path | str) -> None:
    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    db_file = _cache_path(cache_root, SYMBOL_RECORDS_DB_FILENAME)
    should_migrate = not db_file.exists()
    with _connect(cache_root) as connection:
        _create_symbol_records_table(connection)
        if should_migrate:
            _migrate_legacy_json_records(connection, cache_root)


def _create_symbol_records_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SYMBOL_RECORDS_TABLE} (
            symbol TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            provider TEXT,
            data_freshness_status TEXT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{SYMBOL_RECORDS_TABLE}_updated_at
        ON {SYMBOL_RECORDS_TABLE}(updated_at)
        """
    )


def _migrate_legacy_json_records(connection: sqlite3.Connection, cache_dir: Path) -> None:
    records = _load_legacy_json_records(cache_dir)
    if not records:
        return
    normalized_records = [normalize_symbol_record(record) for record in records.values()]
    connection.executemany(
        f"""
        INSERT OR REPLACE INTO {SYMBOL_RECORDS_TABLE} (
            symbol,
            payload_json,
            updated_at,
            provider,
            data_freshness_status
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                record.symbol,
                record.model_dump_json(),
                record.updated_at.isoformat(),
                record.provider,
                record.data_freshness_status,
            )
            for record in normalized_records
        ],
    )


def _load_legacy_json_records(cache_dir: Path | str) -> dict[str, SymbolRecord]:
    records_file = _cache_path(cache_dir, SYMBOL_RECORDS_FILENAME)
    if not records_file.exists():
        return {}
    try:
        return _SYMBOL_RECORD_MAP_ADAPTER.validate_json(records_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
