from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

import httpx


@dataclass(frozen=True)
class AssistantModelInfo:
    name: str
    modified_at: datetime | None = None
    size: int | None = None


@dataclass(frozen=True)
class AssistantModelCatalog:
    models: tuple[AssistantModelInfo, ...]
    fetched_at: datetime
    provider: str = "ollama"
    source: str = "gateway"
    error: str = ""


@dataclass(frozen=True)
class AssistantModelSelection:
    model: str
    reason: str


def parse_assistant_model_catalog(
    payload: Mapping[str, Any], *, fetched_at: datetime | None = None
) -> AssistantModelCatalog:
    raw = payload.get("models") or payload.get("model_details") or payload.get("installed_models")
    records: list[AssistantModelInfo] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                name, modified_at, size = item.strip(), None, None
            elif isinstance(item, Mapping):
                name = str(item.get("name") or item.get("model") or "").strip()
                modified_at = _parse_datetime(item.get("modified_at"))
                size = item.get("size") if isinstance(item.get("size"), int) else None
            else:
                continue
            if name:
                records.append(AssistantModelInfo(name, modified_at, size))
    unique = {item.name: item for item in records}
    return AssistantModelCatalog(
        models=tuple(unique.values()),
        fetched_at=fetched_at or datetime.now(UTC),
        provider=str(payload.get("provider") or "ollama"),
    )


def discover_assistant_models(
    base_url: str,
    *,
    timeout_seconds: float = 3.0,
    transport: httpx.BaseTransport | None = None,
) -> AssistantModelCatalog:
    try:
        with httpx.Client(timeout=timeout_seconds, transport=transport) as client:
            response = client.get(f"{base_url.rstrip('/')}/models")
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("invalid models response")
        return parse_assistant_model_catalog(payload)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return AssistantModelCatalog((), datetime.now(UTC), error=type(exc).__name__)


def select_assistant_model(
    catalog: AssistantModelCatalog,
    *,
    user_selected: str = "",
    previous_selected: str = "",
    configured_model: str = "",
    fallback_default: str = "qwen3:1.7b",
) -> AssistantModelSelection:
    names = {item.name for item in catalog.models}
    if names:
        if user_selected in names:
            return AssistantModelSelection(user_selected, "画面で選択したモデル")
        highest = max(catalog.models, key=assistant_model_performance_key)
        return AssistantModelSelection(highest.name, "利用可能な中で最も高性能なモデル")
    if user_selected:
        return AssistantModelSelection(user_selected, "画面で選択したモデル")
    if configured_model:
        return AssistantModelSelection(configured_model, "モデル一覧取得前の接続確認モデル")
    if previous_selected:
        return AssistantModelSelection(previous_selected, "モデル一覧取得前の前回モデル")
    return AssistantModelSelection(fallback_default, "モデル一覧未取得時の既定値")


def assistant_model_performance_key(model: AssistantModelInfo) -> tuple[float, int, str]:
    """Return a deterministic high-to-low capability key for local model names."""

    matches = re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[bB](?![A-Za-z])", model.name)
    parameter_billions = max((float(value) for value in matches), default=0.0)
    return parameter_billions, model.size or 0, model.name.casefold()


def assistant_models_by_performance(
    catalog: AssistantModelCatalog,
) -> tuple[AssistantModelInfo, ...]:
    return tuple(sorted(catalog.models, key=assistant_model_performance_key, reverse=True))


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
