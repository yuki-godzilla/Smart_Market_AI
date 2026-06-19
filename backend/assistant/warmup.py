from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

from backend.assistant.gateway_client import AssistantGatewayDiagnostic

AssistantWarmupState = Literal[
    "disabled",
    "not_started",
    "warming",
    "ready",
    "degraded",
    "fallback",
    "failed",
    "timeout",
]


@dataclass(frozen=True)
class AssistantWarmupStatus:
    state: AssistantWarmupState = "not_started"
    step: str = "LLM起動確認を待っています"
    message: str = "SMAI標準ナビはすぐに利用できます。"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    diagnostic: AssistantGatewayDiagnostic | None = None
    attempt: int = 0


class AssistantWarmupManager:
    """Thread-safe, non-blocking startup probe with duplicate prevention."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = AssistantWarmupStatus()
        self._thread: threading.Thread | None = None

    def status(self) -> AssistantWarmupStatus:
        with self._lock:
            return self._status

    def start(
        self,
        probe: Callable[[], AssistantGatewayDiagnostic],
        *,
        enabled: bool = True,
    ) -> bool:
        with self._lock:
            if not enabled:
                self._status = AssistantWarmupStatus(
                    state="disabled",
                    step="LLMは無効です",
                    message="SMAI標準ナビで回答します。",
                )
                return False
            if self._thread is not None and self._thread.is_alive():
                return False
            if self._status.state != "not_started":
                return False
            now = datetime.now(UTC)
            self._status = AssistantWarmupStatus(
                state="warming",
                step="LLM Gatewayに接続中",
                message="準備中もSMAI標準ナビを利用できます。",
                started_at=now,
                attempt=self._status.attempt + 1,
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(probe,),
                name="smai-assistant-warmup",
                daemon=True,
            )
            self._thread.start()
            return True

    def retry(self, probe: Callable[[], AssistantGatewayDiagnostic]) -> bool:
        with self._lock:
            if self._status.state == "warming":
                return False
            self._status = replace(self._status, state="not_started")
        return self.start(probe)

    def _run(self, probe: Callable[[], AssistantGatewayDiagnostic]) -> None:
        try:
            diagnostic = probe()
        except TimeoutError:
            self._complete(
                state="timeout",
                step="LLM応答が時間切れになりました",
                message="通常回答で対応中です。後から再確認できます。",
            )
        except Exception:
            self._complete(
                state="failed",
                step="LLM Gatewayを確認できませんでした",
                message="Gateway未接続のため、通常回答で対応中です。",
            )
        else:
            state, step, message = _status_from_diagnostic(diagnostic)
            self._complete(
                state=state,
                step=step,
                message=message,
                diagnostic=diagnostic,
            )

    def _complete(
        self,
        *,
        state: AssistantWarmupState,
        step: str,
        message: str,
        diagnostic: AssistantGatewayDiagnostic | None = None,
    ) -> None:
        with self._lock:
            self._status = replace(
                self._status,
                state=state,
                step=step,
                message=message,
                completed_at=datetime.now(UTC),
                diagnostic=diagnostic,
            )


def _status_from_diagnostic(
    diagnostic: AssistantGatewayDiagnostic,
) -> tuple[AssistantWarmupState, str, str]:
    if diagnostic.status == "ready":
        return "ready", "モデル応答の準備完了", "LLM: 準備完了"
    if diagnostic.status == "gateway_timeout":
        return "timeout", "LLM起動確認が時間切れ", "通常回答で対応中です。"
    if diagnostic.status in {"provider_unavailable", "model_missing"}:
        return (
            "degraded",
            "モデル準備を確認できません",
            "fallbackありで利用できます。",
        )
    return "failed", "LLM Gatewayを確認できません", "fallbackありで利用できます。"


_MANAGERS: dict[str, AssistantWarmupManager] = {}
_MANAGERS_LOCK = threading.Lock()


def get_assistant_warmup_manager(key: str) -> AssistantWarmupManager:
    with _MANAGERS_LOCK:
        return _MANAGERS.setdefault(key, AssistantWarmupManager())
