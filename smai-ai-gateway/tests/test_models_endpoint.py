from __future__ import annotations

from app import main
from app.config import GatewaySettings


class FakeOllamaClient:
    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings

    def list_models(self) -> list[str]:
        return ["qwen3:8b"]


def test_models_endpoint_reports_missing_configured_model(monkeypatch):
    monkeypatch.setattr(main, "settings", GatewaySettings(DEFAULT_LLM_PROFILE="notebook_dev"))
    monkeypatch.setattr(main, "OllamaClient", FakeOllamaClient)

    response = main.models()

    assert response.provider == "ollama"
    assert response.default_profile == "notebook_dev"
    assert response.default_model == "llama3.2:3b"
    assert response.installed_models == ["qwen3:8b"]
    assert response.configured_model_installed is False
    assert response.install_hint == "Please run: ollama pull llama3.2:3b"
