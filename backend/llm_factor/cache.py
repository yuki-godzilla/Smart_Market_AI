from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.core.runtime_paths import CACHE_DIR_ENV, runtime_path_from_env
from backend.llm_factor.contracts import LLMFactorCacheEntry, LLMFactorCacheLookup, LLMFactorResult

LLM_FACTOR_CACHE_DIR: Final[Path] = runtime_path_from_env(CACHE_DIR_ENV, "data/cache")
LLM_FACTOR_CACHE_FILENAME: Final[str] = "llm_factor_results.json"
LLM_FACTOR_TMP_CACHE_FILENAME: Final[str] = "llm_factor_results.tmp.json"
LLM_FACTOR_CACHE_SCHEMA_VERSION: Final[str] = "llm-factor-cache-file-v1"
DEFAULT_LLM_FACTOR_CACHE_TTL_SECONDS: Final[int] = 6 * 60 * 60
MAX_LLM_FACTOR_CACHE_ENTRIES: Final[int] = 200


class _LLMFactorCacheFile(StrictBaseModel):
    schema_version: str = LLM_FACTOR_CACHE_SCHEMA_VERSION
    entries: list[LLMFactorCacheEntry] = Field(default_factory=list)


def llm_factor_cache_key(
    *,
    ticker: str,
    as_of: date,
    source_hash: str,
    model_name: str,
    prompt_version: str,
    schema_version: str | None = None,
    gateway_profile: str | None = None,
) -> str:
    """Return a stable cache key for a factor-generation contract."""

    payload = {
        "ticker": ticker.strip().upper(),
        "as_of": as_of.isoformat(),
        "source_hash": source_hash,
        "model_name": model_name,
        "prompt_version": prompt_version,
    }
    if schema_version:
        payload["schema_version"] = schema_version
    if gateway_profile:
        payload["gateway_profile"] = gateway_profile
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_llm_factor_cache_entry(
    result: LLMFactorResult,
    *,
    cache_key: str,
    expires_at: datetime,
) -> LLMFactorCacheEntry:
    """Create a persisted cache entry from a validated factor result."""

    return LLMFactorCacheEntry(
        cache_key=cache_key,
        ticker=result.ticker,
        as_of=result.as_of,
        source_hash=result.source_hash,
        model_name=result.model_name,
        prompt_version=result.prompt_version,
        generated_at=result.generated_at,
        expires_at=expires_at,
        result=result,
    )


def find_llm_factor_cache_entry(
    *,
    cache_key: str,
    now: datetime | None = None,
    cache_dir: Path | str = LLM_FACTOR_CACHE_DIR,
) -> LLMFactorCacheLookup:
    """Return a valid cache hit, or a miss/expired/invalid status."""

    cache_file, invalid = _load_llm_factor_cache_file(cache_dir=cache_dir)
    if invalid:
        return LLMFactorCacheLookup(cache_key=cache_key, status="invalid", cache_hit=False)

    now_utc = _ensure_utc(now or datetime.now(UTC))
    for entry in cache_file.entries:
        if entry.cache_key != cache_key:
            continue
        if _ensure_utc(entry.expires_at) <= now_utc:
            return LLMFactorCacheLookup(
                cache_key=cache_key,
                status="expired",
                cache_hit=False,
                entry=entry,
            )
        return LLMFactorCacheLookup(
            cache_key=cache_key,
            status="hit",
            cache_hit=True,
            entry=entry,
        )

    return LLMFactorCacheLookup(cache_key=cache_key, status="miss", cache_hit=False)


def save_llm_factor_cache_entry(
    entry: LLMFactorCacheEntry,
    *,
    cache_dir: Path | str = LLM_FACTOR_CACHE_DIR,
    max_entries: int = MAX_LLM_FACTOR_CACHE_ENTRIES,
) -> LLMFactorCacheEntry:
    """Atomically persist a cache entry, keeping only a bounded latest-first list."""

    cache_root = Path(cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_file, _ = _load_llm_factor_cache_file(cache_dir=cache_root)
    entries = [existing for existing in cache_file.entries if existing.cache_key != entry.cache_key]
    entries.insert(0, entry)
    normalized = _LLMFactorCacheFile(entries=entries[: max(1, max_entries)])

    target = _cache_path(cache_root, LLM_FACTOR_CACHE_FILENAME)
    tmp = _cache_path(cache_root, LLM_FACTOR_TMP_CACHE_FILENAME)
    try:
        tmp.write_text(normalized.model_dump_json(indent=2), encoding="utf-8")
        _LLMFactorCacheFile.model_validate_json(tmp.read_text(encoding="utf-8"))
        tmp.replace(target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return entry


def llm_factor_cache_expires_at(
    *,
    now: datetime | None = None,
    ttl_seconds: int = DEFAULT_LLM_FACTOR_CACHE_TTL_SECONDS,
) -> datetime:
    """Return the expiry timestamp for a new cache entry."""

    return _ensure_utc(now or datetime.now(UTC)) + timedelta(seconds=max(1, ttl_seconds))


def _load_llm_factor_cache_file(
    *,
    cache_dir: Path | str,
) -> tuple[_LLMFactorCacheFile, bool]:
    cache_file = _cache_path(cache_dir, LLM_FACTOR_CACHE_FILENAME)
    if not cache_file.exists():
        return _LLMFactorCacheFile(), False
    try:
        return (
            _LLMFactorCacheFile.model_validate_json(cache_file.read_text(encoding="utf-8")),
            False,
        )
    except ValueError:
        return _LLMFactorCacheFile(), True


def _cache_path(cache_dir: Path | str, filename: str) -> Path:
    return Path(cache_dir) / filename


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
