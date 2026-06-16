from __future__ import annotations

from app.config import get_settings


def test_get_settings_prefers_smai_ollama_environment(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("SMAI_OLLAMA_MODEL", "qwen3:1.7b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://legacy.local:11434")
    monkeypatch.setenv("SMAI_OLLAMA_BASE_URL", "http://smai.local:11434")
    monkeypatch.setenv("SMAI_LLM_PROFILE", "notebook_dev")

    settings = get_settings()

    assert settings.DEFAULT_LLM_MODEL == "qwen3:1.7b"
    assert settings.DEFAULT_LLM_PROFILE == "notebook_dev"
    assert settings.OLLAMA_BASE_URL == "http://smai.local:11434"
    get_settings.cache_clear()


def test_get_settings_falls_back_to_notebook_profile(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("SMAI_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("DEFAULT_LLM_MODEL", raising=False)
    monkeypatch.delenv("SMAI_LLM_PROFILE", raising=False)

    settings = get_settings()

    assert settings.DEFAULT_LLM_MODEL == "qwen3:1.7b"
    assert settings.DEFAULT_LLM_PROFILE == "notebook_dev"
    get_settings.cache_clear()
