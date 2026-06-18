from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import ValidationError

from .models import CockpitInterpretationResult

COCKPIT_INTERPRETATION_CACHE_DIR = Path("data/cache")
COCKPIT_INTERPRETATION_CACHE_FILE = "cockpit_interpretation_results.json"
DEFAULT_COCKPIT_INTERPRETATION_CACHE_TTL_SECONDS = 60 * 60 * 12


def cockpit_interpretation_cache_key(
    *,
    symbol: str,
    as_of: str,
    context_hash: str,
    prompt_version: str,
    schema_version: str,
    model: str | None,
    gateway_profile: str | None,
) -> str:
    payload = {
        "task_type": "cockpit_interpretation",
        "symbol": symbol.strip().upper(),
        "as_of": as_of,
        "context_hash": context_hash,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "model": model or "gateway",
        "gateway_profile": gateway_profile or "default",
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_cockpit_interpretation_cache_entry(
    *,
    cache_key: str,
    now: datetime,
    cache_dir: Path | str = COCKPIT_INTERPRETATION_CACHE_DIR,
) -> tuple[str, CockpitInterpretationResult | None, datetime | None]:
    entries = _load_entries(cache_dir)
    raw = entries.get(cache_key)
    if not isinstance(raw, dict):
        return "miss", None, None
    try:
        expires_at = _datetime_from_text(raw.get("expires_at"))
        if expires_at is None or expires_at <= _ensure_utc(now):
            return "miss", None, expires_at
        result = CockpitInterpretationResult.model_validate(raw.get("result"))
    except (TypeError, ValidationError, ValueError):
        return "invalid", None, None
    return "hit", result, expires_at


def save_cockpit_interpretation_cache_entry(
    result: CockpitInterpretationResult,
    *,
    cache_key: str,
    expires_at: datetime,
    cache_dir: Path | str = COCKPIT_INTERPRETATION_CACHE_DIR,
) -> None:
    cache_path = _cache_path(cache_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    entries = _load_entries(cache_dir)
    entries[cache_key] = {
        "result": result.model_dump(mode="json"),
        "expires_at": _ensure_utc(expires_at).isoformat(),
    }
    cache_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def cockpit_interpretation_cache_expires_at(
    *,
    now: datetime,
    ttl_seconds: int = DEFAULT_COCKPIT_INTERPRETATION_CACHE_TTL_SECONDS,
) -> datetime:
    return _ensure_utc(now) + timedelta(seconds=ttl_seconds)


def _load_entries(cache_dir: Path | str) -> dict[str, object]:
    path = _cache_path(cache_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _cache_path(cache_dir: Path | str) -> Path:
    return Path(cache_dir) / COCKPIT_INTERPRETATION_CACHE_FILE


def _datetime_from_text(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = datetime.fromisoformat(value)
    return _ensure_utc(parsed)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
