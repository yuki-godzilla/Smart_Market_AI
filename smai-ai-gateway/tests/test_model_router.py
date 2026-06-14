from __future__ import annotations

from app.config import GatewaySettings
from app.services.model_router import resolve_model_route


def test_router_uses_fast_profile_for_free_chat_on_notebook():
    route = resolve_model_route(
        settings=GatewaySettings(),
        task_type="free_chat",
        environment_profile="notebook",
    )

    assert route.provider == "ollama"
    assert route.model == "qwen3:4b"
    assert route.profile == "notebook_dev"
    assert route.timeout_seconds == 15.0
    assert route.max_tokens == 120


def test_router_keeps_configured_notebook_profile_lightweight():
    route = resolve_model_route(
        settings=GatewaySettings(),
        task_type="decision_report_draft",
        execution_mode="quality",
        environment_profile="notebook",
    )

    assert route.profile == "notebook_dev"
    assert route.model == "qwen3:4b"
    assert route.timeout_seconds == 90.0
    assert route.max_tokens == 800


def test_router_can_use_larger_analysis_profile_on_desktop():
    route = resolve_model_route(
        settings=GatewaySettings(DEFAULT_LLM_PROFILE="desktop_analysis"),
        task_type="llm_factor_generation",
        execution_mode="quality",
        environment_profile="desktop",
    )

    assert route.profile == "desktop_analysis"
    assert route.model == "qwen3:14b"


def test_router_allows_request_model_to_override_profile_model():
    route = resolve_model_route(
        settings=GatewaySettings(DEFAULT_LLM_PROFILE="desktop_fast"),
        task_type="stock_summary",
        environment_profile="desktop",
        requested_model="qwen3:14b",
    )

    assert route.profile == "desktop_fast"
    assert route.model == "qwen3:14b"


def test_router_rejects_unknown_profile_with_clear_message():
    try:
        resolve_model_route(
            settings=GatewaySettings(DEFAULT_LLM_PROFILE="unknown_profile"),
            task_type="free_chat",
        )
    except ValueError as exc:
        assert "Unknown LLM profile 'unknown_profile'" in str(exc)
        assert "notebook_dev" in str(exc)
    else:
        raise AssertionError("Unknown profile should fail clearly")


def test_router_offline_uses_fallback():
    route = resolve_model_route(
        settings=GatewaySettings(),
        task_type="stock_summary",
        environment_profile="offline",
    )

    assert route.fallback
    assert route.provider == "deterministic"
    assert route.profile == "fallback"
