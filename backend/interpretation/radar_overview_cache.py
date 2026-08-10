from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from .radar_overview_models import RadarOverviewInterpretationResult

DEFAULT_RADAR_OVERVIEW_INTERPRETATION_CACHE_TTL_SECONDS = 60 * 60 * 6
RADAR_OVERVIEW_INTERPRETATION_CACHE_FILENAME = "radar_overview_interpretation_results.json"


def radar_overview_interpretation_cache_key(
    *,
    user_id: str,
    radar_context_id: str,
    as_of: str,
    context_hash: str,
    prompt_version: str,
    schema_version: str,
    model: str | None,
    gateway_profile: str | None,
) -> str:
    payload = {
        "task_type": "radar_overview_interpretation",
        "user_id": user_id,
        "radar_context_id": radar_context_id,
        "as_of": as_of,
        "context_hash": context_hash,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "model": model or "gateway",
        "gateway_profile": gateway_profile or "default",
    }
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_radar_overview_interpretation_cache_entry(
    *,
    cache_key: str,
    cache_file: Path,
    now: datetime,
) -> tuple[str, RadarOverviewInterpretationResult | None, datetime | None]:
    entries, load_status = _load_entries(cache_file)
    raw = entries.get(cache_key)
    if not isinstance(raw, dict):
        return load_status, None, None
    try:
        expires_at = _datetime_from_text(raw.get("expires_at"))
        if expires_at is None or expires_at <= _ensure_utc(now):
            return "miss", None, expires_at
        result = RadarOverviewInterpretationResult.model_validate(raw.get("result"))
    except (TypeError, ValidationError, ValueError):
        return "invalid", None, None
    if result.status != "live" or result.is_fallback:
        return "invalid", None, None
    return "hit", result, expires_at


def save_radar_overview_interpretation_cache_entry(
    result: RadarOverviewInterpretationResult,
    *,
    cache_key: str,
    cache_file: Path,
    expires_at: datetime,
) -> None:
    if result.status != "live" or result.is_fallback:
        return
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    entries, _ = _load_entries(cache_file)
    entries[cache_key] = {
        "result": result.model_dump(mode="json"),
        "expires_at": _ensure_utc(expires_at).isoformat(),
    }
    temporary = cache_file.with_suffix(cache_file.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(cache_file)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def radar_overview_interpretation_cache_expires_at(*, now: datetime, ttl_seconds: int) -> datetime:
    return _ensure_utc(now) + timedelta(seconds=ttl_seconds)


def _load_entries(path: Path) -> tuple[dict[str, object], str]:
    if not path.exists():
        return {}, "miss"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "invalid"
    return (payload, "miss") if isinstance(payload, dict) else ({}, "invalid")


def _datetime_from_text(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return _ensure_utc(datetime.fromisoformat(value))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
