from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast

import streamlit as st

from backend.assistant import AssistantResponse

COPILOT_RUNTIME_STATUS_STATE_KEY = "smai_copilot_runtime_status"

AssistantRuntimeState = Literal[
    "ready",
    "checking",
    "generating",
    "research_planned",
    "research_running",
    "degraded",
    "gateway_unavailable",
    "provider_unavailable",
    "model_missing",
]

AssistantStatusSeverity = Literal["ready", "checking", "warning", "error"]


@dataclass(frozen=True)
class AssistantRuntimeStatus:
    state: AssistantRuntimeState
    label: str
    message: str
    severity: AssistantStatusSeverity
    provider: str | None
    model: str | None
    profile: str | None
    last_updated_at: str
    last_request_id: str | None = None
    fallback_reason: str | None = None
    gateway_error_type: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True)
class AssistantStatusEvent:
    name: str
    runtime_config: "CopilotGatewayRuntimeConfig"
    response: AssistantResponse | None = None


@dataclass(frozen=True)
class CopilotGatewayRuntimeConfig:
    enabled: bool
    base_url: str
    timeout_seconds: float
    context_answer_path: str
    execution_mode: str
    environment_profile: str
    provider: str = "ollama"
    model: str = "qwen3:1.7b"
    profile: str = "notebook_dev"
    readiness_status: str = "unchecked"
    readiness_message: str = ""
    gateway_url: str = ""
    gateway_error_type: str = ""
    gateway_error_message: str = ""
    http_status: int | None = None
    provider_error_type: str = ""
    provider_error_message: str = ""
    ollama_base_url: str = ""
    installed_models: tuple[str, ...] = ()

    @property
    def mode_label(self) -> str:
        return "LLM Gateway" if self.enabled else "deterministic"

    @property
    def status_label(self) -> str:
        return "LLM接続: ON" if self.enabled else "LLM接続: OFF"

    @property
    def readiness_label(self) -> str:
        if not self.enabled:
            return "準備完了"
        if self.readiness_status == "ready":
            return "準備完了"
        if self.readiness_status == "gateway_unavailable":
            return "LLM接続エラー"
        if self.readiness_status == "gateway_timeout":
            return "LLM接続エラー"
        if self.readiness_status == "provider_unavailable":
            return "Ollama未接続"
        if self.readiness_status == "model_missing":
            return "モデル未取得"
        if self.readiness_status == "gateway_error":
            return "簡易モードで回答中"
        if self.readiness_status == "unchecked":
            return "LLM待機中"
        return "接続確認中"

    @property
    def readiness_tone(self) -> str:
        if not self.enabled:
            return "fallback"
        if self.readiness_status == "ready":
            return "ready"
        if self.readiness_status == "model_missing":
            return "warning"
        if self.readiness_status in {
            "gateway_unavailable",
            "gateway_timeout",
            "provider_unavailable",
        }:
            return "error"
        if self.readiness_status == "gateway_error":
            return "warning"
        return "checking"

    @property
    def readiness_detail(self) -> str:
        if not self.enabled:
            return "deterministic fallback"
        if self.readiness_message:
            return self.readiness_message
        if self.readiness_status == "ready":
            return f"{self.model} 利用可能"
        if self.readiness_status == "unchecked":
            return "送信時にGateway接続を確認します。"
        return "Gateway / Ollama の状態を確認しています。"


def derive_assistant_runtime_status(event: AssistantStatusEvent) -> AssistantRuntimeStatus:
    state = _assistant_runtime_state_from_event(event)
    response = event.response
    label, message, severity = _assistant_runtime_status_copy(
        state=state,
        runtime_config=event.runtime_config,
        response=response,
    )
    return AssistantRuntimeStatus(
        state=state,
        label=label,
        message=message,
        severity=severity,
        provider=(
            response.provider if response and response.provider else event.runtime_config.provider
        ),
        model=(response.model if response and response.model else event.runtime_config.model),
        profile=(
            response.profile if response and response.profile else event.runtime_config.profile
        ),
        last_updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        last_request_id=response.request_id if response else None,
        fallback_reason=response.fallback_reason if response else None,
        gateway_error_type=(
            response.gateway_error_type
            if response
            else event.runtime_config.gateway_error_type or None
        ),
        latency_ms=response.latency_ms if response else None,
    )


def update_assistant_runtime_status(event: AssistantStatusEvent) -> AssistantRuntimeStatus:
    status = derive_assistant_runtime_status(event)
    st.session_state[COPILOT_RUNTIME_STATUS_STATE_KEY] = _runtime_status_to_state(status)
    return status


def _assistant_runtime_state_from_event(event: AssistantStatusEvent) -> AssistantRuntimeState:
    if event.name == "model_changed":
        return "checking"
    if event.name in {"request_started", "generating"}:
        return "generating"
    if event.name == "research_planned":
        return "research_planned"
    if event.name == "research_running":
        return "research_running"
    if event.name == "cancelled":
        return "ready"
    if event.name == "response_completed" and event.response is not None:
        return _assistant_runtime_state_from_response(event.response)
    return _assistant_runtime_state_from_config(event.runtime_config)


def _assistant_runtime_state_from_config(
    runtime_config: CopilotGatewayRuntimeConfig,
) -> AssistantRuntimeState:
    if not runtime_config.enabled:
        return "degraded"
    if runtime_config.readiness_status == "ready":
        return "ready"
    if runtime_config.readiness_status in {"gateway_unavailable", "gateway_timeout"}:
        return "gateway_unavailable"
    if runtime_config.readiness_status == "provider_unavailable":
        return "provider_unavailable"
    if runtime_config.readiness_status == "model_missing":
        return "model_missing"
    if runtime_config.readiness_status == "gateway_error":
        return "degraded"
    return "checking"


def _assistant_runtime_state_from_response(response: AssistantResponse) -> AssistantRuntimeState:
    if response.gateway_status == "ok" or response.response_source in {"llm", "gateway"}:
        return "ready"
    reason = str(response.fallback_reason or "").strip()
    if reason in {"gateway_unavailable", "gateway_timeout"}:
        return "gateway_unavailable"
    if reason in {"provider_unavailable", "provider_timeout"}:
        return "provider_unavailable"
    if reason == "model_not_found":
        return "model_missing"
    if reason or response.response_source in {"deterministic_fallback", "fallback"}:
        return "degraded"
    if response.gateway_error_type:
        return "gateway_unavailable"
    if response.provider_error_type:
        return "provider_unavailable"
    return "checking"


def _assistant_runtime_status_copy(
    *,
    state: AssistantRuntimeState,
    runtime_config: CopilotGatewayRuntimeConfig,
    response: AssistantResponse | None,
) -> tuple[str, str, AssistantStatusSeverity]:
    if state == "ready":
        return "準備完了", "SMAIナビは通常回答できます。", "ready"
    if state == "generating":
        return "回答生成中", "SMAIナビが回答を整理しています。", "checking"
    if state == "research_planned":
        return "調査計画あり", "取得前の確認待ちです。", "ready"
    if state == "research_running":
        return "材料確認中", "価格・予測・ニュースなどを確認しています。", "checking"
    if state == "degraded":
        return (
            "簡易モードで回答中",
            "LLM応答が不安定なため、簡易回答に切り替わる場合があります。",
            "warning",
        )
    if state == "gateway_unavailable":
        return "LLM接続エラー", "Gatewayに接続できません。簡易モードで回答します。", "error"
    if state == "provider_unavailable":
        return "Ollama未接続", "Ollamaまたは選択モデルに接続できません。", "error"
    if state == "model_missing":
        return "モデル未取得", "選択中のモデルがOllamaに見つかりません。", "warning"
    if state == "checking" and runtime_config.readiness_status == "unchecked":
        return "LLM待機中", "送信時にGateway接続を確認します。", "checking"
    message = runtime_config.readiness_message or "Gateway / Ollama の状態を確認しています。"
    if response and response.gateway_error_message:
        message = "Gateway / Ollama の状態を確認しています。"
    return "接続確認中", message, "checking"


def _runtime_status_to_state(status: AssistantRuntimeStatus) -> dict[str, object]:
    return {
        "state": status.state,
        "label": status.label,
        "message": status.message,
        "severity": status.severity,
        "provider": status.provider,
        "model": status.model,
        "profile": status.profile,
        "last_updated_at": status.last_updated_at,
        "last_request_id": status.last_request_id,
        "fallback_reason": status.fallback_reason,
        "gateway_error_type": status.gateway_error_type,
        "latency_ms": status.latency_ms,
    }


def _runtime_status_from_state(value: object) -> AssistantRuntimeStatus | None:
    if not isinstance(value, dict):
        return None
    raw_state = str(value.get("state", "")).strip()
    if raw_state not in {
        "ready",
        "checking",
        "generating",
        "research_planned",
        "research_running",
        "degraded",
        "gateway_unavailable",
        "provider_unavailable",
        "model_missing",
    }:
        return None
    raw_severity = str(value.get("severity", "")).strip()
    if raw_severity not in {"ready", "checking", "warning", "error"}:
        raw_severity = "checking"
    latency_value = value.get("latency_ms")
    latency_ms = (
        int(latency_value)
        if latency_value is not None and str(latency_value).strip().isdigit()
        else None
    )
    return AssistantRuntimeStatus(
        state=cast(AssistantRuntimeState, raw_state),
        label=str(value.get("label", "")).strip() or "接続確認中",
        message=(
            str(value.get("message", "")).strip() or "Gateway / Ollama の状態を確認しています。"
        ),
        severity=cast(AssistantStatusSeverity, raw_severity),
        provider=str(value.get("provider", "")).strip() or None,
        model=str(value.get("model", "")).strip() or None,
        profile=str(value.get("profile", "")).strip() or None,
        last_updated_at=str(value.get("last_updated_at", "")).strip(),
        last_request_id=str(value.get("last_request_id", "")).strip() or None,
        fallback_reason=str(value.get("fallback_reason", "")).strip() or None,
        gateway_error_type=str(value.get("gateway_error_type", "")).strip() or None,
        latency_ms=latency_ms,
    )


def _runtime_status_matches_runtime_config(
    status: AssistantRuntimeStatus,
    runtime_config: CopilotGatewayRuntimeConfig,
) -> bool:
    return (
        (status.provider or runtime_config.provider) == runtime_config.provider
        and (status.model or runtime_config.model) == runtime_config.model
        and (status.profile or runtime_config.profile) == runtime_config.profile
    )
