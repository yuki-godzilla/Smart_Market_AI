from datetime import UTC, datetime

import httpx

from backend.assistant.model_discovery import (
    discover_assistant_models,
    parse_assistant_model_catalog,
    select_assistant_model,
)


def test_catalog_parses_gateway_model_metadata_and_selects_newest():
    catalog = parse_assistant_model_catalog(
        {
            "provider": "ollama",
            "models": [
                {"name": "qwen3:4b", "modified_at": "2026-06-19T01:00:00Z"},
                {"name": "qwen3:8b", "modified_at": "2026-06-20T01:00:00Z"},
            ],
        }
    )
    selected = select_assistant_model(catalog)
    assert [item.name for item in catalog.models] == ["qwen3:4b", "qwen3:8b"]
    assert selected.model == "qwen3:8b"
    assert "最も高性能" in selected.reason


def test_default_selection_prefers_performance_over_modified_at():
    catalog = parse_assistant_model_catalog(
        {
            "models": [
                {"name": "qwen3:1.7b", "modified_at": "2026-06-20T10:00:00Z"},
                {"name": "qwen3:30b", "modified_at": "2026-06-19T10:00:00Z"},
                {"name": "qwen3:14b", "modified_at": "2026-06-18T10:00:00Z"},
            ]
        }
    )

    assert select_assistant_model(catalog).model == "qwen3:30b"


def test_model_selection_keeps_user_choice_then_uses_highest_available():
    catalog = parse_assistant_model_catalog(
        {"installed_models": ["qwen3:4b", "qwen3:8b"]},
        fetched_at=datetime(2026, 6, 20, tzinfo=UTC),
    )
    assert (
        select_assistant_model(
            catalog,
            user_selected="qwen3:4b",
            previous_selected="qwen3:8b",
            configured_model="qwen3:8b",
        ).model
        == "qwen3:4b"
    )
    assert (
        select_assistant_model(
            catalog, previous_selected="qwen3:4b", configured_model="qwen3:4b"
        ).model
        == "qwen3:8b"
    )


def test_configured_model_is_only_used_before_catalog_is_available():
    catalog = parse_assistant_model_catalog({"installed_models": []})

    selected = select_assistant_model(catalog, configured_model="qwen3:1.7b")

    assert selected.model == "qwen3:1.7b"
    assert "一覧取得前" in selected.reason


def test_model_discovery_failure_is_safe():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "offline"})

    catalog = discover_assistant_models(
        "http://gateway.local", transport=httpx.MockTransport(handler)
    )
    assert catalog.models == ()
    assert catalog.error
