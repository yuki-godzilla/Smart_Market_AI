from __future__ import annotations

import time

from backend.assistant.gateway_client import AssistantGatewayDiagnostic
from backend.assistant.warmup import AssistantWarmupManager


def _diagnostic(status: str = "ready") -> AssistantGatewayDiagnostic:
    return AssistantGatewayDiagnostic(
        status=status,  # type: ignore[arg-type]
        message="test",
        gateway_url="http://127.0.0.1:8088/models",
    )


def _wait(manager: AssistantWarmupManager) -> str:
    for _ in range(100):
        state = manager.status().state
        if state not in {"warming", "retrying", "model_loading"}:
            return state
        time.sleep(0.005)
    raise AssertionError("warmup did not finish")


def test_warmup_success_and_duplicate_start_prevention():
    manager = AssistantWarmupManager()
    calls = 0

    def probe() -> AssistantGatewayDiagnostic:
        nonlocal calls
        calls += 1
        time.sleep(0.02)
        return _diagnostic()

    assert manager.start(probe) is True
    assert manager.start(probe) is False
    assert _wait(manager) == "ready"
    assert calls == 1
    assert manager.start(probe) is False


def test_warmup_timeout_failure_disabled_and_retry():
    manager = AssistantWarmupManager()
    assert manager.start(lambda: (_ for _ in ()).throw(TimeoutError())) is True
    assert _wait(manager) == "fallback"
    assert manager.status().last_failure_state == "timeout"

    assert manager.retry(lambda: _diagnostic()) is True
    assert _wait(manager) == "recovered"

    disabled = AssistantWarmupManager()
    assert disabled.start(lambda: _diagnostic(), enabled=False) is False
    assert disabled.status().state == "disabled"


def test_warmup_provider_unavailable_uses_fallback():
    manager = AssistantWarmupManager()
    manager.start(lambda: _diagnostic("provider_unavailable"))
    assert _wait(manager) == "fallback"
    assert manager.status().last_failure_state == "provider_unavailable"


def test_warmup_unexpected_probe_failure_becomes_failed():
    manager = AssistantWarmupManager()

    manager.start(lambda: (_ for _ in ()).throw(RuntimeError("provider raw")))

    assert _wait(manager) == "fallback"
    assert manager.status().last_failure_state == "gateway_unreachable"
    assert "provider raw" not in manager.status().message


def test_warmup_retries_then_recovers_without_duplicate_threads():
    manager = AssistantWarmupManager()
    calls = 0

    def probe() -> AssistantGatewayDiagnostic:
        nonlocal calls
        calls += 1
        return _diagnostic("gateway_unavailable" if calls < 3 else "ready")

    assert manager.start(probe, max_attempts=3, retry_backoff_seconds=0) is True
    assert manager.start(probe) is False
    assert _wait(manager) == "ready"
    assert calls == 3
