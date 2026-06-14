from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import GatewaySettings

LlmExecutionMode = Literal["auto", "light", "quality", "off"]
LlmEnvironmentProfile = Literal["notebook", "desktop", "server", "offline"]
LlmTaskType = Literal[
    "free_chat",
    "app_help",
    "stock_summary",
    "forecast_risk_compare",
    "news_materials",
    "rag_summary",
    "decision_report_draft",
    "llm_factor_generation",
    "report_export_summary",
]
LlmProfileName = Literal[
    "assistant_fast",
    "assistant_standard",
    "assistant_quality",
    "report_quality",
    "fallback",
]


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    profile: LlmProfileName
    timeout_seconds: float
    max_tokens: int
    reason: str
    fallback: bool = False


_TASK_DEFAULTS: dict[LlmTaskType, LlmProfileName] = {
    "free_chat": "assistant_fast",
    "app_help": "assistant_fast",
    "stock_summary": "assistant_standard",
    "forecast_risk_compare": "assistant_standard",
    "news_materials": "assistant_standard",
    "rag_summary": "assistant_standard",
    "decision_report_draft": "report_quality",
    "llm_factor_generation": "assistant_quality",
    "report_export_summary": "report_quality",
}

_LIGHT_DOWNGRADES: dict[LlmProfileName, LlmProfileName] = {
    "assistant_quality": "assistant_standard",
    "report_quality": "assistant_standard",
}

_QUALITY_UPGRADES: dict[LlmTaskType, LlmProfileName] = {
    "news_materials": "assistant_quality",
    "rag_summary": "assistant_quality",
    "llm_factor_generation": "assistant_quality",
    "decision_report_draft": "report_quality",
    "report_export_summary": "report_quality",
}


def resolve_model_route(
    *,
    settings: GatewaySettings,
    task_type: LlmTaskType = "free_chat",
    execution_mode: LlmExecutionMode = "auto",
    environment_profile: LlmEnvironmentProfile = "notebook",
    preferred_profile: LlmProfileName | None = None,
    requested_model: str | None = None,
) -> ModelRoute:
    """Resolve a task-aware LLM profile without leaking provider choices to SMAI."""

    if execution_mode == "off" or environment_profile == "offline":
        return ModelRoute(
            provider="deterministic",
            model="fallback",
            profile="fallback",
            timeout_seconds=0.0,
            max_tokens=0,
            reason=f"{execution_mode}/{environment_profile} routes to deterministic fallback.",
            fallback=True,
        )

    profile = preferred_profile or _TASK_DEFAULTS[task_type]
    reason = f"{task_type} uses {profile}."

    if execution_mode == "light":
        profile = _LIGHT_DOWNGRADES.get(profile, profile)
        reason = f"light mode uses {profile} for {task_type}."
    elif execution_mode == "quality":
        profile = _QUALITY_UPGRADES.get(task_type, profile)
        reason = f"quality mode uses {profile} for {task_type}."

    if environment_profile == "notebook" and profile in {"assistant_quality", "report_quality"}:
        reason = f"notebook keeps {profile} on the local 8b model."

    return _route_for_profile(
        profile=profile,
        settings=settings,
        environment_profile=environment_profile,
        requested_model=requested_model,
        reason=reason,
    )


def _route_for_profile(
    *,
    profile: LlmProfileName,
    settings: GatewaySettings,
    environment_profile: LlmEnvironmentProfile,
    requested_model: str | None,
    reason: str,
) -> ModelRoute:
    default_model = requested_model or settings.DEFAULT_LLM_MODEL
    quality_model = "qwen3:8b" if environment_profile == "notebook" else "qwen3:14b"
    report_model = "qwen3:8b" if environment_profile == "notebook" else "qwen3:14b"
    profiles: dict[LlmProfileName, tuple[str, float, int]] = {
        "assistant_fast": (default_model, 30.0, 700),
        "assistant_standard": (default_model, 45.0, 1000),
        "assistant_quality": (quality_model, 60.0, 1200),
        "report_quality": (report_model, 75.0, 1600),
        "fallback": ("fallback", 0.0, 0),
    }
    model, timeout_seconds, max_tokens = profiles[profile]
    return ModelRoute(
        provider="ollama",
        model=model,
        profile=profile,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        reason=reason,
    )
