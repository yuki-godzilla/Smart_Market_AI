from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.config import GatewaySettings
from app.main import app


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "smai-ai-gateway"}


class FakeOllamaClient:
    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings

    def list_models(self) -> list[str]:
        return ["qwen3:1.7b"]


def test_readiness_returns_ollama_model_status(monkeypatch):
    monkeypatch.setattr(main, "settings", GatewaySettings(DEFAULT_LLM_PROFILE="notebook_dev"))
    monkeypatch.setattr(main, "OllamaClient", FakeOllamaClient)
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["gateway"] == "ok"
    assert payload["ollama"] == "ok"
    assert payload["default_model"] == "qwen3:1.7b"
    assert payload["configured_model_installed"] is True
