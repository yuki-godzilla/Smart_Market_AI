from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import TypeAdapter

from backend.symbols.cache import SYMBOL_CACHE_DIR
from backend.symbols.contracts import SymbolRecord

SYMBOL_RECORDS_FILENAME: Final[str] = "symbols_cache.json"
SYMBOL_RECORDS_TMP_FILENAME: Final[str] = "symbols_cache.tmp.json"

MAX_NORMALIZED_FIELDS = 80
MAX_FIELD_TEXT_CHARS = 300

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
    """Load normalized latest-only symbol records."""

    records_file = _cache_path(cache_dir, SYMBOL_RECORDS_FILENAME)
    if not records_file.exists():
        return {}
    try:
        return _SYMBOL_RECORD_MAP_ADAPTER.validate_json(records_file.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def load_symbol_record(
    symbol: str,
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> SymbolRecord | None:
    """Load one normalized symbol record if present."""

    return load_symbol_records(cache_dir=cache_dir).get(_normalize_symbol(symbol))


def save_symbol_record(
    record: SymbolRecord,
    *,
    cache_dir: Path | str = SYMBOL_CACHE_DIR,
) -> SymbolRecord:
    """Normalize and atomically upsert one symbol record."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    normalized = normalize_symbol_record(record)
    records = load_symbol_records(cache_dir=cache_root)
    records[normalized.symbol] = normalized

    records_file = _cache_path(cache_root, SYMBOL_RECORDS_FILENAME)
    tmp_file = _cache_path(cache_root, SYMBOL_RECORDS_TMP_FILENAME)
    try:
        tmp_file.write_text(
            _SYMBOL_RECORD_MAP_ADAPTER.dump_json(records, indent=2).decode("utf-8"),
            encoding="utf-8",
        )
        _SYMBOL_RECORD_MAP_ADAPTER.validate_json(tmp_file.read_text(encoding="utf-8"))
        tmp_file.replace(records_file)
    finally:
        if tmp_file.exists():
            tmp_file.unlink()
    return normalized


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
