from __future__ import annotations

from app import main
from app.config import GatewaySettings


class FakeOllamaClient:
    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings

    def list_model_details(self) -> list[dict[str, object]]:
        return [
            {
                "name": "qwen3:8b",
                "modified_at": "2026-06-20T10:00:00Z",
                "size": 8_000_000_000,
            }
        ]


def test_models_endpoint_reports_missing_configured_model(monkeypatch):
    monkeypatch.setattr(main, "settings", GatewaySettings(DEFAULT_LLM_PROFILE="notebook_dev"))
    monkeypatch.setattr(main, "OllamaClient", FakeOllamaClient)

    response = main.models()

    assert response.provider == "ollama"
    assert response.default_profile == "notebook_dev"
    assert response.default_model == "qwen3:1.7b"
    assert response.installed_models == ["qwen3:8b"]
    assert response.models[0].name == "qwen3:8b"
    assert response.models[0].modified_at == "2026-06-20T10:00:00Z"
    assert response.configured_model_installed is False
    assert response.install_hint == "Please run: ollama pull qwen3:1.7b"
