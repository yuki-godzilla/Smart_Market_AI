from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.config import GatewaySettings

LlmExecutionMode = Literal["auto", "light", "quality", "off"]
LlmEnvironmentProfile = Literal["notebook", "desktop", "server", "offline"]
LlmTaskType = Literal[
    "free_chat",
    "identity",
    "app_help",
    "capability_help",
    "screen_guidance",
    "stock_summary",
    "forecast_risk_compare",
    "news_materials",
    "rag_summary",
    "decision_report_draft",
    "llm_factor_generation",
    "report_export_summary",
]
LlmProfileName = Literal[
    "notebook_dev",
    "notebook_standard",
    "desktop_fast",
    "desktop_analysis",
    "desktop_heavy",
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


@dataclass(frozen=True)
class LlmModelProfile:
    provider: str
    model: str
    purpose: str
    timeout_seconds: float
    max_tokens: int


MODEL_PROFILES: dict[str, LlmModelProfile] = {
    "notebook_dev": LlmModelProfile(
        provider="ollama",
        model="qwen3:1.7b",
        purpose="軽量開発・疎通確認",
        timeout_seconds=75.0,
        max_tokens=800,
    ),
    "notebook_standard": LlmModelProfile(
        provider="ollama",
        model="qwen3:4b",
        purpose="ノートPC標準開発・短めの整理",
        timeout_seconds=90.0,
        max_tokens=1000,
    ),
    "desktop_fast": LlmModelProfile(
        provider="ollama",
        model="qwen3:8b",
        purpose="通常Copilot・ニュース要約",
        timeout_seconds=60.0,
        max_tokens=1200,
    ),
    "desktop_analysis": LlmModelProfile(
        provider="ollama",
        model="qwen3:14b",
        purpose="銘柄分析・RAG統合回答",
        timeout_seconds=120.0,
        max_tokens=2000,
    ),
    "desktop_heavy": LlmModelProfile(
        provider="ollama",
        model="qwen3:30b",
        purpose="週次レポート・重要銘柄深掘り",
        timeout_seconds=240.0,
        max_tokens=3000,
    ),
}

_PROFILE_ALIASES: dict[LlmProfileName, str] = {
    "notebook_dev": "notebook_dev",
    "notebook_standard": "notebook_standard",
    "desktop_fast": "desktop_fast",
    "desktop_analysis": "desktop_analysis",
    "desktop_heavy": "desktop_heavy",
    "assistant_fast": "notebook_dev",
    "assistant_standard": "desktop_fast",
    "assistant_quality": "desktop_analysis",
    "report_quality": "desktop_heavy",
    "fallback": "notebook_dev",
}


_TASK_DEFAULTS: dict[LlmTaskType, LlmProfileName] = {
    "free_chat": "notebook_dev",
    "identity": "notebook_dev",
    "app_help": "notebook_dev",
    "capability_help": "notebook_dev",
    "screen_guidance": "notebook_dev",
    "stock_summary": "desktop_fast",
    "forecast_risk_compare": "desktop_fast",
    "news_materials": "desktop_fast",
    "rag_summary": "desktop_fast",
    "decision_report_draft": "desktop_heavy",
    "llm_factor_generation": "desktop_analysis",
    "report_export_summary": "desktop_heavy",
}

_LIGHT_DOWNGRADES: dict[LlmProfileName, LlmProfileName] = {
    "desktop_analysis": "desktop_fast",
    "desktop_heavy": "desktop_fast",
    "assistant_quality": "desktop_fast",
    "report_quality": "desktop_fast",
}

_QUALITY_UPGRADES: dict[LlmTaskType, LlmProfileName] = {
    "news_materials": "desktop_analysis",
    "rag_summary": "desktop_analysis",
    "llm_factor_generation": "desktop_analysis",
    "decision_report_draft": "desktop_heavy",
    "report_export_summary": "desktop_heavy",
}

_TASK_RUNTIME_POLICIES: dict[LlmTaskType, tuple[float, int]] = {
    "free_chat": (25.0, 160),
    "identity": (25.0, 160),
    "app_help": (25.0, 220),
    "capability_help": (25.0, 220),
    "screen_guidance": (25.0, 220),
    "stock_summary": (45.0, 600),
    "forecast_risk_compare": (45.0, 700),
    "news_materials": (60.0, 900),
    "rag_summary": (60.0, 900),
    "decision_report_draft": (75.0, 1200),
    "llm_factor_generation": (90.0, 1200),
    "report_export_summary": (75.0, 1400),
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

    profile_locked = preferred_profile is not None or bool(settings.DEFAULT_LLM_PROFILE)
    profile = preferred_profile or _default_profile_for_task(settings, task_type)
    reason = f"{task_type} uses {profile}."

    if not profile_locked and execution_mode == "light":
        profile = _LIGHT_DOWNGRADES.get(profile, profile)
        reason = f"light mode uses {profile} for {task_type}."
    elif not profile_locked and execution_mode == "quality":
        profile = _QUALITY_UPGRADES.get(task_type, profile)
        reason = f"quality mode uses {profile} for {task_type}."

    return _route_for_profile(
        profile=profile,
        task_type=task_type,
        settings=settings,
        environment_profile=environment_profile,
        requested_model=requested_model,
        reason=reason,
    )


def _route_for_profile(
    *,
    profile: LlmProfileName,
    task_type: LlmTaskType,
    settings: GatewaySettings,
    environment_profile: LlmEnvironmentProfile,
    requested_model: str | None,
    reason: str,
) -> ModelRoute:
    profile_config = model_profile_for_name(profile, settings=settings)
    model = requested_model or profile_config.model
    profile_max_tokens = profile_config.max_tokens
    task_timeout_seconds, task_max_tokens = _TASK_RUNTIME_POLICIES[task_type]
    timeout_seconds = task_timeout_seconds
    max_tokens = min(profile_max_tokens, task_max_tokens)
    return ModelRoute(
        provider=profile_config.provider,
        model=model,
        profile=profile,
        timeout_seconds=timeout_seconds,
        max_tokens=max_tokens,
        reason=reason,
    )


def _default_profile_for_task(settings: GatewaySettings, task_type: LlmTaskType) -> LlmProfileName:
    configured = settings.DEFAULT_LLM_PROFILE
    if configured:
        return _profile_name(configured)
    return _TASK_DEFAULTS[task_type]


def model_profile_for_name(
    profile: str,
    *,
    settings: GatewaySettings,
) -> LlmModelProfile:
    name = _PROFILE_ALIASES.get(_profile_name(profile), profile)
    if name not in MODEL_PROFILES:
        available = ", ".join(sorted(MODEL_PROFILES))
        raise ValueError(f"Unknown LLM profile '{profile}'. Available profiles: {available}.")
    base = MODEL_PROFILES[name]
    if name == "notebook_dev" and settings.DEFAULT_LLM_MODEL:
        return LlmModelProfile(
            provider=base.provider,
            model=settings.DEFAULT_LLM_MODEL,
            purpose=base.purpose,
            timeout_seconds=base.timeout_seconds,
            max_tokens=base.max_tokens,
        )
    return base


def _profile_name(profile: str) -> LlmProfileName:
    return profile  # type: ignore[return-value]
