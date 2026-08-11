from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from .news_interpretation_models import NewsInterpretationResult

DEFAULT_NEWS_INTERPRETATION_CACHE_TTL_SECONDS = 21600
NEWS_INTERPRETATION_CACHE_FILENAME = "news_interpretation_results.json"


def news_interpretation_cache_key(
    *,
    user_id: str,
    news_context_id: str,
    as_of: str,
    context_hash: str,
    prompt_version: str,
    schema_version: str,
    model: str | None,
    gateway_profile: str | None,
) -> str:
    payload = {
        "task_type": "news_interpretation",
        "user_id": user_id,
        "news_context_id": news_context_id,
        "as_of": as_of,
        "context_hash": context_hash,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "model": model or "gateway",
        "gateway_profile": gateway_profile or "default",
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def find_news_interpretation_cache_entry(
    *, cache_key: str, cache_file: Path, now: datetime
) -> tuple[str, NewsInterpretationResult | None, datetime | None]:
    entries, status = _load(cache_file)
    raw = entries.get(cache_key)
    if not isinstance(raw, dict):
        return status, None, None
    try:
        expires = _parse_datetime(raw.get("expires_at"))
        if expires is None or expires <= _utc(now):
            return "miss", None, expires
        result = NewsInterpretationResult.model_validate(raw.get("result"))
    except (TypeError, ValueError, ValidationError):
        return "invalid", None, None
    if result.status != "live" or result.is_fallback:
        return "invalid", None, None
    return "hit", result, expires


def save_news_interpretation_cache_entry(
    result: NewsInterpretationResult, *, cache_key: str, cache_file: Path, expires_at: datetime
) -> None:
    if result.status != "live" or result.is_fallback:
        return
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    entries, _ = _load(cache_file)
    entries[cache_key] = {
        "result": result.model_dump(mode="json"),
        "expires_at": _utc(expires_at).isoformat(),
    }
    temporary = cache_file.with_suffix(cache_file.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(cache_file)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def news_interpretation_cache_expires_at(*, now: datetime, ttl_seconds: int) -> datetime:
    return _utc(now) + timedelta(seconds=ttl_seconds)


def _load(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, "miss"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "invalid"
    return (payload, "miss") if isinstance(payload, dict) else ({}, "invalid")


def _parse_datetime(value: object) -> datetime | None:
    return _utc(datetime.fromisoformat(value)) if isinstance(value, str) and value else None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
