from __future__ import annotations

from app.config import GatewaySettings
from app.services.model_router import resolve_model_route


def test_router_uses_fast_profile_for_free_chat_on_notebook():
    route = resolve_model_route(
        settings=GatewaySettings(DEFAULT_LLM_MODEL="qwen3:8b"),
        task_type="free_chat",
        environment_profile="notebook",
    )

    assert route.provider == "ollama"
    assert route.model == "qwen3:8b"
    assert route.profile == "assistant_fast"
    assert route.timeout_seconds == 30.0
    assert route.max_tokens == 700


def test_router_keeps_quality_profile_lightweight_on_notebook():
    route = resolve_model_route(
        settings=GatewaySettings(DEFAULT_LLM_MODEL="qwen3:8b"),
        task_type="decision_report_draft",
        execution_mode="quality",
        environment_profile="notebook",
    )

    assert route.profile == "report_quality"
    assert route.model == "qwen3:8b"


def test_router_can_use_larger_quality_model_on_desktop():
    route = resolve_model_route(
        settings=GatewaySettings(DEFAULT_LLM_MODEL="qwen3:8b"),
        task_type="llm_factor_generation",
        execution_mode="quality",
        environment_profile="desktop",
    )

    assert route.profile == "assistant_quality"
    assert route.model == "qwen3:14b"


def test_router_offline_uses_fallback():
    route = resolve_model_route(
        settings=GatewaySettings(DEFAULT_LLM_MODEL="qwen3:8b"),
        task_type="stock_summary",
        environment_profile="offline",
    )

    assert route.fallback
    assert route.provider == "deterministic"
    assert route.profile == "fallback"
