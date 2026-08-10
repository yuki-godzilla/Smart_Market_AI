from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from .ranking_models import RankingInterpretationResult

RANKING_INTERPRETATION_CACHE_DIR = Path("data/cache")
RANKING_INTERPRETATION_CACHE_FILE = "ranking_interpretation_results.json"
DEFAULT_RANKING_INTERPRETATION_CACHE_TTL_SECONDS = 60 * 60 * 6


def ranking_interpretation_cache_key(
    *,
    ranking_context_id: str,
    as_of: str,
    context_hash: str,
    prompt_version: str,
    schema_version: str,
    model: str | None,
    gateway_profile: str | None,
) -> str:
    payload = {
        "task_type": "ranking_interpretation",
        "ranking_context_id": ranking_context_id,
        "as_of": as_of,
        "context_hash": context_hash,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "model": model or "gateway",
        "gateway_profile": gateway_profile or "default",
    }
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_ranking_interpretation_cache_entry(
    *,
    cache_key: str,
    now: datetime,
    cache_dir: Path | str = RANKING_INTERPRETATION_CACHE_DIR,
) -> tuple[str, RankingInterpretationResult | None, datetime | None]:
    entries, load_status = _load_entries(cache_dir)
    raw = entries.get(cache_key)
    if not isinstance(raw, dict):
        return load_status, None, None
    try:
        expires_at = _datetime_from_text(raw.get("expires_at"))
        if expires_at is None or expires_at <= _ensure_utc(now):
            return "miss", None, expires_at
        result = RankingInterpretationResult.model_validate(raw.get("result"))
    except (TypeError, ValidationError, ValueError):
        return "invalid", None, None
    if result.status != "live" or result.is_fallback:
        return "invalid", None, None
    return "hit", result, expires_at


def save_ranking_interpretation_cache_entry(
    result: RankingInterpretationResult,
    *,
    cache_key: str,
    expires_at: datetime,
    cache_dir: Path | str = RANKING_INTERPRETATION_CACHE_DIR,
) -> None:
    if result.status != "live" or result.is_fallback:
        return
    path = _cache_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries, _ = _load_entries(cache_dir)
    entries[cache_key] = {
        "result": result.model_dump(mode="json"),
        "expires_at": _ensure_utc(expires_at).isoformat(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def ranking_interpretation_cache_expires_at(*, now: datetime, ttl_seconds: int) -> datetime:
    return _ensure_utc(now) + timedelta(seconds=ttl_seconds)


def _load_entries(cache_dir: Path | str) -> tuple[dict[str, object], str]:
    path = _cache_path(cache_dir)
    if not path.exists():
        return {}, "miss"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "invalid"
    return (payload, "miss") if isinstance(payload, dict) else ({}, "invalid")


def _cache_path(cache_dir: Path | str) -> Path:
    return Path(cache_dir) / RANKING_INTERPRETATION_CACHE_FILE


def _datetime_from_text(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return _ensure_utc(datetime.fromisoformat(value))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
