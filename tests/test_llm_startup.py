from __future__ import annotations

from pathlib import Path

from backend.server_ops.llm_startup import (
    DEFAULT_GATEWAY_URL,
    DEFAULT_OLLAMA_URL,
    LocalLlmStartupConfig,
    LocalLlmStartupManager,
    gateway_command,
    is_local_http_url,
    ollama_tags_url,
    run_local_llm_startup,
)


def test_startup_config_defaults_to_enabled_local_runtime() -> None:
    config = LocalLlmStartupConfig.from_environ({})

    assert config.enabled is True
    assert config.warmup_enabled is True
    assert config.gateway_url == DEFAULT_GATEWAY_URL
    assert config.ollama_url == DEFAULT_OLLAMA_URL
    assert ollama_tags_url(config) == f"{DEFAULT_OLLAMA_URL}/api/tags"


def test_local_runtime_guard_rejects_remote_or_non_http_urls() -> None:
    assert is_local_http_url("http://127.0.0.1:8088") is True
    assert is_local_http_url("http://localhost:11434") is True
    assert is_local_http_url("https://127.0.0.1:8088") is False
    assert is_local_http_url("http://gateway.example:8088") is False


def test_startup_launches_missing_local_services_then_warms_model(monkeypatch) -> None:
    config = LocalLlmStartupConfig(
        enabled=True,
        warmup_enabled=True,
        gateway_url=DEFAULT_GATEWAY_URL,
        ollama_url=DEFAULT_OLLAMA_URL,
        model="qwen3:1.7b",
        profile="notebook_dev",
    )
    monkeypatch.setattr("backend.server_ops.llm_startup.GATEWAY_ROOT", Path("."))
    launched: list[tuple[list[str], object]] = []
    warmed: list[LocalLlmStartupConfig] = []

    def launch(command: list[str], cwd: object, _environment: object) -> bool:
        launched.append((command, cwd))
        return True

    def warm_model(received: LocalLlmStartupConfig) -> bool:
        warmed.append(received)
        return True

    result = run_local_llm_startup(
        config,
        environ={},
        probe=lambda _url: False,
        wait_until_ready=lambda _url: True,
        launch=launch,
        warm_model=warm_model,
    )

    assert result.ollama_started is True
    assert result.gateway_started is True
    assert result.model_warmup_requested is True
    assert launched[0][0] == ["ollama", "serve"]
    assert launched[1][0] == gateway_command(config)
    assert warmed == [config]


def test_startup_leaves_remote_provider_and_model_warmup_untouched() -> None:
    config = LocalLlmStartupConfig(
        enabled=True,
        warmup_enabled=True,
        gateway_url="http://gateway.example:8088",
        ollama_url="http://ollama.example:11434",
        model=None,
        profile="notebook_dev",
    )
    launched: list[list[str]] = []

    def launch(command: list[str], _cwd: object, _environment: object) -> bool:
        launched.append(command)
        return True

    result = run_local_llm_startup(
        config,
        probe=lambda _url: (_ for _ in ()).throw(AssertionError("remote probe")),
        launch=launch,
        warm_model=lambda _config: (_ for _ in ()).throw(AssertionError("remote warmup")),
    )

    assert result == result.__class__(False, False, False, False, False)
    assert launched == []


def test_startup_manager_starts_only_one_background_cycle(monkeypatch) -> None:
    manager = LocalLlmStartupManager()
    config = LocalLlmStartupConfig.from_environ({})
    started: list[object] = []

    class Thread:
        def __init__(self, **kwargs) -> None:
            started.append(kwargs)

        def start(self) -> None:
            return None

    monkeypatch.setattr("backend.server_ops.llm_startup.threading.Thread", Thread)

    assert manager.start(config) is True
    assert manager.start(config) is False
    assert len(started) == 1
