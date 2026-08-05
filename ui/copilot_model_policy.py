"""Deterministic model-profile policy for the Copilot UI."""

from __future__ import annotations

COPILOT_LLM_MODEL_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("notebook_dev", "qwen3:1.7b", "軽量・高速 / 短い相談向け / 低負荷"),
    ("notebook_standard", "qwen3:4b", "標準 / 普段使い向け / 中低負荷"),
    ("desktop_fast", "qwen3:8b", "バランス / 要約・確認向け / 中負荷"),
    ("desktop_analysis", "qwen3:14b", "高精度 / 銘柄分析・RAG向け / 高負荷"),
    ("desktop_heavy", "qwen3:30b", "最高精度 / 詳細分析・レポート向け / 高負荷"),
)


def profile_for_model(model: str, *, fallback: str = "notebook_dev") -> str:
    """Return the configured profile for a discovered model, with an explicit fallback."""

    for profile, option_model, _ in COPILOT_LLM_MODEL_OPTIONS:
        if option_model == model:
            return profile
    return fallback


def model_for_profile(profile: str) -> str:
    """Return the default model for a profile without probing a provider."""

    for option_profile, option_model, _ in COPILOT_LLM_MODEL_OPTIONS:
        if option_profile == profile:
            return option_model
    return "qwen3:1.7b"


def model_option_label(profile: str, model: str, purpose: str) -> str:
    return f"{profile} / {model} - {purpose}"


def model_option_labels() -> list[str]:
    return [
        model_option_label(profile, model, purpose)
        for profile, model, purpose in COPILOT_LLM_MODEL_OPTIONS
    ]


def model_option_from_label(label: str) -> tuple[str, str, str] | None:
    for profile, model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if label == model_option_label(profile, model, purpose):
            return profile, model, purpose
    return None


def profile_model_matches_option(profile: str, model: str) -> bool:
    return any(
        option_profile == profile and option_model == model
        for option_profile, option_model, _ in COPILOT_LLM_MODEL_OPTIONS
    )


def model_option_for_profile_model(profile: str, model: str) -> tuple[str, str, str]:
    for option_profile, option_model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if option_profile == profile and option_model == model:
            return option_profile, option_model, purpose
    for option_profile, option_model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if option_profile == profile:
            return option_profile, option_model, purpose
    for option_profile, option_model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if option_model == model:
            return option_profile, option_model, purpose
    return COPILOT_LLM_MODEL_OPTIONS[0]
