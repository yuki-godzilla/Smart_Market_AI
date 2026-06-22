from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

from backend.assistant.gateway_client import AssistantGatewayDiagnostic

AssistantWarmupState = Literal[
    "disabled",
    "not_started",
    "warming",
    "gateway_unreachable",
    "provider_unavailable",
    "model_missing",
    "model_loading",
    "retrying",
    "ready",
    "recovered",
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
    max_attempts: int = 1
    last_failure_state: AssistantWarmupState | None = None


class AssistantWarmupManager:
    """Thread-safe background startup probe with bounded retries."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status = AssistantWarmupStatus()
        self._thread: threading.Thread | None = None
        self._recovering = False

    def status(self) -> AssistantWarmupStatus:
        with self._lock:
            return self._status

    def start(
        self,
        probe: Callable[[], AssistantGatewayDiagnostic],
        *,
        enabled: bool = True,
        max_attempts: int = 1,
        retry_backoff_seconds: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> bool:
        max_attempts = max(1, max_attempts)
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
            next_attempt = self._status.attempt + 1
            self._status = AssistantWarmupStatus(
                state="warming",
                step="LLM Gatewayに接続中",
                message="準備中もSMAI標準ナビを利用できます。",
                started_at=now,
                attempt=next_attempt,
                max_attempts=max_attempts,
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(probe, max_attempts, retry_backoff_seconds, sleep, next_attempt),
                name="smai-assistant-warmup",
                daemon=True,
            )
            self._thread.start()
            return True

    def retry(
        self,
        probe: Callable[[], AssistantGatewayDiagnostic],
        *,
        max_attempts: int = 1,
        retry_backoff_seconds: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> bool:
        with self._lock:
            if self._status.state in {"warming", "retrying", "model_loading"}:
                return False
            self._recovering = self._status.state in {
                "fallback",
                "failed",
                "timeout",
                "degraded",
                "gateway_unreachable",
                "provider_unavailable",
                "model_missing",
            }
            self._status = replace(self._status, state="not_started")
        return self.start(
            probe,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
            sleep=sleep,
        )

    def _run(
        self,
        probe: Callable[[], AssistantGatewayDiagnostic],
        max_attempts: int,
        retry_backoff_seconds: float,
        sleep: Callable[[float], None],
        first_attempt: int,
    ) -> None:
        last_diagnostic: AssistantGatewayDiagnostic | None = None
        last_failure: AssistantWarmupState = "failed"
        for offset in range(max_attempts):
            attempt = first_attempt + offset
            if offset:
                delay = retry_backoff_seconds * offset
                self._update_retrying(attempt, max_attempts, last_failure, delay)
                if delay:
                    sleep(delay)
            try:
                diagnostic = probe()
            except TimeoutError:
                last_failure = "timeout"
            except Exception:
                last_failure = "gateway_unreachable"
            else:
                last_diagnostic = diagnostic
                state, step, message = _status_from_diagnostic(diagnostic)
                if state == "ready":
                    with self._lock:
                        recovered = self._recovering
                        self._recovering = False
                    self._complete(
                        state="recovered" if recovered else "ready",
                        step="モデル応答の準備完了",
                        message=("LLM接続が復旧しました。" if recovered else message),
                        diagnostic=diagnostic,
                        attempt=attempt,
                    )
                    return
                last_failure = state
                if state == "model_missing":
                    break
            if offset + 1 >= max_attempts:
                break
        self._complete(
            state="fallback",
            step=_failure_step(last_failure),
            message="LLMを確認できないため、SMAI標準ナビで回答します。",
            diagnostic=last_diagnostic,
            attempt=first_attempt + min(max_attempts, offset + 1) - 1,
            last_failure_state=last_failure,
        )

    def _update_retrying(
        self,
        attempt: int,
        max_attempts: int,
        failure: AssistantWarmupState,
        delay: float,
    ) -> None:
        with self._lock:
            self._status = replace(
                self._status,
                state="retrying",
                step=f"LLM接続を再確認中 ({attempt}/{max_attempts})",
                message=f"{delay:.0f}秒待って再接続しています。",
                attempt=attempt,
                max_attempts=max_attempts,
                last_failure_state=failure,
            )

    def _complete(
        self,
        *,
        state: AssistantWarmupState,
        step: str,
        message: str,
        diagnostic: AssistantGatewayDiagnostic | None = None,
        attempt: int | None = None,
        last_failure_state: AssistantWarmupState | None = None,
    ) -> None:
        with self._lock:
            self._status = replace(
                self._status,
                state=state,
                step=step,
                message=message,
                completed_at=datetime.now(UTC),
                diagnostic=diagnostic,
                attempt=self._status.attempt if attempt is None else attempt,
                last_failure_state=last_failure_state,
            )


def _status_from_diagnostic(
    diagnostic: AssistantGatewayDiagnostic,
) -> tuple[AssistantWarmupState, str, str]:
    if diagnostic.status == "ready":
        return "ready", "モデル応答の準備完了", "LLM: 準備完了"
    if diagnostic.status == "gateway_timeout":
        return "timeout", "LLM応答待ちが時間切れ", "接続を再確認します。"
    if diagnostic.status == "gateway_unavailable":
        return "gateway_unreachable", "LLM Gateway未接続", "接続を再確認します。"
    if diagnostic.status == "provider_unavailable":
        return "provider_unavailable", "LLM provider未接続", "providerを再確認します。"
    if diagnostic.status == "model_missing":
        return "model_missing", "選択モデルを確認できません", "別の利用可能モデルを選べます。"
    return "failed", "LLM Gatewayを確認できません", "接続を再確認します。"


def _failure_step(state: AssistantWarmupState) -> str:
    return {
        "timeout": "LLM応答待ちが時間切れ",
        "gateway_unreachable": "LLM Gateway未接続",
        "provider_unavailable": "LLM provider未接続",
        "model_missing": "選択モデルが見つかりません",
    }.get(state, "LLM接続を確認できません")


_MANAGERS: dict[str, AssistantWarmupManager] = {}
_MANAGERS_LOCK = threading.Lock()


def get_assistant_warmup_manager(key: str) -> AssistantWarmupManager:
    with _MANAGERS_LOCK:
        return _MANAGERS.setdefault(key, AssistantWarmupManager())
