from __future__ import annotations

import base64
import html
import json
import os
import time
from collections.abc import MutableMapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Mapping, cast
from urllib.parse import urlencode
from uuid import uuid4

import httpx
import streamlit as st
import streamlit.components.v1 as components

from backend.assistant import (
    AssistantActionExecutor,
    AssistantActionResult,
    AssistantGatewayDiagnostic,
    AssistantGuidedWorkflow,
    AssistantLoadingHeadlines,
    AssistantMessage,
    AssistantModelCatalog,
    AssistantResearchContextBundle,
    AssistantResearchToolPlan,
    AssistantResponse,
    AssistantToolPlanResult,
    AssistantToolResult,
    AssistantWarmupManager,
    AssistantWarmupStatus,
    AssistantWorkflowSession,
    HttpAssistantGatewayClient,
    assistant_models_by_performance,
    assistant_research_bundle_to_decision_report_context,
    assistant_tool_results_from_external_research_failure,
    assistant_tool_results_from_external_research_fetch,
    build_assistant_action_audit_entry,
    build_assistant_context,
    build_assistant_planner_states,
    build_assistant_research_context_bundle,
    build_assistant_research_tool_plan,
    decide_assistant_action_cards,
    detect_assistant_intent,
    execute_assistant_tool_plan,
    get_assistant_action,
    get_assistant_warmup_manager,
    load_assistant_loading_headlines,
    parse_assistant_model_catalog,
    render_research_bundle_markdown_memo,
    route_assistant_conversation_mode,
    select_assistant_model,
)
from backend.assistant import (
    apply_action_result as apply_assistant_workflow_action_result,
)
from backend.assistant import (
    cancel_session as cancel_assistant_workflow_session,
)
from backend.assistant import (
    retry_step as retry_assistant_workflow_step,
)
from backend.assistant import (
    skip_step as skip_assistant_workflow_step,
)
from backend.assistant import (
    start_session as start_assistant_workflow_session,
)
from backend.assistant.response_sanitizer import (
    sanitize_presentation_items,
    sanitize_presentation_text,
)
from backend.core.config import AssistantGatewayConfig, Settings, get_settings
from backend.reporting import (
    DecisionReportContext,
    archive_assistant_decision_report_draft,
    assistant_decision_report_zip_download,
    build_assistant_decision_report_archive_entry,
    render_decision_report_markdown,
)
from ui.components.assistant import (
    SmaiAssistantContext,
    assistant_context_to_report_context,
    assistant_response_for_context,
)
from ui.components.assistant_action_confirm import assistant_action_confirmation_html
from ui.components.assistant_action_result import assistant_action_result_card_html
from ui.components.mascot import (
    MASCOT_NAVI_CHAT_ASSET,
    MASCOT_THUMB_ASSET,
    MASCOT_TITLE_ASSETS,
    _asset_data_uri,
)
from ui.components.sidemenu import (
    SIDEMENU_PAGE_COCKPIT,
    SIDEMENU_PAGE_NEWS,
    SIDEMENU_PAGE_RANKING,
)
from ui.research_state import fetch_external_research_for_symbol

COPILOT_CHAT_HISTORY_STATE_KEY = "smai_copilot_chat_history"
COPILOT_CONVERSATION_ID_STATE_KEY = "smai_copilot_conversation_id"
COPILOT_ACTIVE_INTENT_STATE_KEY = "smai_copilot_active_intent"
COPILOT_PENDING_STREAM_STATE_KEY = "smai_copilot_pending_stream_turn_id"
COPILOT_PENDING_REQUEST_STATE_KEY = "smai_copilot_pending_request"
COPILOT_SUPPRESS_SUBMIT_STATE_KEY = "smai_copilot_suppress_next_submit"
COPILOT_LLM_PROFILE_STATE_KEY = "smai_copilot_llm_profile"
COPILOT_LLM_MODEL_STATE_KEY = "smai_copilot_llm_model"
COPILOT_LLM_MODEL_SELECT_STATE_KEY = "smai_copilot_llm_model_select"
COPILOT_LLM_MODEL_USER_STATE_KEY = "smai_copilot_llm_model_user_selected"
COPILOT_LLM_MODEL_CATALOG_STATE_KEY = "smai_copilot_llm_model_catalog"
COPILOT_LLM_MODEL_REASON_STATE_KEY = "smai_copilot_llm_model_reason"
COPILOT_GATEWAY_DIAGNOSTIC_STATE_KEY = "smai_copilot_gateway_diagnostic"
COPILOT_RUNTIME_STATUS_STATE_KEY = "smai_copilot_runtime_status"
COPILOT_WARMUP_AUTO_TRANSITION_STATE_KEY = "smai_copilot_warmup_auto_transition"
COPILOT_WARMUP_READY_NOTICE_STATE_KEY = "smai_copilot_warmup_ready_notice"
COPILOT_CHAT_LAST_SCROLL_COUNT_STATE_KEY = "smai_copilot_chat_last_scroll_count"
COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY = "pending_decision_report_draft"
COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY = "smai_copilot_pending_action_confirm"
COPILOT_ACTION_AUDIT_STATE_KEY = "smai_copilot_action_audit"
COPILOT_CONFIRMABLE_ACTION_IDS = ("update_research", "create_decision_report")
COPILOT_GATEWAY_DIAGNOSTIC_TTL_SECONDS = 20.0
COPILOT_STREAM_DELAY_SECONDS = 0.16
COPILOT_STREAM_MAX_CHUNKS = 8
COPILOT_PENDING_STEP_DELAY_SECONDS = 0.34
COPILOT_WARMUP_POLL_SECONDS = 2.0

COPILOT_LLM_MODEL_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("notebook_dev", "qwen3:1.7b", "軽量・高速 / 短い相談向け / 低負荷"),
    ("notebook_standard", "qwen3:4b", "標準 / 普段使い向け / 中低負荷"),
    ("desktop_fast", "qwen3:8b", "バランス / 要約・確認向け / 中負荷"),
    ("desktop_analysis", "qwen3:14b", "高精度 / 銘柄分析・RAG向け / 高負荷"),
    ("desktop_heavy", "qwen3:30b", "最高精度 / 詳細分析・レポート向け / 高負荷"),
)

CopilotIntent = Literal[
    "app_help",
    "identity",
    "capability_help",
    "stock_summary",
    "forecast_risk_compare",
    "news_materials",
    "decision_report_draft",
    "free_chat",
    "concept_explanation",
    "broad_discovery",
]

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


@dataclass(frozen=True)
class CopilotConversationPreset:
    intent: CopilotIntent
    label: str
    description: str
    context_id: str
    default_question: str
    prompt_instruction: str


def copilot_context_options() -> tuple[SmaiAssistantContext, ...]:
    return (
        SmaiAssistantContext(
            context_id="copilot_app_help",
            page_key="assistant",
            page_label="SMAIアシスタント",
            section_key="app_help",
            section_label="SMAIの使い方",
            lead=("SMAIの主要画面、確認順、Decision Reportへの残し方を" "初心者向けに案内します。"),
            summary={
                "用途": "SMAIの画面案内",
                "主な材料": "銘柄コックピット、銘柄ランキング、投資レーダー、リバランス",
            },
            suggested_questions=(
                "SMAIでは何から見ればいい？",
                "銘柄コックピットとランキングはどう使い分ける？",
                "Decision Reportには何を残す？",
            ),
            priority=90,
        ),
        SmaiAssistantContext(
            context_id="copilot_cockpit_overview",
            page_key="cockpit",
            page_label="銘柄コックピット",
            section_key="copilot_cockpit",
            section_label="価格・予測・材料確認",
            lead=(
                "1銘柄の価格、AI予測インサイト、上向き気配、下振れ警戒、"
                "根拠資料を横断して整理します。"
            ),
            summary={
                "用途": "単一銘柄の深掘り",
                "主な材料": "価格チャート、AI予測インサイト、Risk、Research Evidence",
            },
            suggested_questions=(
                "この銘柄で最初に確認する材料は？",
                "AI予測インサイトと下振れ警戒をどう比べる？",
                "Decision Reportに残す確認点は？",
            ),
            priority=80,
        ),
        SmaiAssistantContext(
            context_id="copilot_ranking_overview",
            page_key="ranking",
            page_label="銘柄ランキング",
            section_key="copilot_ranking",
            section_label="候補比較",
            lead=(
                "ランキング上位候補を、総合スコア、上向き気配、下振れ警戒、"
                "データ信頼度で比較します。"
            ),
            summary={
                "用途": "候補の比較",
                "主な材料": "AI総合、上向き気配、下振れ警戒、データ信頼度、深掘り候補",
            },
            suggested_questions=(
                "ランキング上位候補は何から比べる？",
                "AI総合・上向き気配・下振れ警戒の違いは？",
                "低信頼データの候補はどう扱う？",
            ),
            priority=70,
        ),
        SmaiAssistantContext(
            context_id="copilot_news_overview",
            page_key="news",
            page_label="投資レーダー",
            section_key="copilot_news",
            section_label="ニュース材料確認",
            lead=("市場ニュース、カテゴリ別材料、関連銘柄、出典と鮮度を分けて確認します。"),
            summary={
                "用途": "ニュースから確認候補を探す",
                "主な材料": "市場ニュース、投資ヒートマップ、関連銘柄、source URL",
            },
            suggested_questions=(
                "今日のニュースはどこから見る？",
                "関連銘柄はどう深掘りする？",
                "出典と鮮度では何を確認する？",
            ),
            priority=60,
        ),
        SmaiAssistantContext(
            context_id="copilot_llm_factor_overview",
            page_key="cockpit",
            page_label="銘柄コックピット",
            section_key="llm_factor_reference",
            section_label="AI材料分析",
            lead=(
                "RAG・ニュース・IR由来の定性材料を参考スコアとして読み、"
                "予測や順位とは分けて扱います。"
            ),
            summary={
                "用途": "定性材料の参考確認",
                "主な材料": "強気材料、弱気材料、カタリスト、リスク、出典URL、材料鮮度",
                "統合状態": "Forecast、Ranking、Investment Scoreには未統合",
            },
            warnings=(
                "LLM材料分析は参考表示であり、売買推奨やランキング順位の決定には使いません。",
            ),
            suggested_questions=(
                "AI材料分析は予測とどう分けて読む？",
                "強気材料と弱気材料の両方が高い時は？",
                "出典URLと材料鮮度では何を見る？",
            ),
            priority=50,
        ),
        SmaiAssistantContext(
            context_id="copilot_rebalance_overview",
            page_key="rebalance",
            page_label="リバランス",
            section_key="copilot_rebalance",
            section_label="配分見直し",
            lead=("現在比率、目標比率、ズレ、模擬取引、リスク警告を確認します。"),
            summary={
                "用途": "配分見直し",
                "主な材料": "現在比率、目標比率、模擬取引、Risk check",
            },
            suggested_questions=(
                "配分のズレは何から見る？",
                "模擬取引はどう確認する？",
                "リスク警告がある時は？",
            ),
            priority=40,
        ),
    )


def copilot_conversation_presets() -> tuple[CopilotConversationPreset, ...]:
    return (
        CopilotConversationPreset(
            intent="app_help",
            label="SMAIの使い方を聞きたい",
            description="画面ごとの役割と、次に開く場所を確認します。",
            context_id="copilot_app_help",
            default_question="SMAIの使い方と、最初に見る画面を教えてください。",
            prompt_instruction=(
                "SMAIの画面と機能を説明し、ユーザーが次に開くべき画面を案内してください。"
            ),
        ),
        CopilotConversationPreset(
            intent="stock_summary",
            label="この銘柄を整理したい",
            description="見る材料、注意点、次に確認することに分けます。",
            context_id="copilot_cockpit_overview",
            default_question="この銘柄を、見る材料・注意点・次に確認することに分けて整理してください。",
            prompt_instruction=(
                "現在の銘柄文脈を、見る材料、注意点、次に確認することに分けて整理してください。"
            ),
        ),
        CopilotConversationPreset(
            intent="forecast_risk_compare",
            label="予測とリスクを比べたい",
            description="予測側とリスク側の温度差を見ます。",
            context_id="copilot_cockpit_overview",
            default_question="AI予測インサイトと下振れ警戒を比べて、確認ポイントを整理してください。",
            prompt_instruction=(
                "予測側の見方、リスク側の見方、矛盾・温度差、確認ポイントの順に整理してください。"
            ),
        ),
        CopilotConversationPreset(
            intent="news_materials",
            label="ニュース材料を見たい",
            description="強気材料、弱気材料、未確認材料を分けます。",
            context_id="copilot_news_overview",
            default_question="ニュースや開示材料を、強気材料・弱気材料・未確認材料に分けて整理してください。",
            prompt_instruction=(
                "ニュース、開示、Research Evidenceを、強気材料、弱気材料、未確認材料、"
                "次に見る資料に分けて整理してください。"
            ),
        ),
        CopilotConversationPreset(
            intent="decision_report_draft",
            label="Decision Reportを作りたい",
            description="判断メモとして残す下書きを作ります。",
            context_id="copilot_cockpit_overview",
            default_question="Decision Reportに残すための整理メモを作ってください。",
            prompt_instruction=(
                "確認した材料、強気材料、弱気材料、未確認事項、次回確認、メモの順に"
                "Decision Reportの下書きを作ってください。"
            ),
        ),
        CopilotConversationPreset(
            intent="free_chat",
            label="自由に会話する",
            description="SMAIや投資材料について自由に相談します。",
            context_id="copilot_app_help",
            default_question="SMAIナビとして、自由相談を始めてください。",
            prompt_instruction=(
                "SMAIナビの口調で自然に会話してください。投資やSMAI以外の話題では、"
                "主な役割がSMAIと投資判断材料の整理であることを添えてください。"
            ),
        ),
    )


def copilot_context_label(context: SmaiAssistantContext) -> str:
    return f"{context.page_label} / {context.section_label}"


def copilot_gateway_runtime_config(
    base_settings: Settings | None = None,
    *,
    probe_gateway: bool = False,
) -> CopilotGatewayRuntimeConfig:
    settings = base_settings or get_settings()
    gateway = settings.assistant.gateway
    selected_profile, selected_model = _selected_llm_profile_model(gateway)

    runtime_config = CopilotGatewayRuntimeConfig(
        enabled=not _is_network_free_app_test_mode(),
        base_url=gateway.base_url,
        timeout_seconds=float(gateway.timeout_seconds),
        context_answer_path=gateway.context_answer_path,
        execution_mode=gateway.execution_mode,
        environment_profile=gateway.environment_profile,
        provider="ollama",
        model=selected_model,
        profile=selected_profile,
    )
    return _with_cached_gateway_diagnostic(
        runtime_config,
        allow_probe=probe_gateway or _assistant_gateway_status_probe_enabled(),
    )


def _is_network_free_app_test_mode() -> bool:
    return (
        os.getenv("SMAI_DISABLE_BACKGROUND_WORKERS") == "1"
        and os.getenv("SMAI_ASSISTANT_GATEWAY_LIVE_SMOKE") != "1"
    )


def _selected_llm_profile_model(gateway: AssistantGatewayConfig) -> tuple[str, str]:
    default_profile = gateway.preferred_profile or os.getenv("SMAI_LLM_PROFILE") or "notebook_dev"
    default_model = (
        gateway.model
        or os.getenv("SMAI_OLLAMA_MODEL")
        or os.getenv("DEFAULT_LLM_MODEL")
        or _model_for_profile(str(default_profile))
    )
    profile = str(st.session_state.get(COPILOT_LLM_PROFILE_STATE_KEY, default_profile))
    catalog = st.session_state.get(COPILOT_LLM_MODEL_CATALOG_STATE_KEY)
    selection = select_assistant_model(
        (
            catalog
            if isinstance(catalog, AssistantModelCatalog)
            else AssistantModelCatalog((), datetime.now(UTC))
        ),
        user_selected=str(st.session_state.get(COPILOT_LLM_MODEL_USER_STATE_KEY, "")),
        previous_selected=str(st.session_state.get(COPILOT_LLM_MODEL_STATE_KEY, "")),
        configured_model=str(default_model),
    )
    model = selection.model
    st.session_state[COPILOT_LLM_MODEL_REASON_STATE_KEY] = selection.reason
    profile = _profile_for_model(model, fallback=profile)
    st.session_state[COPILOT_LLM_PROFILE_STATE_KEY] = profile
    st.session_state[COPILOT_LLM_MODEL_STATE_KEY] = model
    return profile, model


def _profile_for_model(model: str, *, fallback: str = "notebook_dev") -> str:
    for profile, option_model, _ in COPILOT_LLM_MODEL_OPTIONS:
        if option_model == model:
            return profile
    return fallback


def _model_for_profile(profile: str) -> str:
    for option_profile, option_model, _ in COPILOT_LLM_MODEL_OPTIONS:
        if option_profile == profile:
            return option_model
    return "qwen3:1.7b"


def _llm_model_option_label(profile: str, model: str, purpose: str) -> str:
    return f"{profile} / {model} - {purpose}"


def _llm_model_option_labels() -> list[str]:
    return [
        _llm_model_option_label(profile, model, purpose)
        for profile, model, purpose in COPILOT_LLM_MODEL_OPTIONS
    ]


def _llm_model_option_from_label(label: str) -> tuple[str, str, str] | None:
    for profile, model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if label == _llm_model_option_label(profile, model, purpose):
            return profile, model, purpose
    return None


def _llm_profile_model_matches_option(profile: str, model: str) -> bool:
    return any(
        option_profile == profile and option_model == model
        for option_profile, option_model, _ in COPILOT_LLM_MODEL_OPTIONS
    )


def _llm_model_option_for_profile_model(profile: str, model: str) -> tuple[str, str, str]:
    for option_profile, option_model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if option_profile == profile and option_model == model:
            return option_profile, option_model, purpose
    for option_profile, option_model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if option_profile == profile:
            return option_profile, option_model, purpose
    for option_profile, option_model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if option_model == model:
            return option_profile, option_model, purpose
    return COPILOT_LLM_MODEL_OPTIONS[0]


def _render_model_selector(
    runtime_config: CopilotGatewayRuntimeConfig,
) -> CopilotGatewayRuntimeConfig:
    catalog = st.session_state.get(COPILOT_LLM_MODEL_CATALOG_STATE_KEY)
    if not isinstance(catalog, AssistantModelCatalog) or not catalog.models:
        st.selectbox(
            "AIモデル",
            ("モデル一覧を取得中",),
            disabled=True,
            key="smai_copilot_model_loading_select",
        )
        return runtime_config

    available_models = [item.name for item in assistant_models_by_performance(catalog)]
    manual_model = str(st.session_state.get(COPILOT_LLM_MODEL_USER_STATE_KEY, ""))
    if manual_model and manual_model not in available_models:
        st.session_state.pop(COPILOT_LLM_MODEL_USER_STATE_KEY, None)
        manual_model = ""
    model = manual_model if manual_model in available_models else available_models[0]
    stored_model = str(st.session_state.get(COPILOT_LLM_MODEL_SELECT_STATE_KEY, ""))
    if stored_model not in available_models:
        st.session_state.pop(COPILOT_LLM_MODEL_SELECT_STATE_KEY, None)
    selected_model = st.selectbox(
        "AIモデル",
        available_models,
        index=available_models.index(model),
        format_func=_assistant_model_choice_label,
        key=COPILOT_LLM_MODEL_SELECT_STATE_KEY,
    )
    if selected_model != model:
        model = selected_model
        st.session_state[COPILOT_LLM_MODEL_USER_STATE_KEY] = model
        st.session_state[COPILOT_LLM_MODEL_REASON_STATE_KEY] = "画面で選択したモデル"
    elif manual_model != model:
        st.session_state[COPILOT_LLM_MODEL_REASON_STATE_KEY] = "利用可能な中で最も高性能なモデル"
    profile = _profile_for_model(model, fallback=runtime_config.profile)
    st.session_state[COPILOT_LLM_MODEL_STATE_KEY] = model
    st.session_state[COPILOT_LLM_PROFILE_STATE_KEY] = profile
    selected_config = replace(runtime_config, model=model, profile=profile)
    if model != runtime_config.model or profile != runtime_config.profile:
        st.session_state.pop(COPILOT_GATEWAY_DIAGNOSTIC_STATE_KEY, None)
        update_assistant_runtime_status(
            AssistantStatusEvent(name="model_changed", runtime_config=selected_config)
        )
    return selected_config


def _assistant_model_display(model: str) -> tuple[str, str]:
    for _, option_model, purpose in COPILOT_LLM_MODEL_OPTIONS:
        if option_model == model:
            feature = purpose.split(" / ", maxsplit=1)[0]
            return feature, purpose
    return "利用可能", "利用可能モデル / 性能・負荷は提供元の情報を確認"


def _assistant_model_choice_label(model: str, *, badge: str = "") -> str:
    _, purpose = _assistant_model_display(model)
    badge_copy = f"  [{badge}]" if badge else ""
    return f"{model}{badge_copy} — {purpose}"


def _render_chat_composer(
    runtime_config: CopilotGatewayRuntimeConfig,
) -> tuple[str | None, CopilotGatewayRuntimeConfig]:
    submitted = False
    prompt = ""
    model_col, composer_col = st.columns([0.3, 0.7], vertical_alignment="top")
    with model_col:
        st.markdown(
            '<span class="smai-copilot-composer-toolbar" '
            'aria-label="SMAI chat composer"></span>',
            unsafe_allow_html=True,
        )
        selected = _render_model_selector(runtime_config)
    with composer_col:
        with st.form("smai_copilot_composer_form", clear_on_submit=True):
            text_col, send_col = st.columns([0.82, 0.18])
            with text_col:
                prompt = st.text_input(
                    "相談内容",
                    placeholder="価格・予測・ニュース・根拠資料について確認したいことを入力...",
                    key="smai_copilot_text_input",
                    max_chars=240,
                    label_visibility="collapsed",
                )
            with send_col:
                submitted = st.form_submit_button("送信", use_container_width=True)
    return (prompt.strip() if submitted else None), selected


def copilot_settings_from_gateway_runtime(
    runtime_config: CopilotGatewayRuntimeConfig,
    base_settings: Settings | None = None,
) -> Settings:
    settings = base_settings or get_settings()
    gateway = AssistantGatewayConfig(
        enabled=runtime_config.enabled,
        base_url=runtime_config.base_url,
        context_answer_path=runtime_config.context_answer_path,
        timeout_seconds=runtime_config.timeout_seconds,
        model=runtime_config.model,
        execution_mode=cast(
            Literal["auto", "light", "quality", "off"],
            runtime_config.execution_mode,
        ),
        environment_profile=cast(
            Literal["notebook", "desktop", "server", "offline"],
            runtime_config.environment_profile,
        ),
        preferred_profile=runtime_config.profile,  # type: ignore[arg-type]
    )
    assistant_config = settings.assistant.model_copy(update={"gateway": gateway})
    return settings.model_copy(update={"assistant": assistant_config})


def _with_cached_gateway_diagnostic(
    runtime_config: CopilotGatewayRuntimeConfig,
    *,
    allow_probe: bool = False,
) -> CopilotGatewayRuntimeConfig:
    if not runtime_config.enabled:
        return runtime_config

    cache_key = _gateway_diagnostic_cache_key(runtime_config)
    cached = st.session_state.get(COPILOT_GATEWAY_DIAGNOSTIC_STATE_KEY)
    now = time.time()
    if isinstance(cached, dict):
        cached_at = float(cached.get("checked_at", 0.0) or 0.0)
        if (
            cached.get("cache_key") == cache_key
            and now - cached_at < COPILOT_GATEWAY_DIAGNOSTIC_TTL_SECONDS
        ):
            return _runtime_config_from_state(cached.get("runtime_config"))

    if not allow_probe or os.getenv("SMAI_SKIP_ASSISTANT_GATEWAY_STATUS_CHECK") == "1":
        return runtime_config

    diagnosed = _probe_copilot_gateway_runtime(runtime_config)
    _cache_gateway_runtime_config(diagnosed, checked_at=now)
    update_assistant_runtime_status(
        AssistantStatusEvent(name="health_checked", runtime_config=diagnosed)
    )
    return diagnosed


def _assistant_gateway_status_probe_enabled() -> bool:
    return os.getenv("SMAI_ASSISTANT_GATEWAY_STATUS_CHECK", "0") == "1"


def _start_copilot_llm_warmup(
    runtime_config: CopilotGatewayRuntimeConfig,
    *,
    settings: Settings | None = None,
) -> tuple[CopilotGatewayRuntimeConfig, AssistantWarmupStatus]:
    app_settings = settings or get_settings()
    warmup = app_settings.assistant.warmup
    manager = _warmup_manager_for_runtime(runtime_config)
    client = HttpAssistantGatewayClient(
        base_url=runtime_config.base_url,
        context_answer_path=runtime_config.context_answer_path,
        timeout_seconds=min(runtime_config.timeout_seconds, warmup.timeout_seconds),
        model=runtime_config.model,
        execution_mode=runtime_config.execution_mode,
        environment_profile=runtime_config.environment_profile,
        preferred_profile=runtime_config.profile,
    )
    manager.start(
        lambda: _probe_copilot_warmup(
            client=client,
            runtime_config=runtime_config,
            health_timeout_seconds=warmup.health_timeout_seconds,
            chat_enabled=warmup.chat_enabled,
            chat_timeout_seconds=warmup.timeout_seconds,
        ),
        enabled=bool(warmup.enabled and runtime_config.enabled),
        max_attempts=warmup.retry_count + 1,
        retry_backoff_seconds=warmup.retry_backoff_seconds,
    )
    status = manager.status()
    return _runtime_config_from_warmup_status(runtime_config, status), status


def _warmup_manager_for_runtime(
    runtime_config: CopilotGatewayRuntimeConfig,
) -> AssistantWarmupManager:
    key = "|".join(_gateway_diagnostic_cache_key(runtime_config))
    return get_assistant_warmup_manager(key)


def _runtime_config_from_warmup_status(
    runtime_config: CopilotGatewayRuntimeConfig,
    status: AssistantWarmupStatus,
) -> CopilotGatewayRuntimeConfig:
    if status.diagnostic is not None:
        diagnostic = status.diagnostic
        if diagnostic.model_details:
            st.session_state[COPILOT_LLM_MODEL_CATALOG_STATE_KEY] = parse_assistant_model_catalog(
                {
                    "provider": diagnostic.provider or "ollama",
                    "models": [
                        {"name": name, "modified_at": modified_at, "size": size}
                        for name, modified_at, size in diagnostic.model_details
                    ],
                }
            )
        runtime_config = replace(
            runtime_config,
            readiness_status=diagnostic.status,
            readiness_message=diagnostic.message,
            gateway_url=diagnostic.gateway_url,
            gateway_error_type=diagnostic.gateway_error_type or "",
            gateway_error_message=diagnostic.gateway_error_message or "",
            http_status=diagnostic.http_status,
            provider_error_type=diagnostic.provider_error_type or "",
            provider_error_message=diagnostic.provider_error_message or "",
            ollama_base_url=diagnostic.ollama_base_url or "",
            installed_models=diagnostic.installed_models,
            provider=diagnostic.provider or runtime_config.provider,
            model=diagnostic.model or runtime_config.model,
            profile=diagnostic.profile or runtime_config.profile,
        )
        _cache_gateway_runtime_config(runtime_config)
    elif status.state in {"warming", "retrying", "model_loading"}:
        runtime_config = replace(
            runtime_config,
            readiness_status="warming",
            readiness_message=status.message,
        )
    elif status.state == "timeout":
        runtime_config = replace(
            runtime_config,
            readiness_status="gateway_timeout",
            readiness_message=status.message,
        )
    elif status.state in {"failed", "fallback"}:
        runtime_config = replace(
            runtime_config,
            readiness_status="gateway_unavailable",
            readiness_message=status.message,
        )
    return runtime_config


def _apply_copilot_warmup_auto_transition(
    status: AssistantWarmupStatus,
    state: MutableMapping[str, object],
) -> bool:
    if status.state not in {"ready", "recovered", "degraded", "fallback", "failed", "timeout"}:
        return False
    marker = f"{status.attempt}:{status.state}"
    if str(state.get(COPILOT_WARMUP_AUTO_TRANSITION_STATE_KEY, "")) == marker:
        return False
    state[COPILOT_WARMUP_AUTO_TRANSITION_STATE_KEY] = marker
    if status.state in {"ready", "recovered"}:
        state[COPILOT_WARMUP_READY_NOTICE_STATE_KEY] = True
    return True


@st.fragment(run_every=COPILOT_WARMUP_POLL_SECONDS)
def _render_copilot_warmup_monitor(
    *,
    runtime_config: CopilotGatewayRuntimeConfig,
    settings: Settings,
    history: list[dict[str, str]],
    header_placeholder: Any,
) -> None:
    status = _warmup_manager_for_runtime(runtime_config).status()
    current_config = _runtime_config_from_warmup_status(runtime_config, status)
    _render_copilot_header(
        header_placeholder=header_placeholder,
        history=history,
        runtime_config=current_config,
    )
    _render_copilot_loading_panel(status, settings=settings)
    if _apply_copilot_warmup_auto_transition(status, st.session_state):
        st.rerun()


def _probe_copilot_warmup(
    *,
    client: HttpAssistantGatewayClient,
    runtime_config: CopilotGatewayRuntimeConfig,
    health_timeout_seconds: float,
    chat_enabled: bool,
    chat_timeout_seconds: float,
) -> AssistantGatewayDiagnostic:
    diagnostic = client.diagnose(timeout_seconds=health_timeout_seconds)
    if diagnostic.status != "ready" or not chat_enabled:
        return diagnostic
    try:
        response = httpx.post(
            f"{runtime_config.base_url.rstrip('/')}/api/v1/chat",
            json={
                "message": "SMAI warmup. Reply OK.",
                "system_prompt": "Reply only OK.",
                "profile": runtime_config.profile,
                "model": runtime_config.model,
            },
            timeout=chat_timeout_seconds,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise TimeoutError("assistant chat warmup timed out") from exc
    return diagnostic


def _gateway_diagnostic_cache_key(
    runtime_config: CopilotGatewayRuntimeConfig,
) -> tuple[str, str, str, str]:
    return (
        runtime_config.base_url,
        runtime_config.context_answer_path,
        runtime_config.model,
        runtime_config.profile,
    )


def _cache_gateway_runtime_config(
    runtime_config: CopilotGatewayRuntimeConfig,
    *,
    checked_at: float | None = None,
) -> None:
    st.session_state[COPILOT_GATEWAY_DIAGNOSTIC_STATE_KEY] = {
        "checked_at": time.time() if checked_at is None else checked_at,
        "cache_key": _gateway_diagnostic_cache_key(runtime_config),
        "runtime_config": _runtime_config_to_state(runtime_config),
    }


def _probe_copilot_gateway_runtime(
    runtime_config: CopilotGatewayRuntimeConfig,
    *,
    transport: httpx.BaseTransport | None = None,
) -> CopilotGatewayRuntimeConfig:
    if not runtime_config.enabled:
        return runtime_config
    client = HttpAssistantGatewayClient(
        base_url=runtime_config.base_url,
        context_answer_path=runtime_config.context_answer_path,
        timeout_seconds=runtime_config.timeout_seconds,
        model=runtime_config.model,
        execution_mode=runtime_config.execution_mode,
        environment_profile=runtime_config.environment_profile,
        preferred_profile=runtime_config.profile,
        transport=transport,
    )
    diagnostic = client.diagnose(timeout_seconds=min(2.0, max(0.5, runtime_config.timeout_seconds)))
    return replace(
        runtime_config,
        readiness_status=diagnostic.status,
        readiness_message=diagnostic.message,
        gateway_url=diagnostic.gateway_url,
        gateway_error_type=diagnostic.gateway_error_type or "",
        gateway_error_message=diagnostic.gateway_error_message or "",
        http_status=diagnostic.http_status,
        provider_error_type=diagnostic.provider_error_type or "",
        provider_error_message=diagnostic.provider_error_message or "",
        ollama_base_url=diagnostic.ollama_base_url or "",
        installed_models=diagnostic.installed_models,
        provider=diagnostic.provider or runtime_config.provider,
        model=diagnostic.model or runtime_config.model,
        profile=diagnostic.profile or runtime_config.profile,
    )


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


def _assistant_runtime_status_for_header(
    *,
    history: list[dict[str, str]],
    runtime_config: CopilotGatewayRuntimeConfig,
    has_pending: bool = False,
) -> AssistantRuntimeStatus:
    latest = history[-1] if history else {}
    latest_status = str(latest.get("status", "")).strip()
    if has_pending or latest_status == "pending":
        event_name = (
            "research_running"
            if str(latest.get("tool_plan_choice", "")).strip()
            else "request_started"
        )
        return derive_assistant_runtime_status(
            AssistantStatusEvent(name=event_name, runtime_config=runtime_config)
        )
    if latest_status == "tool_plan":
        return derive_assistant_runtime_status(
            AssistantStatusEvent(name="research_planned", runtime_config=runtime_config)
        )
    stored = _runtime_status_from_state(st.session_state.get(COPILOT_RUNTIME_STATUS_STATE_KEY))
    if stored is not None and _runtime_status_matches_runtime_config(stored, runtime_config):
        return stored
    return derive_assistant_runtime_status(
        AssistantStatusEvent(name="health_checked", runtime_config=runtime_config)
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


def copilot_history_messages(
    turns: list[dict[str, str]],
    *,
    max_turns: int = 4,
) -> list[AssistantMessage]:
    messages: list[AssistantMessage] = []
    for turn in turns[-max_turns:]:
        question = str(turn.get("question", "")).strip()
        answer = str(turn.get("answer", "")).strip()
        if question:
            messages.append(AssistantMessage(role="user", content=question))
        if answer:
            messages.append(AssistantMessage(role="assistant", content=answer))
    return messages


def copilot_answer_detail_html(turn: dict[str, str]) -> str:
    intent = _normalize_intent(turn.get("intent", ""))
    tool_plan_panel = _assistant_tool_plan_panel_html(turn)
    workflow_panel = _assistant_guided_workflow_panel_html(turn)
    action_results = _assistant_action_results_panel_html(turn)
    if _is_llm_micro_intent(intent):
        return (
            action_results + workflow_panel + tool_plan_panel + _assistant_action_links_html(turn)
        )
    if str(turn.get("hide_answer_grid", "")).lower() == "true":
        return (
            _execution_result_html(turn)
            + action_results
            + workflow_panel
            + tool_plan_panel
            + _response_meta_html(turn)
            + _assistant_action_links_html(turn)
        )
    titles = _section_titles_for_intent(intent)
    reasons = _list_html(_split_lines(turn.get("reasons", "")))
    cautions = _list_html(_split_lines(turn.get("cautions", "")))
    checkpoints = _list_html(_split_lines(turn.get("next_checkpoints", "")))
    if intent == "app_help":
        return (
            _inline_sections_html(
                (
                    (titles[0], reasons),
                    (titles[1], cautions),
                    (titles[2], checkpoints),
                )
            )
            + _execution_result_html(turn)
            + action_results
            + workflow_panel
            + tool_plan_panel
            + _response_meta_html(turn)
            + _assistant_action_links_html(turn)
        )
    grid_class = "smai-copilot-answer-grid"
    if len(titles) == 4:
        grid_class += " smai-copilot-answer-grid--four"
    return (
        f'<div class="{grid_class}">'
        f"{_block_html(titles[0], reasons)}"
        f"{_block_html(titles[1], cautions)}"
        f"{_block_html(titles[2], checkpoints)}"
        f"{_block_html(titles[3], _list_html(_split_lines(turn.get('memo_points', '')))) if len(titles) == 4 else ''}"
        "</div>"
        f"{_execution_result_html(turn)}"
        f"{action_results}"
        f"{workflow_panel}"
        f"{tool_plan_panel}"
        f"{_response_meta_html(turn)}"
        f"{_assistant_action_links_html(turn)}"
    )


def copilot_turn_html(turn: dict[str, str]) -> str:
    return f'<div class="smai-copilot-thread">{_copilot_turn_rows_html(turn)}</div>'


def _copilot_turn_rows_html(turn: dict[str, str]) -> str:
    context_label = str(turn.get("context_label", "")).strip()
    question = str(turn.get("question", "")).strip()
    answer = str(turn.get("answer", "")).strip()
    status = str(turn.get("status", "")).strip()
    is_pending = status == "pending"
    if status in {"tool_plan", "tool_plan_resolved"}:
        detail_html = _tool_plan_detail_html(turn)
    elif is_pending:
        detail_html = _pending_detail_html(turn)
    else:
        detail_html = copilot_answer_detail_html(turn)
    assistant_html = _assistant_bubble_html(
        answer=answer,
        detail_html=detail_html,
        is_pending=is_pending,
    )
    return _user_bubble_html(context_label=context_label, question=question) + assistant_html


def _copilot_thread_html(turns: list[dict[str, str]]) -> str:
    rows = "".join(_copilot_turn_rows_html(turn) for turn in turns)
    return f'<div class="smai-copilot-thread">{rows}<div id="smai-copilot-latest"></div></div>'


def should_auto_scroll_chat(previous_count: int, current_count: int) -> bool:
    return current_count > previous_count


def _auto_scroll_chat_if_needed(turns: list[dict[str, str]]) -> None:
    current = len(turns)
    previous = int(st.session_state.get(COPILOT_CHAT_LAST_SCROLL_COUNT_STATE_KEY, 0) or 0)
    st.session_state[COPILOT_CHAT_LAST_SCROLL_COUNT_STATE_KEY] = current
    if not should_auto_scroll_chat(previous, current):
        return
    components.html(
        """<script>
        const doc = window.parent.document;
        const target = doc.getElementById('smai-copilot-latest');
        if (target) target.scrollIntoView({behavior:'smooth', block:'end'});
        </script>""",
        height=0,
    )


def render_copilot_workspace_page() -> None:
    contexts = copilot_context_options()
    context_by_id = {context.context_id: context for context in contexts}
    history = _copilot_history()
    settings = get_settings()
    runtime_config = copilot_gateway_runtime_config(settings)
    runtime_config, warmup_status = _start_copilot_llm_warmup(
        runtime_config,
        settings=settings,
    )

    header_placeholder = st.empty()
    _render_copilot_header(
        header_placeholder=header_placeholder,
        history=history,
        runtime_config=runtime_config,
    )
    clear = _render_new_conversation_action()
    _render_material_status(_active_context_from_history(history, context_by_id))
    if warmup_status.state in {"not_started", "warming", "retrying", "model_loading"}:
        _render_copilot_warmup_monitor(
            runtime_config=runtime_config,
            settings=settings,
            history=history,
            header_placeholder=header_placeholder,
        )
    else:
        _render_copilot_loading_panel(warmup_status, settings=settings)
    if bool(st.session_state.pop(COPILOT_WARMUP_READY_NOTICE_STATE_KEY, False)):
        st.toast(
            "SMAIナビの準備ができました。銘柄・予測・ニュース・根拠資料を確認できます。",
            icon="✅",
        )

    if clear:
        st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = []
        st.session_state[COPILOT_CONVERSATION_ID_STATE_KEY] = _new_conversation_id()
        st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = "free_chat"
        st.session_state[COPILOT_PENDING_REQUEST_STATE_KEY] = None
        st.session_state[COPILOT_PENDING_STREAM_STATE_KEY] = ""
        st.session_state[COPILOT_SUPPRESS_SUBMIT_STATE_KEY] = False
        st.session_state.pop(COPILOT_RUNTIME_STATUS_STATE_KEY, None)
        st.session_state.pop(COPILOT_GATEWAY_DIAGNOSTIC_STATE_KEY, None)
        st.session_state.pop(COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY, None)
        st.session_state.pop(COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY, None)
        st.rerun()

    chat_placeholder = st.empty()
    _render_chat_thread(history, placeholder=chat_placeholder)
    if isinstance(st.session_state.get(COPILOT_PENDING_REQUEST_STATE_KEY), dict):
        _render_pending_step_progression(chat_placeholder=chat_placeholder)
    if _process_pending_copilot_request(
        context_by_id=context_by_id,
        fallback_context=contexts[0],
    ):
        _render_chat_thread(_copilot_history(), placeholder=chat_placeholder)
        history = _copilot_history()
        runtime_config = _refresh_copilot_header(
            header_placeholder=header_placeholder,
            history=history,
        )
    if _render_tool_plan_actions(
        _copilot_history(),
        context_by_id=context_by_id,
        fallback_context=contexts[0],
        runtime_config=runtime_config,
    ):
        st.rerun()
    if _render_confirmable_assistant_action(
        _copilot_history(),
        context_by_id=context_by_id,
        fallback_context=contexts[0],
    ):
        st.rerun()
    if _render_workflow_session_controls(_copilot_history()):
        st.rerun()
    if _render_decision_report_draft_action(_copilot_history()):
        st.rerun()
    _render_pending_decision_report_draft_preview()
    st.session_state.pop(COPILOT_SUPPRESS_SUBMIT_STATE_KEY, None)
    suggestions_placeholder = st.empty()
    with suggestions_placeholder.container():
        suggested = _render_suggestion_buttons(has_history=bool(history))

    if suggested is not None:
        context = context_by_id.get(suggested.context_id, contexts[0])
        _queue_copilot_submit(
            context,
            suggested.default_question,
            intent=suggested.intent,
            prompt_instruction=suggested.prompt_instruction,
            visible_question=suggested.label,
            runtime_config=runtime_config,
            pending_overrides={"conversation_mode": "normal_chat"},
            request_overrides={"conversation_mode": "normal_chat"},
        )
        suggestions_placeholder.empty()
        history = _copilot_history()
        _render_copilot_header(
            header_placeholder=header_placeholder,
            history=history,
            runtime_config=runtime_config,
        )
        _process_queued_copilot_request_inline(
            chat_placeholder=chat_placeholder,
            context_by_id=context_by_id,
            fallback_context=contexts[0],
        )
        history = _copilot_history()
        runtime_config = _refresh_copilot_header(
            header_placeholder=header_placeholder,
            history=history,
        )

    prompt, runtime_config = _render_chat_composer(runtime_config)

    if prompt:
        conversation_decision = route_assistant_conversation_mode(prompt)
        if conversation_decision.conversation_mode == "research_plan":
            research_plan = build_assistant_research_tool_plan(prompt, conversation_decision)
            if research_plan is not None:
                intent = _intent_for_research_plan(research_plan.intent)
                context = context_by_id.get(_context_id_for_intent(intent), contexts[0])
                _append_research_tool_plan_turn(
                    context=context,
                    visible_question=prompt,
                    research_plan=research_plan,
                    conversation_reason=conversation_decision.reason,
                )
                suggestions_placeholder.empty()
                st.rerun()
        intent = _intent_from_message(prompt, fallback=_active_intent())
        preset = _preset_for_intent(intent)
        context = context_by_id.get(preset.context_id, contexts[0])
        _queue_copilot_submit(
            context,
            prompt,
            intent=intent,
            prompt_instruction=preset.prompt_instruction,
            visible_question=prompt,
            runtime_config=runtime_config,
            pending_overrides={"conversation_mode": conversation_decision.conversation_mode},
            request_overrides={"conversation_mode": conversation_decision.conversation_mode},
        )
        suggestions_placeholder.empty()
        history = _copilot_history()
        _render_copilot_header(
            header_placeholder=header_placeholder,
            history=history,
            runtime_config=runtime_config,
        )
        _process_queued_copilot_request_inline(
            chat_placeholder=chat_placeholder,
            context_by_id=context_by_id,
            fallback_context=contexts[0],
        )
        history = _copilot_history()
        runtime_config = _refresh_copilot_header(
            header_placeholder=header_placeholder,
            history=history,
        )


def _render_copilot_header(
    *,
    header_placeholder: Any,
    history: list[dict[str, str]],
    runtime_config: CopilotGatewayRuntimeConfig,
) -> None:
    runtime_status = _assistant_runtime_status_for_header(
        history=history,
        runtime_config=runtime_config,
    )
    header_placeholder.markdown(
        _chat_header_html(
            history_count=len(history),
            runtime_config=runtime_config,
            runtime_status=runtime_status,
        ),
        unsafe_allow_html=True,
    )


def _refresh_copilot_header(
    *,
    header_placeholder: Any,
    history: list[dict[str, str]],
) -> CopilotGatewayRuntimeConfig:
    runtime_config = copilot_gateway_runtime_config()
    _render_copilot_header(
        header_placeholder=header_placeholder,
        history=history,
        runtime_config=runtime_config,
    )
    return runtime_config


def _has_pending_copilot_turn(history: list[dict[str, str]]) -> bool:
    return any(str(turn.get("status", "")).strip() == "pending" for turn in history)


def _render_copilot_loading_panel(
    status: AssistantWarmupStatus,
    *,
    settings: Settings,
) -> None:
    warmup = settings.assistant.warmup
    headlines = (
        load_assistant_loading_headlines(
            max_items=warmup.loading_headline_max_items,
            max_age_hours=warmup.loading_headline_cache_max_age_hours,
        )
        if warmup.loading_headlines_enabled
        else None
    )
    markup = copilot_loading_panel_html(
        status,
        headlines=headlines,
        radar_asset_uri=_investment_radar_loading_asset_uri(),
    )
    if markup:
        st.markdown(markup, unsafe_allow_html=True)


def _investment_radar_loading_asset_uri() -> str:
    try:
        return _asset_data_uri(MASCOT_TITLE_ASSETS["investment_radar"])
    except (OSError, ValueError):
        return ""


def investment_radar_loading_icon_html(radar_asset_uri: str = "") -> str:
    if radar_asset_uri:
        return (
            '<span class="smai-warmup-radar-icon" '
            'data-testid="assistant-loading-radar-icon">'
            f'<img src="{html.escape(radar_asset_uri)}" alt="投資レーダー" loading="eager" />'
            "</span>"
        )
    return (
        '<span class="smai-warmup-radar-icon smai-warmup-radar-icon--fallback" '
        'data-testid="assistant-loading-radar-icon" role="img" '
        'aria-label="投資レーダー"><i></i><b></b><em></em></span>'
    )


def assistant_loading_headline_category_tone(category: str) -> str:
    normalized = category.casefold()
    if any(keyword in normalized for keyword in ("地政学", "マクロ", "国内株")):
        return "cyan"
    if any(keyword in normalized for keyword in ("決算", "業績", "修正")):
        return "amber"
    if any(keyword in normalized for keyword in ("小売", "消費")):
        return "mint"
    if any(keyword in normalized for keyword in ("半導体", "ai", "テクノロジー")):
        return "violet"
    if any(keyword in normalized for keyword in ("金利", "為替", "米国株")):
        return "indigo"
    return "neutral"


def assistant_loading_headline_cards_html(
    headlines: AssistantLoadingHeadlines | None,
) -> str:
    if headlines is None or not headlines.items:
        return (
            '<div class="smai-warmup-headlines-empty" '
            'data-testid="assistant-loading-headlines-empty">'
            "<strong>市場ヘッドラインを準備中です。</strong>"
            "<span>ロード中は、前回取得した市場ヘッドラインがここに表示されます。</span>"
            "</div>"
        )
    acquisition_label = "前回取得" if headlines.source == "cache" else "取得済み"
    return (
        '<div class="smai-warmup-news-list">'
        + "".join(
            (
                '<article class="smai-warmup-news-card" '
                'data-testid="assistant-loading-news-card">'
                f'<span class="smai-warmup-news-badge smai-warmup-news-badge--{assistant_loading_headline_category_tone(item.category)}" data-testid="assistant-loading-news-category">'
                f"{html.escape(item.category)}</span>"
                f'<div class="smai-warmup-news-title" data-testid="assistant-loading-news-title" title="{html.escape(item.title)}">'
                f"{html.escape(item.title)}</div>"
                '<div class="smai-warmup-news-meta" data-testid="assistant-loading-news-meta">'
                f"<span>{html.escape(item.source)}</span><i>・</i><span>{acquisition_label}</span>"
                "</div></article>"
            )
            for item in headlines.items[:5]
        )
        + "</div>"
    )


def copilot_loading_panel_html(
    status: AssistantWarmupStatus,
    *,
    headlines: AssistantLoadingHeadlines | None,
    radar_asset_uri: str = "",
) -> str:
    if status.state in {"ready", "recovered", "disabled"}:
        return ""
    state_label = {
        "not_started": "LLM起動確認待ち",
        "warming": "LLM起動確認中",
        "model_loading": "モデルを読み込み中",
        "retrying": "LLM接続を再確認中",
        "gateway_unreachable": "LLM Gateway未接続",
        "provider_unavailable": "LLM provider未接続",
        "model_missing": "選択モデル未取得",
        "degraded": "通常回答で対応中",
        "fallback": "通常回答で対応中",
        "failed": "LLM Gateway未接続",
        "timeout": "LLM応答待ちが時間切れ",
    }.get(status.state, "LLM起動確認中")
    steps = [
        "✓ SMAI本体を起動",
        "✓ ニュースキャッシュを確認",
        f"{'・' if status.state in {'warming', 'retrying', 'model_loading'} else '✓'} {html.escape(status.step)}",
    ]
    headline_html = ""
    if headlines is not None:
        freshness = "前回取得"
        updated = headlines.updated_at.astimezone().strftime("%Y-%m-%d %H:%M")
        stale_note = (
            "<small>※前回取得したヘッドラインを表示しています</small>" if headlines.stale else ""
        )
        headline_html = (
            '<div class="smai-warmup-headlines"><div class="smai-warmup-headlines-header">'
            + investment_radar_loading_icon_html(radar_asset_uri)
            + "<div><strong>市場ヘッドライン</strong>"
            + (
                f"<small>{freshness}: {html.escape(updated)}</small>{stale_note}"
                if headlines.items
                else "<small>キャッシュを待たずにSMAIナビを準備しています</small>"
            )
            + "</div></div>"
            + assistant_loading_headline_cards_html(headlines)
            + "</div>"
        )
    fallback_copy = (
        "LLMの応答準備に時間がかかっています。いったんSMAI標準ナビで回答します。"
        if status.state
        in {
            "degraded",
            "fallback",
            "failed",
            "timeout",
            "gateway_unreachable",
            "provider_unavailable",
            "model_missing",
        }
        else "市場データとAIの準備を進めています。準備中もSMAI標準ナビを利用できます。"
    )
    modal = status.state in {"not_started", "warming", "retrying", "model_loading"}
    wrapper_open = (
        '<div class="smai-warmup-overlay" data-testid="assistant-loading-modal" role="dialog" aria-modal="true">'
        if modal
        else '<div class="smai-warmup-inline" data-testid="assistant-fallback-panel">'
    )
    return (
        """
        <style>
        .smai-warmup-overlay{position:fixed;z-index:999;inset:3.75rem 0 0 21rem;display:grid;place-items:center;
          padding:24px;background:rgba(2,8,23,.72);backdrop-filter:blur(4px);pointer-events:auto}
        section[data-testid="stSidebar"]{z-index:1002!important}
        .smai-warmup-inline{position:relative;margin:10px 0 18px}
        .smai-warmup-panel{position:relative;overflow:hidden;width:min(760px,calc(100vw - 48px));max-height:calc(100vh - 100px);overflow-y:auto;margin:10px 0 18px;padding:18px;
          border:1px solid rgba(56,189,248,.34);border-radius:16px;
          background:linear-gradient(135deg,rgba(7,17,31,.97),rgba(13,42,57,.92));color:#e5edf7}
        .smai-warmup-panel:after{content:"";position:absolute;inset:-70% 35%;border:1px solid rgba(34,211,238,.18);
          border-radius:50%;animation:smaiRadar 5s linear infinite;pointer-events:none}
        .smai-warmup-core{display:inline-flex;width:28px;height:28px;margin-right:10px;border-radius:50%;
          border:2px solid #22d3ee;box-shadow:0 0 18px rgba(34,211,238,.55);animation:smaiPulse 1.8s ease-in-out infinite}
        .smai-warmup-core:after{content:"•••";position:absolute;margin:28px 0 0 2px;color:#67e8f9;letter-spacing:3px;animation:smaiDots 1.4s steps(3,end) infinite;overflow:hidden;width:24px}
        .smai-warmup-title{display:flex;align-items:center;font-weight:750;font-size:1.05rem}.smai-warmup-state{color:#67e8f9}
        .smai-warmup-panel p{margin:8px 0;color:#cbd5e1}.smai-warmup-steps{display:grid;gap:4px;font-size:.9rem;color:#a5f3fc}
        .smai-warmup-headlines{margin-top:14px;padding:14px 15px;border:1px solid rgba(103,232,249,.16);border-radius:13px;background:rgba(5,20,36,.42)}
        .smai-warmup-headlines-header{display:flex;align-items:center;gap:11px}.smai-warmup-headlines-header>div{display:grid;gap:2px}
        .smai-warmup-headlines small{color:#94a3b8;font-size:.72rem;line-height:1.45}.smai-warmup-news-list{display:grid;gap:8px;margin-top:12px}
        .smai-warmup-news-card{display:grid;grid-template-columns:auto minmax(0,1fr);gap:5px 10px;padding:10px 12px;border:1px solid rgba(96,165,250,.15);border-radius:10px;background:linear-gradient(135deg,rgba(15,34,55,.72),rgba(8,29,45,.6));transition:background-color .16s ease,border-color .16s ease}
        .smai-warmup-news-card:hover{border-color:rgba(103,232,249,.28);background:linear-gradient(135deg,rgba(17,43,66,.8),rgba(8,37,52,.7))}
        .smai-warmup-news-badge{align-self:start;padding:2px 7px;border:1px solid rgba(148,163,184,.24);border-radius:999px;color:#cbd5e1;background:rgba(100,116,139,.13);font-size:.69rem;font-weight:760;line-height:1.45;white-space:nowrap}
        .smai-warmup-news-badge--cyan{color:#a5f3fc;border-color:rgba(34,211,238,.28);background:rgba(8,145,178,.13)}
        .smai-warmup-news-badge--amber{color:#fde68a;border-color:rgba(251,191,36,.28);background:rgba(217,119,6,.12)}
        .smai-warmup-news-badge--mint{color:#a7f3d0;border-color:rgba(52,211,153,.26);background:rgba(5,150,105,.12)}
        .smai-warmup-news-badge--violet{color:#ddd6fe;border-color:rgba(167,139,250,.28);background:rgba(124,58,237,.12)}
        .smai-warmup-news-badge--indigo{color:#c7d2fe;border-color:rgba(129,140,248,.28);background:rgba(79,70,229,.12)}
        .smai-warmup-news-title{min-width:0;color:#e6f2ff;font-size:.86rem;font-weight:680;line-height:1.55;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
        .smai-warmup-news-meta{grid-column:2;display:flex;align-items:center;gap:5px;color:#8fa8bf;font-size:.7rem;line-height:1.45}.smai-warmup-news-meta i{font-style:normal;color:#526b82}
        .smai-warmup-headlines-empty{display:grid;gap:4px;margin-top:12px;padding:13px;border:1px dashed rgba(103,232,249,.2);border-radius:10px;background:rgba(8,28,45,.48)}
        .smai-warmup-headlines-empty strong{color:#dbeafe;font-size:.84rem}.smai-warmup-headlines-empty span{color:#8fa8bf;font-size:.75rem;line-height:1.55}
        .smai-warmup-radar-icon{position:relative;display:inline-grid;place-items:center;width:56px;height:56px;flex:0 0 56px;border-radius:50%;background:radial-gradient(circle,rgba(34,211,238,.16),rgba(8,47,73,.06));box-shadow:0 0 17px rgba(34,211,238,.2)}
        .smai-warmup-radar-icon img{width:56px;height:56px;object-fit:contain;filter:drop-shadow(0 0 5px rgba(34,211,238,.32))}
        .smai-warmup-radar-icon--fallback{overflow:hidden;border:1px solid rgba(103,232,249,.45);background:repeating-radial-gradient(circle,transparent 0 8px,rgba(34,211,238,.2) 9px 10px)}
        .smai-warmup-radar-icon--fallback:after{content:"";position:absolute;width:50%;height:1px;left:50%;top:50%;transform-origin:left;transform:rotate(-32deg);background:#67e8f9;box-shadow:0 0 7px #22d3ee}
        .smai-warmup-radar-icon--fallback i,.smai-warmup-radar-icon--fallback b,.smai-warmup-radar-icon--fallback em{position:absolute;width:5px;height:5px;border-radius:50%;background:#67e8f9;box-shadow:0 0 7px #22d3ee}.smai-warmup-radar-icon--fallback i{left:13px;top:18px}.smai-warmup-radar-icon--fallback b{right:11px;top:27px}.smai-warmup-radar-icon--fallback em{left:29px;bottom:10px}
        @keyframes smaiPulse{0%,100%{opacity:.58;transform:scale(.9)}50%{opacity:1;transform:scale(1.06)}}
        @keyframes smaiRadar{to{transform:rotate(360deg)}}
        @keyframes smaiDots{0%{width:0}100%{width:24px}}
        @media(max-width:768px){.smai-warmup-overlay{inset:3.75rem 0 0 0;padding:12px}.smai-warmup-panel{width:calc(100vw - 24px)}.smai-warmup-news-card{grid-template-columns:1fr}.smai-warmup-news-meta{grid-column:1}}
        @media (prefers-reduced-motion:reduce){.smai-warmup-core,.smai-warmup-panel:after{animation:none}}
        </style>
        """
        + wrapper_open
        + '<section class="smai-warmup-panel" aria-label="SMAIナビ準備状況">'
        + '<div class="smai-warmup-title"><span class="smai-warmup-core" data-testid="assistant-loading-animation"></span>'
        + f'SMAIナビが市場の気配を確認中です… <span class="smai-warmup-state">{html.escape(state_label)}</span></div>'
        + f"<p>{html.escape(fallback_copy)}（fallbackあり）</p>"
        + '<div class="smai-warmup-steps">'
        + "".join(f"<span>{step}</span>" for step in steps)
        + "</div>"
        + headline_html
        + "</section></div>"
    )


def _render_new_conversation_action() -> bool:
    st.markdown(
        '<div class="smai-copilot-chat-actions-anchor" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    _, clear_col = st.columns([0.78, 0.22], gap="small", vertical_alignment="center")
    with clear_col:
        return st.button(
            "新しい会話",
            key="smai_copilot_new_conversation",
            use_container_width=True,
        )


def _render_chat_thread(turns: list[dict[str, str]], *, placeholder: Any | None = None) -> None:
    if not turns:
        return

    pending_turn_id = str(st.session_state.get(COPILOT_PENDING_STREAM_STATE_KEY, "") or "")
    pending_index = next(
        (
            index
            for index, turn in enumerate(turns)
            if pending_turn_id and str(turn.get("turn_id", "")) == pending_turn_id
        ),
        None,
    )
    if pending_index is None:
        _render_chat_markup(_copilot_thread_html(turns), placeholder=placeholder)
        _auto_scroll_chat_if_needed(turns)
        return

    _render_streaming_turn(turns[:pending_index], turns[pending_index], placeholder=placeholder)
    st.session_state[COPILOT_PENDING_STREAM_STATE_KEY] = ""
    _auto_scroll_chat_if_needed(turns)


def _render_chat_markup(markup: str, *, placeholder: Any | None = None) -> None:
    if placeholder is None:
        st.markdown(markup, unsafe_allow_html=True)
        return
    placeholder.markdown(markup, unsafe_allow_html=True)


def _process_queued_copilot_request_inline(
    *,
    chat_placeholder: Any,
    context_by_id: dict[str, SmaiAssistantContext],
    fallback_context: SmaiAssistantContext,
) -> None:
    _render_pending_step_progression(chat_placeholder=chat_placeholder)
    if _process_pending_copilot_request(
        context_by_id=context_by_id,
        fallback_context=fallback_context,
    ):
        _render_chat_thread(_copilot_history(), placeholder=chat_placeholder)


def _render_pending_step_progression(*, chat_placeholder: Any) -> None:
    request = st.session_state.get(COPILOT_PENDING_REQUEST_STATE_KEY)
    if not isinstance(request, dict):
        _render_chat_thread(_copilot_history(), placeholder=chat_placeholder)
        return
    pending_turn_id = str(request.get("turn_id", ""))
    steps = _pending_steps_for_turn_id(pending_turn_id)
    if not pending_turn_id or not steps:
        _render_chat_thread(_copilot_history(), placeholder=chat_placeholder)
        return
    for index in range(len(steps)):
        _set_pending_step_index(pending_turn_id, index)
        _render_chat_thread(_copilot_history(), placeholder=chat_placeholder)
        if index < len(steps) - 1:
            time.sleep(COPILOT_PENDING_STEP_DELAY_SECONDS)


def _pending_steps_for_turn_id(turn_id: str) -> list[str]:
    if not turn_id:
        return []
    for turn in _copilot_history():
        if str(turn.get("turn_id", "")) == turn_id and str(turn.get("status", "")) == "pending":
            return _split_lines(turn.get("pending_steps", ""))
    return []


def _set_pending_step_index(turn_id: str, step_index: int) -> None:
    history = _copilot_history()
    next_history: list[dict[str, str]] = []
    for turn in history:
        if str(turn.get("turn_id", "")) == turn_id and str(turn.get("status", "")) == "pending":
            updated = dict(turn)
            updated["pending_step_index"] = str(max(0, step_index))
            next_history.append(updated)
        else:
            next_history.append(turn)
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = next_history


def _render_suggestion_buttons(
    *,
    has_history: bool,
) -> CopilotConversationPreset | None:
    if has_history:
        return None
    heading = "今日は何を相談しますか？"
    st.markdown(
        f'<div class="smai-copilot-suggestions-title">{html.escape(heading)}</div>',
        unsafe_allow_html=True,
    )
    _, suggestions_col, _ = st.columns([0.04, 0.92, 0.04])
    with suggestions_col:
        presets = copilot_conversation_presets()
        for row_start in range(0, len(presets), 3):
            columns = st.columns(3)
            for offset, preset in enumerate(presets[row_start : row_start + 3]):
                with columns[offset]:
                    st.markdown(
                        _action_card_intro_html(preset=preset),
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        preset.label,
                        key=f"smai_copilot_suggestion_{preset.intent}",
                        use_container_width=True,
                        help=preset.description,
                    ):
                        st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = preset.intent
                        return preset
    return None


def _queue_copilot_submit(
    context: SmaiAssistantContext,
    question: str,
    *,
    intent: CopilotIntent,
    prompt_instruction: str,
    visible_question: str,
    runtime_config: CopilotGatewayRuntimeConfig,
    pending_overrides: Mapping[str, str] | None = None,
    request_overrides: Mapping[str, str] | None = None,
) -> None:
    normalized_question = question.strip()
    if not normalized_question:
        st.warning("質問を入力してください。")
        return
    turn_id = uuid4().hex
    history = _copilot_history()
    pending_state = dict(pending_overrides or {})
    request_state = dict(request_overrides or {})
    pending_turn = _pending_turn(
        turn_id=turn_id,
        context=context,
        visible_question=visible_question,
        intent=intent,
        runtime_config=runtime_config,
    )
    pending_turn.update(pending_state)
    history.append(pending_turn)
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = history
    st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = intent
    update_assistant_runtime_status(
        AssistantStatusEvent(
            name=(
                "research_running" if pending_state.get("tool_plan_choice") else "request_started"
            ),
            runtime_config=runtime_config,
        )
    )
    pending_request = {
        "turn_id": turn_id,
        "context_id": context.context_id,
        "question": normalized_question,
        "intent": intent,
        "prompt_instruction": prompt_instruction,
        "visible_question": visible_question,
        "runtime_config": _runtime_config_to_state(runtime_config),
    }
    pending_request.update(request_state)
    st.session_state[COPILOT_PENDING_REQUEST_STATE_KEY] = pending_request


def _process_pending_copilot_request(
    *,
    context_by_id: dict[str, SmaiAssistantContext],
    fallback_context: SmaiAssistantContext,
) -> bool:
    request = st.session_state.get(COPILOT_PENDING_REQUEST_STATE_KEY)
    if not isinstance(request, dict):
        return False
    pending_turn_id = str(request.get("turn_id", ""))
    history = _copilot_history()
    has_pending_turn = any(
        str(turn.get("turn_id", "")) == pending_turn_id and str(turn.get("status", "")) == "pending"
        for turn in history
    )
    if not pending_turn_id or not has_pending_turn:
        st.session_state[COPILOT_PENDING_REQUEST_STATE_KEY] = None
        return False
    st.session_state[COPILOT_PENDING_REQUEST_STATE_KEY] = None
    intent = _normalize_intent(str(request.get("intent", "free_chat")))
    context = context_by_id.get(str(request.get("context_id", "")), fallback_context)
    runtime_config = _runtime_config_from_state(request.get("runtime_config"))
    _handle_copilot_submit(
        context,
        str(request.get("question", "")),
        intent=intent,
        prompt_instruction=str(request.get("prompt_instruction", "")),
        visible_question=str(request.get("visible_question", "")),
        runtime_config=runtime_config,
        pending_turn_id=pending_turn_id,
        tool_plan_choice=str(request.get("tool_plan_choice", "")),
        tool_plan_subject=str(request.get("tool_plan_subject", "")),
        tool_plan_missing_materials=_split_lines(
            str(request.get("tool_plan_missing_materials", ""))
        ),
        tool_plan_tools=str(request.get("tool_plan_tools", "")),
        conversation_mode=str(request.get("conversation_mode", "normal_chat")),
    )
    return True


def _pending_turn(
    *,
    turn_id: str,
    context: SmaiAssistantContext,
    visible_question: str,
    intent: CopilotIntent,
    runtime_config: CopilotGatewayRuntimeConfig | None = None,
) -> dict[str, str]:
    uses_llm = runtime_config.enabled if runtime_config is not None else True
    return {
        "turn_id": turn_id,
        "status": "pending",
        "context_id": context.context_id,
        "context_label": copilot_context_label(context),
        "intent": intent,
        "intent_label": _preset_for_intent(intent).label,
        "question": visible_question,
        "answer": _pending_message_for_intent(intent),
        "pending_steps": "\n".join(_pending_steps_for_intent(intent, uses_llm=uses_llm)),
        "pending_step_index": "0",
        "reasons": "",
        "cautions": "",
        "next_checkpoints": "",
        "memo_points": "",
        "executed_checks": "",
        "tool_statuses": "",
        "conversation_mode": "normal_chat",
        "response_source": "",
        "model": "",
        "provider": "",
        "profile": "",
        "latency_ms": "",
        "gateway_status": "",
        "fallback_reason": "",
        "gateway_error_type": "",
        "gateway_error_message": "",
        "gateway_url": "",
        "http_status": "",
        "provider_error_type": "",
        "provider_error_message": "",
        "request_id": "",
        "timeout_sec": "",
        "context_tokens_estimate": "",
        "prompt_chars": "",
        "response_chars": "",
        "tool_execution_ms": "",
        "llm_generation_ms": "",
        "total_elapsed_ms": "",
        "response_meta": "",
        "research_bundle": "",
        "decision_report_context": "",
        "decision_report_markdown": "",
        "can_add_to_decision_report": "",
        "report_draft_status": "",
        "decision_report_source": "",
        "decision_report_symbol": "",
        "decision_report_company_name": "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _append_research_tool_plan_turn(
    *,
    context: SmaiAssistantContext,
    visible_question: str,
    research_plan: AssistantResearchToolPlan,
    conversation_reason: str,
) -> None:
    history = _copilot_history()
    intent = _intent_for_research_plan(research_plan.intent)
    history.append(
        {
            "turn_id": uuid4().hex,
            "status": "tool_plan",
            "context_id": context.context_id,
            "context_label": copilot_context_label(context),
            "intent": intent,
            "intent_label": "調査計画",
            "question": visible_question,
            "answer": _tool_plan_answer(research_plan),
            "reasons": "",
            "cautions": "",
            "next_checkpoints": "",
            "memo_points": "",
            "executed_checks": "",
            "tool_statuses": "",
            "conversation_mode": "research_plan",
            "conversation_reason": conversation_reason,
            "research_intent": research_plan.intent,
            "symbol_query": research_plan.symbol_query or "",
            "symbol": research_plan.symbol or "",
            "company_name": _research_plan_company_name(research_plan) or "",
            "approval_reason": research_plan.approval_reason,
            "tool_plan_tools": _tool_plan_tools_state(research_plan),
            "approval_choice": "",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = history
    st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = intent
    update_assistant_runtime_status(
        AssistantStatusEvent(
            name="research_planned",
            runtime_config=copilot_gateway_runtime_config(),
        )
    )


def _render_tool_plan_actions(
    history: list[dict[str, str]],
    *,
    context_by_id: dict[str, SmaiAssistantContext],
    fallback_context: SmaiAssistantContext,
    runtime_config: CopilotGatewayRuntimeConfig,
) -> bool:
    if not history or str(history[-1].get("status", "")) != "tool_plan":
        return False
    turn = history[-1]
    st.markdown(
        '<div class="smai-copilot-chat-actions-anchor" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    columns = st.columns(3, gap="small")
    actions = (
        ("approve", "取得して分析する"),
        ("cached_only", "取得済み情報だけで回答"),
        ("cancel", "キャンセル"),
    )
    for column, (choice, label) in zip(columns, actions):
        with column:
            if st.button(
                label,
                key=f"smai_copilot_tool_plan_{choice}_{turn.get('turn_id', '')}",
                use_container_width=True,
            ):
                _handle_tool_plan_choice(
                    turn,
                    choice=choice,
                    label=label,
                    context_by_id=context_by_id,
                    fallback_context=fallback_context,
                    runtime_config=runtime_config,
                )
                return True
    return False


def _render_confirmable_assistant_action(
    history: list[dict[str, str]],
    *,
    context_by_id: dict[str, SmaiAssistantContext],
    fallback_context: SmaiAssistantContext,
) -> bool:
    pending = st.session_state.get(COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY)
    if isinstance(pending, dict):
        turn = _turn_by_id(history, str(pending.get("turn_id", "")))
        action_id = str(pending.get("action_id", "")).strip()
        if turn is None or not action_id:
            st.session_state.pop(COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY, None)
            return True
        return _render_assistant_action_confirmation(
            turn,
            action_id=action_id,
            context_by_id=context_by_id,
            fallback_context=fallback_context,
        )

    candidate = _latest_confirmable_assistant_action_turn(history)
    if candidate is None:
        return False
    turn, action_id = candidate
    action = get_assistant_action(action_id)
    if action is None:
        return False
    st.markdown(
        '<div class="smai-copilot-chat-actions-anchor" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    _, action_col = st.columns([0.62, 0.38], gap="small")
    with action_col:
        if st.button(
            _assistant_action_confirm_label(action_id),
            key=f"smai_copilot_confirm_action_{action_id}_{turn.get('turn_id', '')}",
            use_container_width=True,
            help="実行前に対象、使用材料、変更しないものを確認します。",
        ):
            st.session_state[COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY] = {
                "turn_id": str(turn.get("turn_id", "")),
                "action_id": action_id,
            }
            return True
    return False


def _render_workflow_session_controls(history: list[dict[str, str]]) -> bool:
    if isinstance(st.session_state.get(COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY), dict):
        return False
    candidate = _latest_workflow_session_turn(history)
    if candidate is None:
        return False
    turn, session = candidate
    options = _workflow_session_control_options(session)
    if not options:
        return False
    st.markdown(
        '<div class="smai-copilot-chat-actions-anchor" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.caption("確認フローの操作")
    columns = st.columns(len(options), gap="small")
    for column, option in zip(columns, options):
        control = option["control"]
        label = option["label"]
        step_id = option["step_id"]
        with column:
            if st.button(
                label,
                key=f"smai_copilot_workflow_{control}_{step_id}_{turn.get('turn_id', '')}",
                use_container_width=True,
                help=option["help"],
            ):
                updated = _apply_workflow_session_control(session, control, step_id)
                _record_workflow_session_state(
                    turn_id=str(turn.get("turn_id", "")),
                    session=updated,
                )
                st.session_state.pop(COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY, None)
                if control == "cancel_session":
                    update_assistant_runtime_status(
                        AssistantStatusEvent(
                            name="cancelled",
                            runtime_config=copilot_gateway_runtime_config(),
                        )
                    )
                return True
    return False


def _workflow_session_control_options(
    session: AssistantWorkflowSession,
) -> list[dict[str, str]]:
    if session.status == "active":
        active_step = _workflow_session_active_step(session)
        if active_step is None:
            return [
                _workflow_control_option(
                    "cancel_session",
                    "フローを中止",
                    "",
                    "この確認フローをここで止めます。データ取得やレポート作成は行いません。",
                )
            ]
        options: list[dict[str, str]] = []
        if active_step.status in {"planned", "waiting_confirmation"}:
            options.append(
                _workflow_control_option(
                    "skip_step",
                    _workflow_skip_button_label(active_step.action_id),
                    active_step.step_id,
                    "現在の手順だけをスキップします。次の手順も自動実行はしません。",
                )
            )
        options.append(
            _workflow_control_option(
                "cancel_session",
                "フローを中止",
                active_step.step_id,
                "この確認フローをここで止めます。データ取得やレポート作成は行いません。",
            )
        )
        return options
    if session.status != "failed":
        return []
    failed_step = _workflow_session_failed_step(session)
    if failed_step is None:
        return [
            _workflow_control_option(
                "cancel_session",
                "フローを中止",
                "",
                "この確認フローをここで止めます。",
            )
        ]
    options = [
        _workflow_control_option(
            "retry_step",
            _workflow_retry_button_label(failed_step.action_id),
            failed_step.step_id,
            "失敗した手順をもう一度、実行前確認に戻します。",
        )
    ]
    if failed_step.action_id == "update_research":
        options.append(
            _workflow_control_option(
                "continue_with_existing_materials",
                "今ある材料で確認",
                failed_step.step_id,
                "AI調査更新をスキップし、取得済み材料で次の確認へ進みます。",
            )
        )
    options.append(
        _workflow_control_option(
            "cancel_session",
            "フローを中止",
            failed_step.step_id,
            "この確認フローをここで止めます。データ取得やレポート作成は行いません。",
        )
    )
    return options


def _workflow_control_option(
    control: str,
    label: str,
    step_id: str,
    help_text: str,
) -> dict[str, str]:
    return {"control": control, "label": label, "step_id": step_id, "help": help_text}


def _apply_workflow_session_control(
    session: AssistantWorkflowSession,
    control: str,
    step_id: str,
) -> AssistantWorkflowSession:
    if control == "cancel_session":
        return cancel_assistant_workflow_session(
            session,
            "ユーザー操作により確認フローを中止しました。",
        )
    if control == "retry_step":
        return retry_assistant_workflow_step(
            session,
            step_id,
            "前回の結果を確認し、もう一度実行前確認に戻しました。",
        )
    if control == "continue_with_existing_materials":
        return skip_assistant_workflow_step(
            session,
            step_id,
            "今ある材料で確認するため、失敗したAI調査更新をスキップしました。",
        )
    if control == "skip_step":
        return skip_assistant_workflow_step(
            session,
            step_id,
            "ユーザー操作により、この手順をスキップしました。",
        )
    return session


def _workflow_skip_button_label(action_id: str | None) -> str:
    return {
        "update_research": "AI調査をスキップ",
        "create_decision_report": "レポート作成をスキップ",
    }.get(str(action_id or ""), "この手順をスキップ")


def _workflow_retry_button_label(action_id: str | None) -> str:
    return {
        "update_research": "AI調査をもう一度更新",
        "create_decision_report": "レポート作成をもう一度試す",
    }.get(str(action_id or ""), "もう一度試す")


def _latest_workflow_session_turn(
    history: list[dict[str, str]],
) -> tuple[dict[str, str], AssistantWorkflowSession] | None:
    for turn in reversed(history):
        if str(turn.get("status", "")) != "complete":
            continue
        session = _workflow_session_from_turn(turn)
        if session is None:
            continue
        if session.status in {"active", "failed"}:
            return turn, session
    return None


def _workflow_session_from_turn(
    turn: dict[str, str],
) -> AssistantWorkflowSession | None:
    value = str(turn.get("assistant_workflow_session", "")).strip()
    if not value:
        return None
    try:
        return AssistantWorkflowSession.model_validate_json(value)
    except ValueError:
        return None


def _workflow_session_active_step(session: AssistantWorkflowSession):
    active_step_id = str(session.active_step_id or "").strip()
    if not active_step_id:
        return None
    return next((step for step in session.steps if step.step_id == active_step_id), None)


def _workflow_session_failed_step(session: AssistantWorkflowSession):
    return next((step for step in session.steps if step.status == "failed"), None)


def _record_workflow_session_state(
    *,
    turn_id: str,
    session: AssistantWorkflowSession,
) -> None:
    history = _copilot_history()
    next_history: list[dict[str, str]] = []
    for item in history:
        if str(item.get("turn_id", "")) != turn_id:
            next_history.append(item)
            continue
        updated = dict(item)
        updated["assistant_workflow_session"] = session.model_dump_json()
        next_history.append(updated)
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = next_history


def _render_assistant_action_confirmation(
    turn: dict[str, str],
    *,
    action_id: str,
    context_by_id: dict[str, SmaiAssistantContext],
    fallback_context: SmaiAssistantContext,
) -> bool:
    action = get_assistant_action(action_id)
    if action is None:
        st.session_state.pop(COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY, None)
        return True
    context = context_by_id.get(str(turn.get("context_id", "")), fallback_context)
    st.markdown(
        assistant_action_confirmation_html(
            action=action,
            target_label=_assistant_action_target_label(turn, context),
            materials=_assistant_action_materials(context),
        ),
        unsafe_allow_html=True,
    )
    execute_col, cancel_col = st.columns(2, gap="small")
    with execute_col:
        if st.button(
            _assistant_action_execute_label(action_id),
            key=f"smai_copilot_execute_action_{action_id}_{turn.get('turn_id', '')}",
            use_container_width=True,
        ):
            result = _execute_confirmed_assistant_action(
                turn,
                action_id=action_id,
                context=context,
            )
            _record_assistant_action_result(
                turn_id=str(turn.get("turn_id", "")),
                result=result,
                context=context,
                confirmed=True,
            )
            st.session_state.pop(COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY, None)
            return True
    with cancel_col:
        if st.button(
            "キャンセル",
            key=f"smai_copilot_cancel_action_{action_id}_{turn.get('turn_id', '')}",
            use_container_width=True,
        ):
            result = _cancelled_assistant_action_result(action_id)
            _record_assistant_action_result(
                turn_id=str(turn.get("turn_id", "")),
                result=result,
                context=context,
                confirmed=False,
            )
            st.session_state.pop(COPILOT_PENDING_ACTION_CONFIRM_STATE_KEY, None)
            return True
    return False


def _execute_confirmed_assistant_action(
    turn: dict[str, str],
    *,
    action_id: str,
    context: SmaiAssistantContext,
) -> AssistantActionResult:
    backend_context = _assistant_backend_context_for_ui_context(
        context=context,
        question=str(turn.get("question", "")),
    )
    return AssistantActionExecutor(research_fetcher=_fetch_research_for_assistant_action).execute(
        action_id,
        backend_context,
        payload={
            "report_context": assistant_context_to_report_context(context),
            "user_question": str(turn.get("question", "")),
            "assistant_answer": str(turn.get("answer", "")),
            "symbol": _assistant_action_symbol(turn, context),
            "company_name": _assistant_action_company_name(turn, context),
        },
        confirmed=True,
    )


def _fetch_research_for_assistant_action(
    *,
    symbol: str,
    company_name: str | None = None,
    related_keywords: list[str] | None = None,
    allow_network: bool = True,
    context: Mapping[str, object] | None = None,
):
    _ = context
    return fetch_external_research_for_symbol(
        symbol,
        company_name=company_name,
        related_keywords=related_keywords or [],
        allow_network=allow_network,
    )


def _cancelled_assistant_action_result(action_id: str) -> AssistantActionResult:
    now = datetime.now(UTC)
    action = get_assistant_action(action_id)
    label = action.label if action is not None else "操作"
    return AssistantActionResult(
        action_id=action_id,
        status="cancelled",
        title=f"{label}をキャンセルしました",
        summary="ユーザー操作により、実行前にキャンセルしました。",
        user_message="この操作ではデータ取得、レポート作成、スコア変更は行っていません。",
        started_at=now,
        completed_at=now,
        followup_actions=["summarize_next_checks"],
    )


def _record_assistant_action_result(
    *,
    turn_id: str,
    result: AssistantActionResult,
    context: SmaiAssistantContext,
    confirmed: bool,
) -> None:
    action = get_assistant_action(result.action_id)
    backend_context = _assistant_backend_context_for_ui_context(
        context=context,
        question="",
    )
    audit = build_assistant_action_audit_entry(
        result=result,
        action=action,
        context=backend_context,
        confirmed=confirmed,
    )
    audit_log = st.session_state.get(COPILOT_ACTION_AUDIT_STATE_KEY)
    if not isinstance(audit_log, list):
        audit_log = []
    audit_log.append(audit.model_dump(mode="json"))
    st.session_state[COPILOT_ACTION_AUDIT_STATE_KEY] = audit_log[-50:]

    history = _copilot_history()
    next_history: list[dict[str, str]] = []
    for item in history:
        if str(item.get("turn_id", "")) != turn_id:
            next_history.append(item)
            continue
        updated = dict(item)
        updated["assistant_action_results"] = _append_action_result_state(
            str(updated.get("assistant_action_results", "")),
            result,
        )
        updated["assistant_workflow_session"] = _apply_action_result_to_workflow_session_state(
            str(updated.get("assistant_workflow_session", "")),
            result,
        )
        if result.status == "success" and result.action_id == "create_decision_report":
            _attach_action_decision_report_draft(updated, result)
        next_history.append(updated)
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = next_history
    if result.status == "success" and result.action_id == "create_decision_report":
        updated_turn = _turn_by_id(_copilot_history(), turn_id)
        if updated_turn is not None:
            _store_pending_decision_report_draft(
                updated_turn,
                action_label="確認レポートを作る",
            )


def _attach_action_decision_report_draft(
    turn: dict[str, str],
    result: AssistantActionResult,
) -> None:
    raw_context = str(result.details.get("report_context_json", "") or "").strip()
    markdown = str(result.details.get("report_markdown", "") or "").strip()
    if not raw_context or not markdown:
        return
    try:
        context = DecisionReportContext.model_validate_json(raw_context)
    except ValueError:
        return
    _attach_decision_report_context_to_turn(
        turn,
        context=context,
        markdown=markdown,
        source="assistant_action_execution",
    )


def _append_action_result_state(value: str, result: AssistantActionResult) -> str:
    items = _assistant_action_results_from_state(value)
    items.append(result.model_dump(mode="json"))
    return json.dumps(items[-5:], ensure_ascii=False)


def _apply_action_result_to_workflow_session_state(
    value: str,
    result: AssistantActionResult,
) -> str:
    if not value.strip():
        return ""
    try:
        session = AssistantWorkflowSession.model_validate_json(value)
    except ValueError:
        return value
    step_id = _workflow_session_step_id_for_action(session, result.action_id)
    if not step_id:
        return value
    updated = apply_assistant_workflow_action_result(session, step_id, result)
    return updated.model_dump_json()


def _workflow_session_step_id_for_action(
    session: AssistantWorkflowSession,
    action_id: str,
) -> str:
    active = next(
        (
            step
            for step in session.steps
            if step.step_id == session.active_step_id and step.action_id == action_id
        ),
        None,
    )
    if active is not None:
        return active.step_id
    candidate = next(
        (
            step
            for step in session.steps
            if step.action_id == action_id
            and step.status not in {"done", "failed", "skipped", "cancelled", "blocked"}
        ),
        None,
    )
    if candidate is not None:
        return candidate.step_id
    fallback = next((step for step in session.steps if step.action_id == action_id), None)
    return fallback.step_id if fallback is not None else ""


def _latest_confirmable_assistant_action_turn(
    history: list[dict[str, str]],
) -> tuple[dict[str, str], str] | None:
    for turn in reversed(history):
        if str(turn.get("status", "")) != "complete":
            continue
        action_id = _first_confirmable_action_id(turn)
        if not action_id:
            continue
        if _turn_has_action_result(turn, action_id):
            continue
        return turn, action_id
    return None


def _first_confirmable_action_id(turn: dict[str, str]) -> str:
    session = _assistant_workflow_session_dict(turn)
    if session:
        return _first_confirmable_action_id_from_session(turn, session)
    if str(turn.get("assistant_workflow_session_gate", "")).strip() == "blocked":
        return ""
    workflow = _assistant_guided_workflow_dict(turn)
    workflow_steps = workflow.get("steps")
    if isinstance(workflow_steps, list):
        for step in workflow_steps:
            if not isinstance(step, dict):
                continue
            action_id = str(step.get("action_id", "")).strip()
            if action_id not in COPILOT_CONFIRMABLE_ACTION_IDS:
                continue
            if _turn_has_action_result(turn, action_id):
                continue
            if not bool(step.get("requires_confirmation")):
                continue
            return action_id
    plan = _assistant_tool_plan_dict(turn)
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return ""
    for step in steps:
        if not isinstance(step, dict):
            continue
        action_id = str(step.get("action_id", "")).strip()
        if action_id not in COPILOT_CONFIRMABLE_ACTION_IDS:
            continue
        if _turn_has_action_result(turn, action_id):
            continue
        if not bool(step.get("requires_confirmation")):
            continue
        return action_id
    return ""


def _first_confirmable_action_id_from_session(
    turn: dict[str, str],
    session: dict[str, object],
) -> str:
    if str(session.get("status", "")).strip() in {"completed", "cancelled", "failed"}:
        return ""
    steps = session.get("steps")
    if not isinstance(steps, list):
        return ""
    terminal_statuses = {"done", "running", "failed", "skipped", "cancelled", "blocked"}
    for step in steps:
        if not isinstance(step, dict):
            continue
        action_id = str(step.get("action_id", "")).strip()
        if action_id not in COPILOT_CONFIRMABLE_ACTION_IDS:
            continue
        if not bool(step.get("requires_confirmation")):
            continue
        if str(step.get("status", "")).strip() in terminal_statuses:
            continue
        return action_id
    return ""


def _turn_has_action_result(turn: dict[str, str], action_id: str) -> bool:
    for result in _assistant_action_results_from_state(
        str(turn.get("assistant_action_results", ""))
    ):
        if str(result.get("action_id", "")) == action_id:
            return True
    return False


def _turn_by_id(
    history: list[dict[str, str]],
    turn_id: str,
) -> dict[str, str] | None:
    return next((turn for turn in history if str(turn.get("turn_id", "")) == turn_id), None)


def _assistant_action_target_label(
    turn: dict[str, str],
    context: SmaiAssistantContext,
) -> str:
    symbol = _assistant_action_symbol(turn, context)
    company = _assistant_action_company_name(turn, context)
    if symbol and company:
        return f"{symbol} - {company}"
    if symbol:
        return symbol
    return copilot_context_label(context)


def _assistant_action_symbol(
    turn: dict[str, str],
    context: SmaiAssistantContext,
) -> str:
    return (
        str(turn.get("decision_report_symbol", "")).strip()
        or str(context.summary.get("銘柄", "")).strip()
        or str(context.summary.get("symbol", "")).strip()
    )


def _assistant_action_company_name(
    turn: dict[str, str],
    context: SmaiAssistantContext,
) -> str:
    return (
        str(turn.get("decision_report_company_name", "")).strip()
        or str(context.summary.get("会社名", "")).strip()
        or str(context.summary.get("company_name", "")).strip()
    )


def _assistant_action_confirm_label(action_id: str) -> str:
    if action_id == "update_research":
        return "AI調査を更新する前に確認"
    if action_id == "create_decision_report":
        return "確認レポートを作る前に確認"
    return "実行前に確認"


def _assistant_action_execute_label(action_id: str) -> str:
    if action_id == "update_research":
        return "AI調査を更新する"
    if action_id == "create_decision_report":
        return "作成する"
    return "実行する"


def _assistant_action_materials(context: SmaiAssistantContext) -> tuple[str, ...]:
    return tuple(
        f"{label}: {value}" for label, value in _material_status(context) if label != "LLM"
    )


def _render_decision_report_draft_action(history: list[dict[str, str]]) -> bool:
    turn = _latest_decision_report_ready_turn(history)
    if turn is None:
        return False
    draft = st.session_state.get(COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY)
    if isinstance(draft, dict) and str(draft.get("turn_id", "")) == str(turn.get("turn_id", "")):
        return False
    label = (
        "Decision Reportに保存"
        if _normalize_intent(turn.get("intent", "")) == "decision_report_draft"
        else "Decision Reportに追加"
    )
    st.markdown(
        '<div class="smai-copilot-chat-actions-anchor" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    _, action_col = st.columns([0.68, 0.32], gap="small")
    with action_col:
        if st.button(
            label,
            key=f"smai_copilot_add_decision_report_{turn.get('turn_id', '')}",
            use_container_width=True,
            help="この回答に紐づくDecision Report下書きを作成します。",
        ):
            _store_pending_decision_report_draft(turn, action_label=label)
            return True
    return False


def _render_pending_decision_report_draft_preview() -> None:
    draft = st.session_state.get(COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY)
    if not isinstance(draft, dict):
        return
    markdown = str(draft.get("markdown", "")).strip()
    if not markdown:
        return
    status = str(draft.get("status", "draft_ready"))
    context = _decision_report_context_from_draft(draft)
    if status == "archived":
        saved_path = _display_path(str(draft.get("archive_markdown_path", "")))
        st.success(f"Decision Report下書きを保存しました。保存先: {saved_path}")
        if str(draft.get("manifest_status", "")) == "partial":
            st.warning("下書きファイルは保存されましたが、manifestの更新に失敗しました。")
    elif status == "archive_failed":
        st.error(
            "Decision Report下書きを保存できませんでした。ファイル権限または保存先を確認してください。"
        )
    else:
        st.info("Decision Report下書きを作成しました。内容を確認して保存できます。")
    with st.expander("Decision Report下書きプレビュー", expanded=True):
        st.markdown(markdown)
        save_col, markdown_col, zip_col, cancel_col = st.columns(4, gap="small")
        with save_col:
            if st.button(
                "下書きを保存",
                key=f"smai_copilot_report_draft_save_{draft.get('turn_id', '')}",
                use_container_width=True,
            ):
                _archive_pending_decision_report_draft(draft, context=context)
                st.rerun()
        with markdown_col:
            st.download_button(
                "Markdown保存",
                data=markdown,
                file_name=_memo_filename(
                    {
                        "intent": "decision_report_draft",
                        "context_label": (
                            draft.get("company_name") or draft.get("symbol") or "SMAI"
                        ),
                    }
                ),
                mime="text/markdown",
                key=f"smai_copilot_report_draft_download_{draft.get('turn_id', '')}",
                use_container_width=True,
            )
        with zip_col:
            if context is not None:
                zip_manifest = build_assistant_decision_report_archive_entry(
                    context,
                    markdown=markdown,
                    markdown_filename="report.md",
                    zip_filename="assistant_decision_report.zip",
                )
                st.download_button(
                    "ZIP保存",
                    data=assistant_decision_report_zip_download(markdown, zip_manifest),
                    file_name=_memo_filename(
                        {
                            "intent": "decision_report_draft",
                            "context_label": (
                                draft.get("company_name") or draft.get("symbol") or "SMAI"
                            ),
                        },
                        extension="zip",
                    ),
                    mime="application/zip",
                    key=f"smai_copilot_report_draft_zip_{draft.get('turn_id', '')}",
                    use_container_width=True,
                )
            else:
                st.button(
                    "ZIP保存",
                    key=f"smai_copilot_report_draft_zip_disabled_{draft.get('turn_id', '')}",
                    use_container_width=True,
                    disabled=True,
                )
        with cancel_col:
            if st.button(
                "キャンセル",
                key=f"smai_copilot_report_draft_cancel_{draft.get('turn_id', '')}",
                use_container_width=True,
            ):
                st.session_state.pop(COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY, None)
                st.rerun()


def _archive_pending_decision_report_draft(
    draft: dict[str, object],
    *,
    context: DecisionReportContext | None,
) -> None:
    updated = dict(draft)
    if context is None:
        updated["status"] = "archive_failed"
        st.session_state[COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY] = updated
        return
    try:
        result = archive_assistant_decision_report_draft(
            context,
            _assistant_decision_report_archive_dir(),
            markdown=str(draft.get("markdown", "")),
            include_zip=True,
        )
    except OSError:
        updated["status"] = "archive_failed"
        st.session_state[COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY] = updated
        return

    updated.update(
        {
            "status": "archived",
            "archive_draft_id": result.draft_id,
            "archive_markdown_path": str(result.markdown_path),
            "archive_manifest_path": str(result.manifest_path),
            "archive_zip_path": str(result.zip_path or ""),
            "manifest_status": "updated" if result.manifest_updated else "partial",
        }
    )
    st.session_state[COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY] = updated
    _mark_turn_report_draft_status(str(draft.get("turn_id", "")), "archived")


def _decision_report_context_from_draft(
    draft: Mapping[str, object],
) -> DecisionReportContext | None:
    raw_context = str(draft.get("context", "")).strip()
    if not raw_context:
        return None
    try:
        return DecisionReportContext.model_validate_json(raw_context)
    except ValueError:
        return None


def _assistant_decision_report_archive_dir() -> Path:
    return Path("exports") / "decision_reports"


def _display_path(path: str) -> str:
    if not path:
        return "未確認"
    try:
        return Path(path).relative_to(Path.cwd()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _latest_decision_report_ready_turn(
    history: list[dict[str, str]],
) -> dict[str, str] | None:
    for turn in reversed(history):
        if (
            str(turn.get("status", "")) == "complete"
            and str(turn.get("can_add_to_decision_report", "")).lower() == "true"
            and str(turn.get("decision_report_markdown", "")).strip()
        ):
            return turn
    return None


def _store_pending_decision_report_draft(turn: dict[str, str], *, action_label: str) -> None:
    draft = {
        "source": str(turn.get("decision_report_source", "assistant_research_mode")),
        "turn_id": str(turn.get("turn_id", "")),
        "symbol": str(turn.get("decision_report_symbol", "")),
        "company_name": str(turn.get("decision_report_company_name", "")),
        "markdown": str(turn.get("decision_report_markdown", "")),
        "context": str(turn.get("decision_report_context", "")),
        "created_at": str(turn.get("created_at", "")),
        "status": "draft_ready",
        "action_label": action_label,
    }
    st.session_state[COPILOT_PENDING_DECISION_REPORT_DRAFT_STATE_KEY] = draft
    _mark_turn_report_draft_status(str(turn.get("turn_id", "")), "pending_draft_created")


def _mark_turn_report_draft_status(turn_id: str, status: str) -> None:
    if not turn_id:
        return
    history = _copilot_history()
    next_history: list[dict[str, str]] = []
    for turn in history:
        if str(turn.get("turn_id", "")) == turn_id:
            updated = dict(turn)
            updated["report_draft_status"] = status
            next_history.append(updated)
        else:
            next_history.append(turn)
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = next_history


def _handle_tool_plan_choice(
    turn: dict[str, str],
    *,
    choice: str,
    label: str,
    context_by_id: dict[str, SmaiAssistantContext],
    fallback_context: SmaiAssistantContext,
    runtime_config: CopilotGatewayRuntimeConfig,
) -> None:
    history = _copilot_history()
    resolved_history: list[dict[str, str]] = []
    for item in history:
        if str(item.get("turn_id", "")) == str(turn.get("turn_id", "")):
            resolved = dict(item)
            resolved["status"] = "tool_plan_resolved"
            resolved["approval_choice"] = label
            resolved_history.append(resolved)
        else:
            resolved_history.append(item)
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = resolved_history

    context = context_by_id.get(str(turn.get("context_id", "")), fallback_context)
    intent = _normalize_intent(turn.get("intent", "stock_summary"))
    question = str(turn.get("question", "")).strip()
    if choice == "cancel":
        _append_tool_plan_cancel_turn(context=context, question=label)
        return

    followup_state = _tool_plan_followup_state(turn=turn, choice=choice)
    _queue_copilot_submit(
        context,
        question,
        intent=intent,
        prompt_instruction=_tool_plan_followup_instruction(turn=turn, choice=choice),
        visible_question=label,
        runtime_config=runtime_config,
        pending_overrides=followup_state,
        request_overrides=followup_state,
    )


def _append_tool_plan_cancel_turn(*, context: SmaiAssistantContext, question: str) -> None:
    history = _copilot_history()
    history.append(
        {
            "turn_id": uuid4().hex,
            "status": "complete",
            "context_id": context.context_id,
            "context_label": copilot_context_label(context),
            "intent": "free_chat",
            "intent_label": "調査キャンセル",
            "question": question,
            "answer": (
                "了解しました。外部情報の取得は行いません。"
                "必要になったら、いつでも「材料を取得して分析して」と聞いてください。"
            ),
            "reasons": "",
            "cautions": "",
            "next_checkpoints": "",
            "memo_points": "",
            "executed_checks": "ユーザーが調査をキャンセル",
            "tool_statuses": "",
            "conversation_mode": "research_plan",
            "response_source": "deterministic_fallback",
            "fallback_reason": "research_cancelled",
            "response_meta": "SMAI通常回答 / research_cancelled / free_chat",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = history
    update_assistant_runtime_status(
        AssistantStatusEvent(
            name="cancelled",
            runtime_config=copilot_gateway_runtime_config(),
        )
    )


def _tool_plan_followup_instruction(*, turn: dict[str, str], choice: str) -> str:
    tools = _tool_plan_tools_from_turn(turn)
    labels = "、".join(str(tool["label"]) for tool in tools) or "取得済み材料"
    subject = _tool_plan_subject_from_turn(turn)
    missing = _external_tool_labels_from_tools(tools)
    missing_text = "、".join(missing) if missing else "外部取得が必要な材料"
    if choice == "cached_only":
        return (
            "ユーザーは外部取得を行わず、取得済み情報だけで回答することを選びました。"
            "冒頭は「取得済み情報だけで整理します。現時点では未取得の材料もあるため、"
            "価格・AI予測・ニュースのうち確認できている範囲に絞って回答します。」としてください。"
            f"対象は {subject} です。確認予定は {labels} です。"
            f"未確認材料として {missing_text} を必ず明示してください。"
            "売買推奨、スコア変更、ランキング変更、予測値変更はしないでください。"
        )
    return (
        "ユーザーはTool Planを承認しました。SMAI側のread-only文脈と、承認後に取得できた"
        "外部ニュース・Research Evidenceを使って整理してください。取得失敗または未取得の材料は"
        "未確認として明示してください。"
        f"対象は {subject} です。計画された材料: {labels}。"
        "冒頭は「取得できた材料を整理しました。買い/売りを断定するのではなく、"
        "上昇方向を見る材料と注意すべき材料に分けて確認します。」の趣旨にしてください。"
        "回答は「結論」「上昇方向を見る材料」「注意すべき材料」「未確認材料」「次に確認」に分けてください。"
        "売買推奨、スコア変更、ランキング変更、予測値変更はしないでください。"
    )


def _tool_plan_followup_state(*, turn: dict[str, str], choice: str) -> dict[str, str]:
    tools = _tool_plan_tools_from_turn(turn)
    missing = _external_tool_labels_from_tools(tools)
    return {
        "tool_plan_choice": choice,
        "tool_plan_subject": _tool_plan_subject_from_turn(turn),
        "tool_plan_tools": str(turn.get("tool_plan_tools", "")),
        "tool_plan_missing_materials": "\n".join(missing),
        "conversation_mode": "research_running",
        "pending_steps": "\n".join(str(tool["label"]) for tool in tools),
        "answer": (
            "SMAIナビが材料を確認しています..."
            if choice == "approve"
            else "SMAIナビが取得済み情報を整理しています..."
        ),
    }


def _external_tool_labels_from_tools(tools: list[dict[str, object]]) -> list[str]:
    return [str(tool["label"]) for tool in tools if bool(tool.get("external"))]


def _pending_message_for_intent(intent: CopilotIntent) -> str:
    return {
        "free_chat": "SMAIナビが考えています...",
        "identity": "SMAIナビが考えています...",
        "capability_help": "SMAIナビができることを整理しています...",
        "app_help": "SMAIナビが使い方を整理しています...",
        "stock_summary": "SMAIナビが銘柄・価格・材料を確認しています...",
        "forecast_risk_compare": "SMAIナビが予測とリスクを見比べています...",
        "news_materials": "SMAIナビがニュース材料を整理しています...",
        "decision_report_draft": "SMAIナビがDecision Report向けに整理しています...",
    }[intent]


def _pending_steps_for_intent(intent: CopilotIntent, *, uses_llm: bool = True) -> tuple[str, ...]:
    answer_step = "LLMへ回答作成を依頼中" if uses_llm else "回答を作成中"
    lightweight_answer_step = "LLMへ短い回答を依頼中" if uses_llm else "短い回答を作成中"
    return {
        "free_chat": (
            "質問の意図を確認中",
            "SMAIナビの文脈を準備中",
            lightweight_answer_step,
        ),
        "identity": (
            "質問の意図を確認中",
            "SMAIナビの自己紹介文脈を準備中",
            lightweight_answer_step,
        ),
        "capability_help": (
            "相談内容を読み取り中",
            "SMAIで使える機能を整理中",
            lightweight_answer_step,
        ),
        "app_help": (
            "相談内容を読み取り中",
            "SMAIの画面・使い方を整理中",
            answer_step,
        ),
        "stock_summary": (
            "銘柄を確認中",
            "価格・予測材料を確認中",
            "ニュース材料を整理中",
            answer_step,
        ),
        "forecast_risk_compare": (
            "銘柄と期間を確認中",
            "価格・予測材料を確認中",
            "リスク材料を整理中",
            answer_step,
        ),
        "news_materials": (
            "相談テーマを確認中",
            "ニュース材料を整理中",
            "未確認材料を分けています",
            answer_step,
        ),
        "decision_report_draft": (
            "会話と参照材料を確認中",
            "Decision Reportの見出しを準備中",
            "未確認事項を整理中",
            answer_step,
        ),
    }[intent]


def _pending_detail_html(turn: dict[str, str]) -> str:
    if str(turn.get("tool_plan_choice", "")).strip() == "approve":
        return _tool_plan_progress_html(turn)
    steps = _split_lines(turn.get("pending_steps", ""))
    if not steps:
        intent = _normalize_intent(turn.get("intent", "free_chat"))
        steps = list(_pending_steps_for_intent(intent))
    current_step = _pending_current_step_label(turn=turn, steps=steps)
    return (
        '<section class="smai-copilot-pending-steps" aria-label="現在の処理" aria-live="polite">'
        '<span class="smai-copilot-pending-caption">現在の処理</span>'
        '<div class="smai-copilot-pending-current">'
        '<span class="smai-copilot-pending-current-dot" aria-hidden="true"></span>'
        f'<span class="smai-copilot-pending-current-label">{html.escape(current_step)}</span>'
        "</div>"
        "</section>"
    )


def _tool_plan_progress_html(turn: dict[str, str]) -> str:
    tools = _tool_plan_tools_from_turn(turn)
    if not tools:
        return _pending_detail_html({**turn, "tool_plan_choice": ""})
    subject = str(turn.get("tool_plan_subject", "")).strip()
    raw_index = str(turn.get("pending_step_index", "0")).strip()
    try:
        step_index = int(raw_index)
    except ValueError:
        step_index = 0
    bounded_index = max(0, min(step_index, len(tools) - 1))
    items = "".join(
        _tool_plan_progress_item_html(
            tool=tool,
            index=index,
            current_index=bounded_index,
            subject=subject,
        )
        for index, tool in enumerate(tools)
    )
    return (
        '<section class="smai-copilot-tool-progress" aria-label="材料確認の進捗" '
        'aria-live="polite">'
        '<span class="smai-copilot-pending-caption">材料を確認中</span>'
        '<p class="smai-copilot-tool-progress-lead">SMAIナビが材料を確認しています...</p>'
        f"<ul>{items}</ul>"
        "</section>"
    )


def _tool_plan_progress_item_html(
    *,
    tool: dict[str, object],
    index: int,
    current_index: int,
    subject: str,
) -> str:
    label = str(tool["label"])
    if index < current_index:
        prefix = "✓"
        text = _tool_plan_completed_progress_label(label=label, subject=subject)
        state_class = "complete"
    elif index == current_index:
        prefix = "…"
        text = f"{label}を確認中"
        state_class = "current"
    else:
        prefix = "…"
        text = f"{label}を確認中"
        state_class = "pending"
    return (
        f'<li class="smai-copilot-tool-progress-item '
        f'smai-copilot-tool-progress-item--{state_class}">'
        f"<span>{html.escape(prefix)}</span>"
        f"<b>{html.escape(text)}</b>"
        "</li>"
    )


def _tool_plan_completed_progress_label(*, label: str, subject: str) -> str:
    if label == "銘柄を特定" and subject:
        return f"銘柄を特定: {subject}"
    if label == "価格の動き":
        return "価格の動きを確認"
    if label == "AI予測・下振れ警戒":
        return "AI予測・下振れ警戒を確認"
    return f"{label}を確認"


def _pending_current_step_label(*, turn: dict[str, str], steps: list[str]) -> str:
    if not steps:
        return "確認中"
    raw_index = str(turn.get("pending_step_index", "0")).strip()
    try:
        step_index = int(raw_index)
    except ValueError:
        step_index = 0
    bounded_index = max(0, min(step_index, len(steps) - 1))
    return steps[bounded_index]


def _runtime_config_to_state(config: CopilotGatewayRuntimeConfig) -> dict[str, object]:
    return {
        "enabled": config.enabled,
        "base_url": config.base_url,
        "timeout_seconds": config.timeout_seconds,
        "context_answer_path": config.context_answer_path,
        "execution_mode": config.execution_mode,
        "environment_profile": config.environment_profile,
        "provider": config.provider,
        "model": config.model,
        "profile": config.profile,
        "readiness_status": config.readiness_status,
        "readiness_message": config.readiness_message,
        "gateway_url": config.gateway_url,
        "gateway_error_type": config.gateway_error_type,
        "gateway_error_message": config.gateway_error_message,
        "http_status": config.http_status,
        "provider_error_type": config.provider_error_type,
        "provider_error_message": config.provider_error_message,
        "ollama_base_url": config.ollama_base_url,
        "installed_models": list(config.installed_models),
    }


def _runtime_config_from_state(value: object) -> CopilotGatewayRuntimeConfig:
    if not isinstance(value, dict):
        return copilot_gateway_runtime_config()
    http_status_value = value.get("http_status")
    http_status = (
        int(http_status_value)
        if http_status_value is not None and str(http_status_value).strip()
        else None
    )
    raw_installed_models = value.get("installed_models", [])
    return CopilotGatewayRuntimeConfig(
        enabled=bool(value.get("enabled", True)),
        base_url=str(value.get("base_url", "http://127.0.0.1:8088")),
        timeout_seconds=float(value.get("timeout_seconds", 90.0) or 90.0),
        context_answer_path=str(value.get("context_answer_path", "/api/v1/context-answer")),
        execution_mode=str(value.get("execution_mode", "auto")),
        environment_profile=str(value.get("environment_profile", "notebook")),
        provider=str(value.get("provider", "ollama")),
        model=str(value.get("model", "qwen3:1.7b")),
        profile=str(value.get("profile", "notebook_dev")),
        readiness_status=str(value.get("readiness_status", "unchecked")),
        readiness_message=str(value.get("readiness_message", "")),
        gateway_url=str(value.get("gateway_url", "")),
        gateway_error_type=str(value.get("gateway_error_type", "")),
        gateway_error_message=str(value.get("gateway_error_message", "")),
        http_status=http_status,
        provider_error_type=str(value.get("provider_error_type", "")),
        provider_error_message=str(value.get("provider_error_message", "")),
        ollama_base_url=str(value.get("ollama_base_url", "")),
        installed_models=(
            tuple(str(item).strip() for item in raw_installed_models if str(item).strip())
            if isinstance(raw_installed_models, list)
            else ()
        ),
    )


def _handle_copilot_submit(
    context: SmaiAssistantContext,
    question: str,
    *,
    intent: CopilotIntent,
    prompt_instruction: str,
    visible_question: str,
    runtime_config: CopilotGatewayRuntimeConfig,
    pending_turn_id: str | None = None,
    tool_plan_choice: str = "",
    tool_plan_subject: str = "",
    tool_plan_missing_materials: list[str] | None = None,
    tool_plan_tools: str = "",
    conversation_mode: str = "normal_chat",
) -> None:
    normalized_question = question.strip()
    if not normalized_question:
        st.warning("質問を入力してください。")
        return

    history = _copilot_history()
    history_for_request = [
        turn
        for turn in history
        if not pending_turn_id or str(turn.get("turn_id", "")) != pending_turn_id
    ]
    recent_report_draft = _latest_decision_report_draft_from_history(history_for_request)
    conversation_id = _conversation_id()
    effective_context = _context_for_llm(
        intent=intent, context=context, question=normalized_question
    )
    tool_plan = (
        execute_assistant_tool_plan(
            intent=intent,
            message=normalized_question,
            report_context=assistant_context_to_report_context(context),
        )
        if not _is_llm_micro_intent(intent)
        else None
    )
    if tool_plan is not None:
        tool_plan = _tool_plan_with_approved_external_fetch(
            tool_plan=tool_plan,
            choice=tool_plan_choice,
            subject=tool_plan_subject,
            question=normalized_question,
            tool_plan_tools=tool_plan_tools,
        )
    research_context_bundle = (
        build_assistant_research_context_bundle(
            subject=tool_plan_subject,
            choice=_research_choice_from_tool_plan_choice(tool_plan_choice),
            tool_plan=tool_plan,
            planned_tools=_tool_plan_tools_from_state(tool_plan_tools),
        )
        if tool_plan_choice and tool_plan is not None
        else None
    )
    if research_context_bundle is not None:
        effective_context = _context_with_research_bundle(
            context=effective_context,
            bundle=research_context_bundle,
        )
    tool_summaries = (
        list(research_context_bundle.llm_context_lines())
        if research_context_bundle is not None
        else [result.summary for result in tool_plan.executed] if tool_plan else []
    )
    friendly_tool_summaries = (
        list(research_context_bundle.executed_check_lines())
        if research_context_bundle is not None
        else tool_summaries
    )
    gateway_question = _gateway_question(
        question=normalized_question,
        intent=intent,
        prompt_instruction=prompt_instruction,
        tool_summaries=tool_summaries,
    )
    response = assistant_response_for_context(
        effective_context,
        gateway_question,
        conversation_id=conversation_id,
        message_history=(
            () if _is_llm_micro_intent(intent) else copilot_history_messages(history_for_request)
        ),
        referenced_context_ids=[] if _is_llm_micro_intent(intent) else [context.context_id],
        gateway_task_type=intent,
        settings=copilot_settings_from_gateway_runtime(runtime_config),
    )
    if _readiness_status_from_assistant_response(response):
        runtime_config = _runtime_config_from_assistant_response(
            runtime_config=runtime_config,
            response=response,
        )
        _cache_gateway_runtime_config(runtime_config)
    update_assistant_runtime_status(
        AssistantStatusEvent(
            name="response_completed",
            runtime_config=runtime_config,
            response=response,
        )
    )
    turn = _turn_from_response(
        context,
        visible_question,
        response,
        intent=intent,
        turn_id=pending_turn_id,
        executed_checks=[
            *([] if _is_llm_micro_intent(intent) else [_material_status_summary(context)]),
            *friendly_tool_summaries,
        ],
        tool_statuses=[
            f"{result.name}: {result.status}"
            for result in (tool_plan.executed if tool_plan else ())
        ],
    )
    turn["conversation_mode"] = "research_answer" if tool_plan_choice else conversation_mode
    if tool_plan_choice:
        turn["answer"] = _with_tool_plan_answer_prefix(
            answer=turn["answer"],
            choice=tool_plan_choice,
            subject=tool_plan_subject,
            missing_materials=tool_plan_missing_materials or [],
            research_context=research_context_bundle,
            response_source=response.response_source,
        )
        if research_context_bundle is not None:
            _apply_research_context_to_turn(turn, research_context_bundle)
            _attach_research_decision_report_draft(
                turn,
                research_context_bundle,
                user_question=normalized_question,
                intent=intent,
            )
    if intent == "decision_report_draft" and recent_report_draft is not None:
        _copy_decision_report_draft_to_turn(turn, recent_report_draft)
    elif (
        intent == "decision_report_draft"
        and tool_plan is not None
        and tool_plan.report_context is not None
        and str(turn.get("can_add_to_decision_report", "")).lower() != "true"
    ):
        _attach_tool_plan_decision_report_draft(turn, tool_plan.report_context)
    if pending_turn_id:
        replaced = False
        next_history: list[dict[str, str]] = []
        for item in history:
            if str(item.get("turn_id", "")) == pending_turn_id:
                next_history.append(turn)
                replaced = True
            else:
                next_history.append(item)
        if not replaced:
            next_history.append(turn)
        history = next_history
    else:
        history.append(turn)
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = history
    st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = intent
    st.session_state[COPILOT_PENDING_STREAM_STATE_KEY] = turn["turn_id"]


def _tool_plan_with_approved_external_fetch(
    *,
    tool_plan: AssistantToolPlanResult,
    choice: str,
    subject: str,
    question: str,
    tool_plan_tools: str,
) -> AssistantToolPlanResult:
    if choice != "approve":
        return tool_plan
    planned_tools = _tool_plan_tools_from_state(tool_plan_tools)
    include_news = any(str(tool.get("name", "")) == "news_fetch" for tool in planned_tools)
    include_research = any(str(tool.get("name", "")) == "research_fetch" for tool in planned_tools)
    if not include_news and not include_research:
        return tool_plan

    symbol = _external_fetch_symbol_for_tool_plan(tool_plan=tool_plan, subject=subject)
    if not symbol:
        external_results = assistant_tool_results_from_external_research_failure(
            message="対象銘柄を特定できなかったため、外部ニュースとResearch Evidenceは未確認です。",
            include_news=include_news,
            include_research=include_research,
        )
        return _replace_tool_plan_results(tool_plan, external_results)

    company_name = _external_fetch_company_name(subject=subject, symbol=symbol)
    related_keywords = _external_fetch_related_keywords(
        subject=subject,
        question=question,
        company_name=company_name,
    )
    try:
        fetch_result = fetch_external_research_for_symbol(
            symbol,
            company_name=company_name,
            related_keywords=related_keywords,
            allow_network=True,
        )
    except Exception:
        external_results = assistant_tool_results_from_external_research_failure(
            message="外部情報の取得結果を確認できませんでした。今回は取得済み材料を中心に整理します。",
            include_news=include_news,
            include_research=include_research,
        )
        return _replace_tool_plan_results(tool_plan, external_results)

    external_results = assistant_tool_results_from_external_research_fetch(
        fetch_result,
        include_news=include_news,
        include_research=include_research,
    )
    return _replace_tool_plan_results(tool_plan, external_results)


def _replace_tool_plan_results(
    tool_plan: AssistantToolPlanResult,
    replacements: tuple[AssistantToolResult, ...],
) -> AssistantToolPlanResult:
    if not replacements:
        return tool_plan
    replacements_by_name = {result.name: result for result in replacements}
    seen: set[str] = set()
    executed: list[AssistantToolResult] = []
    for result in tool_plan.executed:
        replacement = replacements_by_name.get(result.name)
        if replacement is not None:
            executed.append(replacement)
            seen.add(replacement.name)
        else:
            executed.append(result)
    for result in replacements:
        if result.name not in seen and not any(item.name == result.name for item in executed):
            executed.append(result)
    return replace(tool_plan, executed=tuple(executed))


def _external_fetch_symbol_for_tool_plan(
    *,
    tool_plan: AssistantToolPlanResult,
    subject: str,
) -> str:
    for result in tool_plan.executed:
        symbol = str(result.details.get("symbol", "")).strip()
        if symbol:
            return symbol
    if tool_plan.current_context.symbol:
        return tool_plan.current_context.symbol
    for token in str(subject or "").replace("（", "(").replace("）", ")").split("("):
        clean = token.split(")", 1)[0].strip().upper()
        if clean.endswith(".T") and clean[:-2].isdigit():
            return clean
        if clean.isascii() and clean.isalnum() and 1 <= len(clean) <= 5:
            return clean
    return ""


def _external_fetch_company_name(*, subject: str, symbol: str) -> str | None:
    clean_subject = str(subject or "").strip()
    if not clean_subject:
        return None
    for separator in ("（", "("):
        if separator in clean_subject:
            company = clean_subject.split(separator, 1)[0].strip()
            return company or None
    if clean_subject.strip().upper() == symbol.strip().upper():
        return None
    return clean_subject


def _external_fetch_related_keywords(
    *,
    subject: str,
    question: str,
    company_name: str | None,
) -> list[str]:
    keywords: list[str] = []
    for value in (company_name, subject, question):
        clean = str(value or "").strip()
        if clean and clean not in keywords:
            keywords.append(clean)
    return keywords[:4]


def _runtime_config_from_assistant_response(
    *,
    runtime_config: CopilotGatewayRuntimeConfig,
    response: AssistantResponse,
) -> CopilotGatewayRuntimeConfig:
    if not runtime_config.enabled:
        return runtime_config
    readiness_status = _readiness_status_from_assistant_response(response)
    if not readiness_status:
        return runtime_config
    return replace(
        runtime_config,
        readiness_status=readiness_status,
        readiness_message=_readiness_message_from_assistant_response(
            status=readiness_status,
            response=response,
        ),
        gateway_url=response.gateway_url or runtime_config.gateway_url,
        gateway_error_type=response.gateway_error_type or "",
        gateway_error_message=response.gateway_error_message or "",
        http_status=response.http_status,
        provider_error_type=response.provider_error_type or "",
        provider_error_message=response.provider_error_message or "",
        provider=response.provider or runtime_config.provider,
        model=response.model or runtime_config.model,
        profile=response.profile or runtime_config.profile,
    )


def _readiness_status_from_assistant_response(response: AssistantResponse) -> str:
    if response.gateway_status == "ok" or response.response_source in {"llm", "gateway"}:
        return "ready"
    reason = str(response.fallback_reason or "").strip()
    if reason == "gateway_unavailable":
        return "gateway_unavailable"
    if reason == "gateway_timeout":
        return "gateway_timeout"
    if reason in {"provider_unavailable", "provider_timeout"}:
        return "provider_unavailable"
    if reason == "model_not_found":
        return "model_missing"
    if reason in {"response_validation_failure", "empty_llm_answer"}:
        return "gateway_error"
    if response.gateway_error_type:
        return "gateway_error"
    if response.provider_error_type:
        return "provider_unavailable"
    return ""


def _readiness_message_from_assistant_response(
    *,
    status: str,
    response: AssistantResponse,
) -> str:
    if status == "ready":
        elapsed = f"（{response.latency_ms}ms）" if response.latency_ms is not None else ""
        return f"最新回答でGateway応答を確認しました{elapsed}。"
    if status == "gateway_unavailable":
        return response.gateway_error_message or "smai-ai-gateway に接続できません。"
    if status == "gateway_timeout":
        return "回答時のGateway接続がタイムアウトしました。次回送信時に再試行します。"
    if status == "provider_unavailable":
        if response.provider_error_message:
            return response.provider_error_message
        if response.fallback_reason == "provider_timeout":
            return "Ollamaの応答がタイムアウトしました。次回送信時に再試行します。"
        return "Ollama APIに接続できません。"
    if status == "model_missing":
        return f"{response.model or '指定モデル'} がOllamaに見つかりません。"
    if response.fallback_reason == "response_validation_failure":
        return "Gateway応答の形式を確認できませんでした。次回送信時に再試行します。"
    if response.fallback_reason == "empty_llm_answer":
        return "Gateway応答が空でした。取得済み材料で回答しました。"
    return response.gateway_error_message or "Gateway応答を確認できませんでした。"


def _friendly_tool_execution_summaries(
    *,
    tool_plan_tools: str,
    tool_plan: Any,
    subject: str,
) -> list[str]:
    planned_tools = _tool_plan_tools_from_state(tool_plan_tools)
    results = {str(result.name): result for result in (tool_plan.executed if tool_plan else ())}
    items: list[str] = []
    for tool in planned_tools:
        result = results.get(_tool_result_name_for_plan_tool(str(tool["name"])))
        label = str(tool["label"])
        if result is None:
            items.append(f"… {label}: 確認中")
            continue
        if result.status == "ok":
            items.append(f"✓ {_tool_plan_completed_progress_label(label=label, subject=subject)}")
        else:
            items.append(f"… {label}: 取得できませんでした")
    return items


def _tool_result_name_for_plan_tool(name: str) -> str:
    return {
        "symbol_resolve": "resolve_symbol",
        "price_fetch": "get_price_summary",
        "forecast_fetch": "get_forecast_summary",
        "news_fetch": "search_news_materials",
        "research_fetch": "search_rag_materials",
        "decision_report_draft": "build_decision_report",
    }.get(name, name)


def _with_tool_plan_answer_prefix(
    *,
    answer: str,
    choice: str,
    subject: str,
    missing_materials: list[str],
    research_context: AssistantResearchContextBundle | None = None,
    response_source: str = "",
) -> str:
    body = str(answer or "").strip()
    if research_context is not None and (
        response_source not in {"gateway", "llm"} or _is_research_context_echo(body)
    ):
        body = ""
    clean_subject = subject.strip() or "対象銘柄"
    missing = _missing_materials_block(
        list(research_context.missing_labels()) if research_context else missing_materials
    )
    research_block = (
        _research_context_answer_block(research_context) if research_context is not None else ""
    )
    if choice == "cached_only":
        prefix = (
            "取得済み情報だけで整理します。\n"
            "現時点では未取得の材料もあるため、価格・AI予測・ニュースのうち"
            "確認できている範囲に絞って回答します。"
        )
        return _join_answer_parts(prefix, research_block or missing, body)
    prefix = (
        f"{clean_subject}について、取得できた材料を整理しました。\n"
        "買い/売りを断定するのではなく、上昇方向を見る材料と注意すべき材料に分けて確認します。"
    )
    return _join_answer_parts(prefix, research_block, body)


def _research_choice_from_tool_plan_choice(
    choice: str,
) -> Literal["approve", "cached_only", "normal"]:
    if choice == "cached_only":
        return "cached_only"
    if choice == "approve":
        return "approve"
    return "normal"


def _context_with_research_bundle(
    *,
    context: SmaiAssistantContext,
    bundle: AssistantResearchContextBundle,
) -> SmaiAssistantContext:
    rows = [
        {
            "分類": "確認できた材料",
            "項目": material.label,
            "状態": "確認済み",
            "要約": material.summary,
        }
        for material in bundle.confirmed_materials
    ]
    rows.extend(
        {
            "分類": "未確認材料",
            "項目": material.label,
            "状態": "未確認",
            "要約": material.summary,
        }
        for material in bundle.missing_materials
    )
    summary = {
        **{str(key): value for key, value in context.summary.items()},
        "対象": bundle.subject,
        "回答方針": (
            "取得済み情報だけ" if bundle.choice == "cached_only" else "取得できた材料を整理"
        ),
        "確認できた材料": " / ".join(material.label for material in bundle.confirmed_materials)
        or "なし",
        "未確認材料": " / ".join(bundle.missing_labels()) or "なし",
    }
    return replace(
        context,
        summary=summary,
        rows=tuple(rows),
        warnings=tuple([*context.warnings, *bundle.caution_materials]),
        notes=tuple([*context.notes, *bundle.next_checkpoints]),
    )


def _apply_research_context_to_turn(
    turn: dict[str, str],
    bundle: AssistantResearchContextBundle,
) -> None:
    turn["hide_answer_grid"] = "true"
    confirmed = [f"{material.label}: {material.summary}" for material in bundle.confirmed_materials]
    missing = [f"{material.label}: {material.summary}" for material in bundle.missing_materials]
    turn["reasons"] = "\n".join(confirmed[:4])
    turn["cautions"] = "\n".join([*bundle.caution_materials[:3], *missing[:2]])
    turn["next_checkpoints"] = "\n".join(bundle.next_checkpoints[:4])
    if not turn.get("memo_points", "").strip():
        turn["memo_points"] = (
            f"対象: {bundle.subject}\n"
            f"確認済み: {', '.join(material.label for material in bundle.confirmed_materials) or 'なし'}\n"
            f"未確認: {', '.join(bundle.missing_labels()) or 'なし'}"
        )


def _attach_research_decision_report_draft(
    turn: dict[str, str],
    bundle: AssistantResearchContextBundle,
    *,
    user_question: str,
    intent: CopilotIntent,
) -> None:
    context = assistant_research_bundle_to_decision_report_context(
        bundle,
        user_question=user_question,
        assistant_answer=turn.get("answer", ""),
        intent=intent,
    )
    markdown = render_research_bundle_markdown_memo(context)
    _attach_decision_report_context_to_turn(
        turn,
        context=context,
        markdown=markdown,
        source="assistant_research_mode",
    )
    turn["research_bundle"] = "\n".join(bundle.llm_context_lines())


def _attach_tool_plan_decision_report_draft(
    turn: dict[str, str],
    context: DecisionReportContext,
) -> None:
    _attach_decision_report_context_to_turn(
        turn,
        context=context,
        markdown=render_decision_report_markdown(context),
        source="assistant_tool_layer",
    )


def _attach_decision_report_context_to_turn(
    turn: dict[str, str],
    *,
    context: DecisionReportContext,
    markdown: str,
    source: str,
) -> None:
    turn["decision_report_context"] = context.model_dump_json(indent=2)
    turn["decision_report_markdown"] = markdown
    turn["can_add_to_decision_report"] = "true"
    turn["report_draft_status"] = "draft_ready"
    turn["decision_report_source"] = source
    turn["decision_report_symbol"] = _decision_report_symbol(context)
    turn["decision_report_company_name"] = _decision_report_company_name(context)


def _copy_decision_report_draft_to_turn(
    turn: dict[str, str],
    draft_turn: dict[str, str],
) -> None:
    for key in (
        "research_bundle",
        "decision_report_context",
        "decision_report_markdown",
        "decision_report_source",
        "decision_report_symbol",
        "decision_report_company_name",
    ):
        turn[key] = str(draft_turn.get(key, ""))
    turn["can_add_to_decision_report"] = "true"
    turn["report_draft_status"] = "draft_ready_from_recent_research"
    if "直近の調査結果" not in str(turn.get("answer", "")):
        turn["answer"] = _join_answer_parts(
            "直近の調査結果をDecision Report下書きとして整理しました。",
            str(turn.get("answer", "")),
        )


def _latest_decision_report_draft_from_history(
    history: list[dict[str, str]],
) -> dict[str, str] | None:
    for turn in reversed(history):
        if (
            str(turn.get("can_add_to_decision_report", "")).lower() == "true"
            and str(turn.get("decision_report_markdown", "")).strip()
            and str(turn.get("decision_report_context", "")).strip()
        ):
            return turn
    return None


def _decision_report_symbol(context: DecisionReportContext) -> str:
    return next(
        (section.source.symbol for section in context.sections if section.source.symbol),
        "",
    )


def _decision_report_company_name(context: DecisionReportContext) -> str:
    for section in context.sections:
        value = section.summary.get("company_name")
        if value:
            return str(value)
    return ""


def _research_context_answer_block(bundle: AssistantResearchContextBundle | None) -> str:
    if bundle is None:
        return ""
    confirmed = _markdown_bullets(
        f"{material.label}: {material.summary}" for material in bundle.confirmed_materials
    )
    cautions = _markdown_bullets(bundle.caution_materials)
    missing = _markdown_bullets(
        f"{material.label}: {material.summary}" for material in bundle.missing_materials
    )
    next_steps = _markdown_bullets(bundle.next_checkpoints)
    return _join_answer_parts(
        f"確認できた材料:\n{confirmed}" if confirmed else "",
        f"注意すべき材料:\n{cautions}" if cautions else "",
        f"未確認材料:\n{missing}" if missing else "",
        f"次に確認:\n{next_steps}" if next_steps else "",
    )


def _markdown_bullets(items: Any) -> str:
    lines = [str(item).strip() for item in items if str(item).strip()]
    return "\n".join(f"- {line}" for line in lines[:5])


def _is_research_context_echo(body: str) -> bool:
    clean_body = str(body or "").strip()
    if (
        len(clean_body) <= 160
        and "取得できた材料を整理しました" in clean_body
        and "買い/売りを断定" in clean_body
    ):
        return True
    return all(
        marker in clean_body
        for marker in (
            "見る材料",
            "注意点",
            "次に確認",
            "銘柄を特定:",
        )
    )


def _missing_materials_block(missing_materials: list[str]) -> str:
    items = [item.strip() for item in missing_materials if item.strip()]
    if not items:
        return ""
    lines = "\n".join(f"- {item}" for item in items)
    return f"未確認材料:\n{lines}"


def _join_answer_parts(*parts: str) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _context_for_llm(
    *,
    intent: CopilotIntent,
    context: SmaiAssistantContext,
    question: str,
) -> SmaiAssistantContext:
    if not _is_llm_micro_intent(intent):
        return context
    return SmaiAssistantContext(
        context_id=f"copilot_{intent}_minimal",
        page_key="assistant",
        page_label="SMAIアシスタント",
        section_key=intent,
        section_label="SMAIナビとの軽い相談",
        lead="SMAIナビが短く自然に答えるための最小文脈です。",
        summary={
            "assistant_name": "SMAIナビ",
            "screen": "SMAIアシスタント",
            "role": "Smart Market AIの投資判断アシスタント",
            "message": question[:120],
        },
        priority=100,
    )


def _turn_from_response(
    context: SmaiAssistantContext,
    question: str,
    response: AssistantResponse,
    *,
    intent: CopilotIntent = "stock_summary",
    turn_id: str | None = None,
    executed_checks: list[str] | None = None,
    tool_statuses: list[str] | None = None,
) -> dict[str, str]:
    answer = sanitize_presentation_text(
        _conversation_answer(intent=intent, question=question, response=response)
    )
    if not answer:
        answer = _intent_fallback_answer(intent=intent, question=question)
    item_limit = _item_limit_for_intent(intent)
    reasons = sanitize_presentation_items(response.reasons, limit=item_limit)
    cautions = sanitize_presentation_items(response.cautions, limit=item_limit)
    next_checkpoints = sanitize_presentation_items(
        response.next_checkpoints,
        limit=1 if _is_llm_micro_intent(intent) else item_limit,
    )
    memo_points = sanitize_presentation_items(
        _memo_points_for_intent(intent, response), limit=item_limit
    )
    if _is_llm_micro_intent(intent):
        reasons = []
        cautions = []
        memo_points = []
        if intent not in {"app_help", "screen_guidance"}:
            next_checkpoints = []
    intent_decision = detect_assistant_intent(question)
    action_card_decision = decide_assistant_action_cards(question, intent_decision.intent)
    planner_states = (
        _assistant_planner_states(context=context, question=question)
        if action_card_decision.show_cards
        else None
    )
    assistant_tool_plan = (
        planner_states.tool_plan.model_dump_json() if planner_states is not None else ""
    )
    guided_workflow = planner_states.guided_workflow if planner_states is not None else None
    assistant_workflow_session = _assistant_workflow_session_state(guided_workflow)
    assistant_workflow_session_gate = (
        "blocked"
        if guided_workflow is not None and not assistant_workflow_session
        else "passed" if assistant_workflow_session else "not_applicable"
    )
    assistant_guided_workflow = (
        guided_workflow.model_dump_json()
        if guided_workflow is not None and assistant_workflow_session
        else ""
    )
    planner_meta = planner_states.metadata if planner_states is not None else None
    return {
        "turn_id": turn_id or uuid4().hex,
        "status": "complete",
        "context_id": context.context_id,
        "context_label": copilot_context_label(context),
        "intent": intent,
        "intent_label": _preset_for_intent(intent).label,
        "question": question,
        "answer": answer,
        "reasons": "\n".join(reasons),
        "cautions": "\n".join(cautions),
        "next_checkpoints": "\n".join(next_checkpoints),
        "memo_points": "\n".join(memo_points),
        "executed_checks": "\n".join(sanitize_presentation_items(executed_checks or (), limit=6)),
        "tool_statuses": "\n".join(tool_statuses or ()),
        "conversation_mode": "normal_chat",
        "response_source": response.response_source,
        "model": response.model or "",
        "provider": response.provider or "",
        "profile": response.profile or "",
        "latency_ms": str(response.latency_ms or ""),
        "gateway_status": response.gateway_status or "",
        "fallback_reason": response.fallback_reason or "",
        "gateway_error_type": response.gateway_error_type or "",
        "gateway_error_message": response.gateway_error_message or "",
        "gateway_url": response.gateway_url or "",
        "http_status": str(response.http_status or ""),
        "provider_error_type": response.provider_error_type or "",
        "provider_error_message": response.provider_error_message or "",
        "request_id": response.request_id or "",
        "timeout_sec": str(response.timeout_sec or ""),
        "context_tokens_estimate": str(response.context_tokens_estimate or ""),
        "prompt_chars": str(response.prompt_chars or ""),
        "response_chars": str(response.response_chars or ""),
        "tool_execution_ms": str(response.tool_execution_ms or ""),
        "llm_generation_ms": str(response.llm_generation_ms or ""),
        "total_elapsed_ms": str(response.total_elapsed_ms or ""),
        "response_meta": _response_meta_label(response=response, intent=intent),
        "research_bundle": "",
        "decision_report_context": "",
        "decision_report_markdown": "",
        "can_add_to_decision_report": "",
        "report_draft_status": "",
        "decision_report_source": "",
        "decision_report_symbol": "",
        "decision_report_company_name": "",
        "assistant_action_results": "",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "assistant_tool_plan": assistant_tool_plan,
        "assistant_guided_workflow": assistant_guided_workflow,
        "assistant_workflow_session": assistant_workflow_session,
        "assistant_workflow_session_gate": assistant_workflow_session_gate,
        "assistant_action_card_level": str(action_card_decision.level),
        "assistant_action_card_reason": action_card_decision.reason,
        "assistant_planner_source": planner_meta.planner_source if planner_meta else "suppressed",
        "assistant_planner_used_plan_type": (
            planner_meta.used_plan_type or "" if planner_meta else ""
        ),
        "assistant_planner_fallback_reason": (
            planner_meta.fallback_reason or "" if planner_meta else ""
        ),
        "assistant_planner_provider": planner_meta.provider or "" if planner_meta else "",
        "assistant_planner_model": planner_meta.model or "" if planner_meta else "",
        "assistant_planner_profile": planner_meta.profile or "" if planner_meta else "",
        "assistant_planner_gateway_status": (
            planner_meta.gateway_status or "" if planner_meta else ""
        ),
        "assistant_planner_request_id": planner_meta.request_id or "" if planner_meta else "",
        "assistant_planner_meta": planner_meta.model_dump_json() if planner_meta else "",
    }


def _assistant_planner_states(
    *,
    context: SmaiAssistantContext,
    question: str,
):
    assistant_context = _assistant_backend_context_for_ui_context(
        context=context,
        question=question,
    )
    return build_assistant_planner_states(assistant_context)


def _assistant_guided_workflow_state(
    *,
    context: SmaiAssistantContext,
    question: str,
) -> str:
    states = _assistant_planner_states(
        context=context,
        question=question,
    )
    if states.guided_workflow is None:
        return ""
    return states.guided_workflow.model_dump_json()


def _assistant_workflow_session_state(
    workflow: AssistantGuidedWorkflow | None,
) -> str:
    if workflow is None:
        return ""
    session = start_assistant_workflow_session(workflow)
    if session is None:
        return ""
    return session.model_dump_json()


def _assistant_tool_plan_state(
    *,
    context: SmaiAssistantContext,
    question: str,
) -> str:
    states = _assistant_planner_states(
        context=context,
        question=question,
    )
    return states.tool_plan.model_dump_json()


def _assistant_backend_context_for_ui_context(
    *,
    context: SmaiAssistantContext,
    question: str,
):
    material_state = {
        _material_state_key(label): value
        for label, value in _material_status(context)
        if _material_state_key(label)
    }
    page_state = {
        "current_context_id": context.context_id,
        "section": context.section_label,
        "active_symbol": context.summary.get("銘柄") or context.summary.get("symbol"),
        "ranking_policy": context.summary.get("評価方針"),
        "candidate_count": context.summary.get("候補数"),
    }
    assistant_context = build_assistant_context(
        current_page=context.page_key,
        user_question=question,
        page_state={key: value for key, value in page_state.items() if value},
        material_state=material_state,
        report_context=assistant_context_to_report_context(context),
        metadata={"ui_context_id": context.context_id},
    )
    return assistant_context


def _assistant_tool_plan_dict(turn: dict[str, str]) -> dict[str, object]:
    value = str(turn.get("assistant_tool_plan", "")).strip()
    if not value:
        return {}
    try:
        plan = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return plan if isinstance(plan, dict) else {}


def _assistant_guided_workflow_dict(turn: dict[str, str]) -> dict[str, object]:
    value = str(turn.get("assistant_guided_workflow", "")).strip()
    if not value:
        return {}
    try:
        workflow = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return workflow if isinstance(workflow, dict) else {}


def _assistant_workflow_session_dict(turn: dict[str, str]) -> dict[str, object]:
    value = str(turn.get("assistant_workflow_session", "")).strip()
    if not value:
        return {}
    try:
        session = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return session if isinstance(session, dict) else {}


def _assistant_action_results_from_state(value: str) -> list[dict[str, object]]:
    if not value.strip():
        return []
    try:
        raw = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _assistant_action_result_by_action_id(
    turn: dict[str, str],
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for item in _assistant_action_results_from_state(str(turn.get("assistant_action_results", ""))):
        action_id = str(item.get("action_id", "")).strip()
        if action_id:
            results[action_id] = item
    return results


def _material_state_key(label: str) -> str:
    return {
        "価格": "price_data_status",
        "AI予測": "forecast_status",
        "ニュース": "news_status",
        "Research Evidence": "research_status",
        "Decision Report": "decision_report_status",
        "LLM": "llm_gateway_status",
    }.get(label, "")


def _copilot_history() -> list[dict[str, str]]:
    raw_history = st.session_state.get(COPILOT_CHAT_HISTORY_STATE_KEY)
    if not isinstance(raw_history, list):
        raw_history = []
        st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = raw_history
    return [
        {str(key): str(value) for key, value in item.items()}
        for item in raw_history
        if isinstance(item, dict)
    ]


def _conversation_id() -> str:
    conversation_id = st.session_state.get(COPILOT_CONVERSATION_ID_STATE_KEY)
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        conversation_id = _new_conversation_id()
        st.session_state[COPILOT_CONVERSATION_ID_STATE_KEY] = conversation_id
    return conversation_id


def _new_conversation_id() -> str:
    return f"smai-copilot-{uuid4().hex}"


def _chat_header_html(
    *,
    history_count: int,
    runtime_config: CopilotGatewayRuntimeConfig | None = None,
    runtime_status: AssistantRuntimeStatus | None = None,
    has_pending: bool = False,
) -> str:
    runtime_config = runtime_config or CopilotGatewayRuntimeConfig(
        enabled=True,
        base_url="http://127.0.0.1:8088",
        timeout_seconds=90.0,
        context_answer_path="/api/v1/context-answer",
        execution_mode="auto",
        environment_profile="notebook",
    )
    runtime_status = runtime_status or _assistant_runtime_status_for_header(
        history=[],
        runtime_config=runtime_config,
        has_pending=has_pending,
    )
    status_label = runtime_status.label
    status_detail = runtime_status.message
    if (
        history_count
        and runtime_status.state == "checking"
        and runtime_config.readiness_status == "unchecked"
    ):
        status_detail = f"会話 {history_count}件"
    llm_label = (
        f"LLM: {runtime_status.provider or runtime_config.provider} / "
        f"{runtime_status.model or runtime_config.model}"
        if runtime_config.enabled
        else "LLM: deterministic fallback"
    )
    statusbar_class = (
        "smai-copilot-statusbar "
        f"smai-copilot-statusbar--{runtime_status.severity} "
        f"smai-copilot-statusbar-state--{runtime_status.state}"
    )
    navi_image = _asset_data_uri(MASCOT_NAVI_CHAT_ASSET)
    return (
        '<section class="smai-copilot-chat-topbar">'
        '<div class="smai-copilot-header-identity">'
        '<div class="smai-copilot-header-icon" aria-hidden="true">'
        f'<img src="{navi_image}" alt="" loading="lazy" />'
        "</div>"
        '<div class="smai-copilot-header-title">'
        '<span class="smai-copilot-eyebrow">SMAIアシスタント</span>'
        "<h1>SMAIナビ</h1>"
        "<p>銘柄・予測・ニュース・根拠資料を横断して、確認すべき材料を整理します。</p>"
        "</div>"
        "</div>"
        f'<div class="{statusbar_class}" data-status-state="{html.escape(runtime_status.state)}">'
        '<span class="smai-copilot-chat-status-dot" aria-hidden="true"></span>'
        f"<strong>{status_label}</strong>"
        f"<small>{html.escape(status_detail)}</small>"
        f"<small>{html.escape(llm_label)}</small>"
        "</div>"
        "</section>"
    )


def _user_bubble_html(*, context_label: str, question: str) -> str:
    return (
        '<section class="smai-copilot-message-row smai-copilot-message-row--user">'
        '<div class="smai-copilot-message-card smai-copilot-message-card--user">'
        '<div class="smai-copilot-message-meta">あなたの確認</div>'
        f'<div class="smai-copilot-message-context">{html.escape(context_label)}</div>'
        f"<p>{html.escape(question)}</p>"
        "</div>"
        "</section>"
    )


def _assistant_bubble_html(*, answer: str, detail_html: str, is_pending: bool = False) -> str:
    image = _asset_data_uri(MASCOT_THUMB_ASSET)
    card_class = "smai-copilot-message-card smai-copilot-message-card--assistant"
    if is_pending:
        card_class += " smai-copilot-message-card--pending"
    pending_dots = (
        '<div class="smai-copilot-pending-dots" aria-hidden="true">'
        "<span></span><span></span><span></span>"
        "</div>"
        if is_pending
        else ""
    )
    return (
        '<section class="smai-copilot-message-row smai-copilot-message-row--assistant">'
        '<div class="smai-copilot-assistant-avatar" aria-hidden="true">'
        f'<img class="smai-copilot-assistant-avatar-image '
        f'smai-copilot-assistant-avatar-image--reply" src="{image}" alt="" loading="lazy" />'
        "</div>"
        f'<div class="{card_class}">'
        '<div class="smai-copilot-message-meta">SMAIナビ</div>'
        f'<p class="smai-copilot-natural-lead">{html.escape(answer)}</p>'
        f"{pending_dots}"
        f"{detail_html}"
        "</div>"
        "</section>"
    )


def _render_streaming_turn(
    previous_turns: list[dict[str, str]],
    turn: dict[str, str],
    *,
    placeholder: Any | None = None,
) -> None:
    context_label = str(turn.get("context_label", "")).strip()
    question = str(turn.get("question", "")).strip()
    answer = str(turn.get("answer", "")).strip()
    previous_rows = "".join(_copilot_turn_rows_html(item) for item in previous_turns)
    user_row = _user_bubble_html(context_label=context_label, question=question)
    stream_placeholder = placeholder or st.empty()
    for partial in _stream_chunks(answer):
        stream_placeholder.markdown(
            (
                '<div class="smai-copilot-thread">'
                f"{previous_rows}{user_row}"
                f'{_assistant_bubble_html(answer=partial, detail_html="")}'
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        time.sleep(COPILOT_STREAM_DELAY_SECONDS)
    stream_placeholder.markdown(
        (
            '<div class="smai-copilot-thread">'
            f"{previous_rows}{user_row}"
            f"{_assistant_bubble_html(answer=answer, detail_html=copilot_answer_detail_html(turn))}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _stream_chunks(text: str) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return [""]
    segments = _stream_segments(normalized)
    if len(segments) > 1:
        chunk_count = min(COPILOT_STREAM_MAX_CHUNKS, len(segments))
        chunks = []
        for step in range(1, chunk_count + 1):
            boundary = (len(segments) * step + chunk_count - 1) // chunk_count
            chunks.append("".join(segments[:boundary]).strip())
        return _deduplicate_stream_chunks(chunks, normalized)
    chunk_count = min(
        COPILOT_STREAM_MAX_CHUNKS,
        max(2, min(6, (len(normalized) + 23) // 24)),
    )
    chunks = [
        normalized[: (len(normalized) * step + chunk_count - 1) // chunk_count]
        for step in range(1, chunk_count + 1)
    ]
    return _deduplicate_stream_chunks(chunks, normalized)


def _stream_segments(text: str) -> list[str]:
    sentence_segments = _split_stream_segments(text, "。！？!?\n")
    if len(sentence_segments) > 1:
        return sentence_segments
    phrase_segments = _split_stream_segments(text, "、，,;；:")
    return phrase_segments if len(phrase_segments) > 1 else [text]


def _split_stream_segments(text: str, break_chars: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    for character in text:
        current.append(character)
        if character in break_chars:
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
    tail = "".join(current).strip()
    if tail:
        segments.append(tail)
    return segments


def _deduplicate_stream_chunks(chunks: list[str], final_text: str) -> list[str]:
    deduplicated: list[str] = []
    for chunk in chunks:
        if chunk and (not deduplicated or chunk != deduplicated[-1]):
            deduplicated.append(chunk)
    if not deduplicated or deduplicated[-1] != final_text:
        deduplicated.append(final_text)
    return deduplicated


def _action_card_intro_html(*, preset: CopilotConversationPreset) -> str:
    return (
        '<div class="smai-copilot-action-card">'
        f'<span class="smai-copilot-action-label">{html.escape(preset.label)}</span>'
        f"<p>{html.escape(preset.description)}</p>"
        "</div>"
    )


def _tool_plan_answer(plan: AssistantResearchToolPlan) -> str:
    subject = _tool_plan_subject_label(
        symbol=plan.symbol,
        symbol_query=plan.symbol_query,
        company_name=_research_plan_company_name(plan),
    )
    approval_text = (
        "最新のニュース・開示・IR候補を確認するため、実行前に確認します。"
        if plan.has_external_tools
        else "SMAI内の取得済み材料を整理する前に確認します。"
    )
    return (
        f"{subject}について、確認する材料を整理しました。"
        "価格・AI予測・ニュースなどを確認すると、上昇材料と注意材料を分けて見やすくなります。"
        f"{approval_text}"
    )


def _research_plan_company_name(plan: AssistantResearchToolPlan) -> str | None:
    value = getattr(plan, "company_name", None)
    if value is not None:
        return str(value).strip() or None
    return _known_research_company_name(
        symbol=getattr(plan, "symbol", None),
        symbol_query=getattr(plan, "symbol_query", None),
    )


def _known_research_company_name(*, symbol: object, symbol_query: object) -> str | None:
    aliases = {
        "7203.T": "トヨタ自動車",
        "6758.T": "ソニーグループ",
        "9432.T": "日本電信電話",
        "8058.T": "三菱商事",
        "9532.T": "大阪ガス",
        "トヨタ": "トヨタ自動車",
        "toyota": "トヨタ自動車",
        "ソニー": "ソニーグループ",
        "sony": "ソニーグループ",
        "ntt": "日本電信電話",
        "三菱商事": "三菱商事",
        "大阪ガス": "大阪ガス",
    }
    clean_symbol = str(symbol or "").strip()
    if clean_symbol in aliases:
        return aliases[clean_symbol]
    clean_query = str(symbol_query or "").strip()
    if clean_query in aliases:
        return aliases[clean_query]
    lowered_query = clean_query.lower()
    if lowered_query in aliases:
        return aliases[lowered_query]
    return None


def _tool_plan_display_copy(
    *,
    name: str,
    label: str,
    reason: str,
) -> tuple[str, str]:
    copy_by_name = {
        "symbol_resolve": (
            "銘柄を特定",
            "入力された銘柄名から、対象銘柄を確認します。",
        ),
        "price_fetch": (
            "価格の動き",
            "直近の価格推移や変動を確認します。",
        ),
        "forecast_fetch": (
            "AI予測・下振れ警戒",
            "AI予測の方向感と、下振れリスクを確認します。",
        ),
        "news_fetch": (
            "最新ニュース",
            "直近ニュースや開示材料を確認します。",
        ),
        "research_fetch": (
            "根拠資料 / Research Evidence",
            "根拠資料や外部参照ソースを確認します。",
        ),
    }
    return copy_by_name.get(name, (label, reason))


def _tool_plan_detail_html(turn: dict[str, str]) -> str:
    tools = _tool_plan_tools_from_turn(turn)
    subject = _tool_plan_subject_from_turn(turn)
    approval_choice = str(turn.get("approval_choice", "")).strip()
    items = "".join(
        (
            "<li>"
            f'<b>{html.escape(str(tool["label"]))}</b>'
            f'<span>{html.escape(str(tool["reason"]))}</span>'
            f'<small>{"外部取得あり" if bool(tool["external"]) else "SMAI内で確認"}'
            f' / {"必須" if bool(tool["required"]) else "任意"}</small>'
            "</li>"
        )
        for tool in tools
    )
    choice_html = (
        '<p class="smai-copilot-tool-plan-choice">' f"選択済み: {html.escape(approval_choice)}</p>"
        if approval_choice
        else ""
    )
    return (
        '<section class="smai-copilot-tool-plan">'
        '<span class="smai-copilot-tool-plan-title">調査計画</span>'
        f"<p>対象: {html.escape(subject)}</p>"
        "<p>確認する材料を以下に分けて進めます。</p>"
        f"<ul>{items}</ul>"
        f"{choice_html}"
        "</section>"
    )


def _assistant_tool_plan_panel_html(turn: dict[str, str]) -> str:
    value = str(turn.get("assistant_tool_plan", "")).strip()
    if not value:
        return ""
    try:
        plan = json.loads(value)
    except json.JSONDecodeError:
        return ""
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return ""
    items = "".join(_assistant_tool_plan_step_html(step) for step in steps[:5])
    if not items:
        return ""
    missing = _assistant_tool_plan_inline_items(plan.get("missing_materials"), "未確認")
    warnings = _assistant_tool_plan_inline_items(plan.get("warnings"), "注意")
    safety_note = str(plan.get("safety_note", "")).strip()
    return (
        '<section class="smai-copilot-tool-plan smai-copilot-tool-plan--next-actions">'
        '<span class="smai-copilot-tool-plan-title">次にできること</span>'
        f"<p>{html.escape(str(plan.get('overall_summary', '')).strip())}</p>"
        f"<ul>{items}</ul>"
        f"{missing}"
        f"{warnings}"
        f'<p class="smai-copilot-tool-plan-safety">{html.escape(safety_note)}</p>'
        "</section>"
    )


def _assistant_guided_workflow_panel_html(turn: dict[str, str]) -> str:
    session = _assistant_workflow_session_dict(turn)
    if session:
        return _assistant_workflow_session_panel_html(session)
    workflow = _assistant_guided_workflow_dict(turn)
    steps = workflow.get("steps")
    if not isinstance(steps, list) or not steps:
        return ""
    action_results = _assistant_action_result_by_action_id(turn)
    items = "".join(
        _assistant_guided_workflow_step_html(
            step,
            index=index,
            action_results=action_results,
        )
        for index, step in enumerate(steps[:6], start=1)
    )
    if not items:
        return ""
    safety_note = str(workflow.get("safety_note", "")).strip()
    return (
        '<section class="smai-copilot-tool-plan smai-copilot-guided-workflow">'
        '<span class="smai-copilot-tool-plan-title">確認フロー</span>'
        f"<p>{html.escape(str(workflow.get('summary', '')).strip())}</p>"
        f"<ul>{items}</ul>"
        f'<p class="smai-copilot-tool-plan-safety">{html.escape(safety_note)}</p>'
        "</section>"
    )


def _assistant_workflow_session_panel_html(session: dict[str, object]) -> str:
    steps = session.get("steps")
    if not isinstance(steps, list) or not steps:
        return ""
    active_step_id = str(session.get("active_step_id", "")).strip()
    items = "".join(
        _assistant_workflow_session_step_html(
            step,
            index=index,
            active_step_id=active_step_id,
        )
        for index, step in enumerate(steps[:6], start=1)
    )
    if not items:
        return ""
    status = _assistant_workflow_session_status_label(str(session.get("status", "")).strip())
    safety_note = str(session.get("safety_note", "")).strip()
    summary = str(session.get("summary", "")).strip()
    status_line = f"進行状態: {status}"
    if active_step_id:
        active_title = _assistant_workflow_active_step_title(steps, active_step_id)
        if active_title:
            status_line = f"{status_line} / 現在: {active_title}"
    return (
        '<section class="smai-copilot-tool-plan smai-copilot-guided-workflow">'
        '<span class="smai-copilot-tool-plan-title">確認フロー</span>'
        f"<p>{html.escape(summary)}</p>"
        f'<p class="smai-copilot-tool-plan-note">{html.escape(status_line)}</p>'
        f"<ul>{items}</ul>"
        f'<p class="smai-copilot-tool-plan-safety">{html.escape(safety_note)}</p>'
        "</section>"
    )


def _assistant_workflow_session_step_html(
    step: object,
    *,
    index: int,
    active_step_id: str,
) -> str:
    if not isinstance(step, dict):
        return ""
    title = str(step.get("title", "")).strip()
    summary = str(step.get("summary", "")).strip()
    action_id = str(step.get("action_id", "")).strip()
    disabled_reason = _clean_optional_tool_plan_text(step.get("disabled_reason"))
    followup_hint = _clean_optional_tool_plan_text(step.get("followup_hint"))
    result_summary = _clean_optional_tool_plan_text(step.get("result_summary"))
    status = _assistant_workflow_runtime_status_label(str(step.get("status", "")).strip())
    active_label = "現在の手順" if str(step.get("step_id", "")).strip() == active_step_id else ""
    action = get_assistant_action(action_id) if action_id else None
    action_label = action.label if action else _workflow_kind_label(step)
    href = _assistant_tool_plan_navigation_href(action_id)
    action_html = (
        '<a class="smai-copilot-tool-plan-link" '
        f'href="{html.escape(href, quote=True)}" target="_self">開く</a>'
        if href and not disabled_reason
        else ""
    )
    details = " / ".join(
        item
        for item in (
            action_label,
            status,
            active_label,
            disabled_reason,
            result_summary,
            followup_hint,
        )
        if item
    )
    return (
        "<li>"
        f"<b>{index}. {html.escape(title)}</b>"
        f"<span>{html.escape(summary)}</span>"
        f"<small>{html.escape(details)}</small>"
        f"{action_html}"
        "</li>"
    )


def _assistant_workflow_active_step_title(
    steps: list[object],
    active_step_id: str,
) -> str:
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("step_id", "")).strip() == active_step_id:
            return str(step.get("title", "")).strip()
    return ""


def _assistant_workflow_session_status_label(status: str) -> str:
    return {
        "planned": "計画済み",
        "active": "進行中",
        "paused": "一時停止",
        "completed": "完了",
        "cancelled": "中止",
        "failed": "停止中",
    }.get(status, status or "計画済み")


def _assistant_workflow_runtime_status_label(status: str) -> str:
    return {
        "planned": "予定",
        "waiting_confirmation": "確認待ち",
        "running": "実行中",
        "done": "完了",
        "failed": "失敗",
        "skipped": "スキップ",
        "cancelled": "中止",
        "blocked": "実行できません",
    }.get(status, status or "予定")


def _assistant_guided_workflow_step_html(
    step: object,
    *,
    index: int,
    action_results: dict[str, dict[str, object]],
) -> str:
    if not isinstance(step, dict):
        return ""
    title = str(step.get("title", "")).strip()
    summary = str(step.get("summary", "")).strip()
    action_id = str(step.get("action_id", "")).strip()
    disabled_reason = _clean_optional_tool_plan_text(step.get("disabled_reason"))
    followup_hint = _clean_optional_tool_plan_text(step.get("followup_hint"))
    result = action_results.get(action_id)
    status = _assistant_workflow_status_label(step, result)
    action = get_assistant_action(action_id) if action_id else None
    action_label = action.label if action else _workflow_kind_label(step)
    href = _assistant_tool_plan_navigation_href(action_id)
    action_html = (
        '<a class="smai-copilot-tool-plan-link" '
        f'href="{html.escape(href, quote=True)}" target="_self">開く</a>'
        if href and not disabled_reason
        else ""
    )
    result_summary = ""
    if result:
        result_summary = _clean_optional_tool_plan_text(result.get("summary"))
    details = " / ".join(
        item
        for item in (
            action_label,
            status,
            disabled_reason,
            result_summary,
            followup_hint,
        )
        if item
    )
    return (
        "<li>"
        f"<b>{index}. {html.escape(title)}</b>"
        f"<span>{html.escape(summary)}</span>"
        f"<small>{html.escape(details)}</small>"
        f"{action_html}"
        "</li>"
    )


def _assistant_workflow_status_label(
    step: dict[str, object],
    result: dict[str, object] | None,
) -> str:
    if result:
        status = str(result.get("status", "")).strip()
        return {
            "success": "完了",
            "partial_success": "一部完了",
            "failed": "失敗",
            "skipped": "未実行",
            "cancelled": "キャンセル済み",
            "not_available": "利用不可",
            "validation_error": "確認エラー",
        }.get(status, status or "結果あり")
    status = str(step.get("status", "")).strip()
    return {
        "ready": "開けます",
        "waiting_confirmation": "実行前確認",
        "suggested": "必要なら確認",
        "blocked": "利用不可",
        "done": "完了",
        "skipped": "未実行",
        "failed": "失敗",
    }.get(status, status or "提案")


def _workflow_kind_label(step: dict[str, object]) -> str:
    kind = str(step.get("kind", "")).strip()
    return {
        "navigation": "画面確認",
        "confirmable_action": "確認付き操作",
        "review": "材料確認",
        "manual_check": "手動確認",
        "not_available": "利用不可",
    }.get(kind, "確認")


def _assistant_tool_plan_step_html(step: object) -> str:
    if not isinstance(step, dict):
        return ""
    title = str(step.get("title", "")).strip()
    summary = str(step.get("summary", "")).strip()
    action_id = str(step.get("action_id", "")).strip()
    disabled_reason = _clean_optional_tool_plan_text(step.get("disabled_reason"))
    requires_confirmation = bool(step.get("requires_confirmation"))
    action = get_assistant_action(action_id) if action_id else None
    action_label = action.label if action else action_id
    confirmation = "実行前確認" if requires_confirmation else "画面確認"
    disabled = f" / {disabled_reason}" if disabled_reason else ""
    href = _assistant_tool_plan_navigation_href(action_id)
    action_html = (
        '<a class="smai-copilot-tool-plan-link" '
        f'href="{html.escape(href, quote=True)}" target="_self">開く</a>'
        if href and not disabled_reason
        else ""
    )
    return (
        "<li>"
        f"<b>{html.escape(title)}</b>"
        f"<span>{html.escape(summary)}</span>"
        f"<small>{html.escape(action_label)} / {html.escape(confirmation + disabled)}</small>"
        f"{action_html}"
        "</li>"
    )


def _clean_optional_tool_plan_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _assistant_tool_plan_navigation_href(action_id: str) -> str:
    page_by_action = {
        "open_ranking": SIDEMENU_PAGE_RANKING,
        "open_cockpit": SIDEMENU_PAGE_COCKPIT,
        "open_symbol_from_ranking": SIDEMENU_PAGE_COCKPIT,
        "open_news_radar": SIDEMENU_PAGE_NEWS,
        "open_macro_news": SIDEMENU_PAGE_NEWS,
        "open_symbol_related_news": SIDEMENU_PAGE_NEWS,
    }
    page = page_by_action.get(action_id)
    if not page:
        return ""
    return "?" + urlencode({"smai_page": page})


def _assistant_tool_plan_inline_items(value: object, label: str) -> str:
    if not isinstance(value, list):
        return ""
    items = [str(item).strip() for item in value if str(item).strip()]
    if not items:
        return ""
    visible = " / ".join(items[:4])
    return (
        f'<p class="smai-copilot-tool-plan-note">{html.escape(label)}: '
        f"{html.escape(visible)}</p>"
    )


def _tool_plan_subject_from_turn(turn: dict[str, str]) -> str:
    symbol = str(turn.get("symbol", "")).strip() or None
    symbol_query = str(turn.get("symbol_query", "")).strip() or None
    company_name = str(turn.get("company_name", "")).strip() or None
    return _tool_plan_subject_label(
        symbol=symbol,
        symbol_query=symbol_query,
        company_name=company_name
        or _known_research_company_name(symbol=symbol, symbol_query=symbol_query),
    )


def _tool_plan_subject_label(
    *,
    symbol: str | None,
    symbol_query: str | None,
    company_name: str | None,
) -> str:
    clean_symbol = str(symbol or "").strip()
    clean_company = str(company_name or "").strip()
    if clean_company and clean_symbol:
        return f"{clean_company}（{clean_symbol}）"
    if clean_symbol:
        return clean_symbol
    return str(symbol_query or "この相談").strip() or "この相談"


def _tool_plan_tools_state(plan: AssistantResearchToolPlan) -> str:
    rows: list[str] = []
    for tool in plan.tools:
        label, reason = _tool_plan_display_copy(
            name=tool.name,
            label=tool.label,
            reason=tool.reason,
        )
        rows.append(
            "\t".join(
                (
                    tool.name,
                    label,
                    reason,
                    "1" if tool.external else "0",
                    "1" if tool.required else "0",
                )
            )
        )
    return "\n".join(rows)


def _tool_plan_tools_from_turn(turn: dict[str, str]) -> list[dict[str, object]]:
    return _tool_plan_tools_from_state(str(turn.get("tool_plan_tools", "")))


def _tool_plan_tools_from_state(value: str) -> list[dict[str, object]]:
    tools: list[dict[str, object]] = []
    for line in str(value).splitlines():
        parts = line.split("\t")
        if len(parts) != 5:
            continue
        name, label, reason, external, required = parts
        tools.append(
            {
                "name": name,
                "label": label,
                "reason": reason,
                "external": external == "1",
                "required": required == "1",
            }
        )
    return tools


def _inline_sections_html(sections: tuple[tuple[str, str], ...]) -> str:
    blocks = "".join(
        (
            '<section class="smai-copilot-inline-section">'
            f"<span>{html.escape(title)}</span>"
            f"{body}"
            "</section>"
        )
        for title, body in sections
        if body
    )
    if not blocks:
        return ""
    return f'<div class="smai-copilot-inline-sections">{blocks}</div>'


def _conversation_answer(
    *,
    intent: CopilotIntent,
    question: str,
    response: AssistantResponse,
) -> str:
    if response.response_source == "llm":
        body = _safe_response_body(response.answer, intent=intent)
        if body:
            return body
    if intent == "concept_explanation":
        body = _safe_response_body(response.answer, intent=intent)
        return body or _concept_explanation_answer(question)
    if intent == "broad_discovery":
        body = _safe_response_body(response.answer, intent=intent)
        return body or _broad_discovery_answer()
    if intent in {"free_chat", "identity", "capability_help"}:
        if (
            _is_simple_greeting(question)
            and not _is_identity_question(question)
            and not _is_capability_question(question)
        ):
            return _fallback_free_chat_answer(question, greeting=True)
        body = _safe_response_body(response.answer, intent=intent)
        if body:
            return body
        return _fallback_free_chat_answer(question)
    if intent == "app_help" and response.response_source not in {"gateway", "llm"}:
        return (
            "SMAIは、目的別に画面を使い分けると分かりやすいです。"
            "銘柄を深掘りするなら「銘柄コックピット」、候補を探すなら「銘柄ランキング」、"
            "市場全体を見るなら「投資レーダー」を使います。"
            "迷ったら、気になる銘柄名を入れて「何を見ればいい？」と聞いてください。"
        )
    lead = {
        "app_help": "はい。SMAIは目的別に画面を使い分けると分かりやすいです。",
        "stock_summary": "まず、この銘柄で確認する材料を短く整理します。",
        "forecast_risk_compare": (
            "AI予測とリスクを分けて確認します。AI予測の方向感と、"
            "下振れ警戒のバランスを見るのがポイントです。"
        ),
        "news_materials": (
            "ニュース材料は、取得済みの材料と、" "まだ未確認の材料を分けて整理します。"
        ),
        "decision_report_draft": (
            "Decision Reportに残す前提で、確認済み材料、" "強気・弱気材料、未確認事項を分けます。"
        ),
        "free_chat": "はい。分かる範囲で短く整理します。",
    }[intent]
    body = _safe_response_body(response.answer, intent=intent)
    if response.response_source in {"gateway", "llm"} and body:
        return body
    if not body or body.startswith(lead):
        return lead
    return f"{lead}\n\n{body}"


def _fallback_free_chat_answer(question: str, *, greeting: bool = False) -> str:
    if greeting:
        if _is_wellbeing_question(question):
            return (
                "こんにちは。元気です。SMAIナビとして、銘柄の確認材料やAI予測、"
                "ニュースの見方を短く整理できます。"
            )
        return (
            "こんにちは。SMAIナビです。SMAIの使い方、銘柄の確認材料、"
            "AI予測やニュースの見方を短く整理できます。"
        )
    topic = str(question or "").strip()
    if _is_identity_question(topic):
        user_name = _user_name_from_introduction(topic)
        greeting_line = f"{user_name}さん、こんにちは。" if user_name else "こんにちは。"
        return (
            f"{greeting_line}私はSMAIナビです。Smart Market AIの中で、銘柄の見方、AI予測、ニュース、"
            "根拠資料の確認ポイントを整理するお手伝いをします。"
        )
    if _is_capability_question(topic):
        return (
            "SMAIナビでは、SMAIの使い方、銘柄の確認順、AI予測とリスクの見比べ方、"
            "ニュース材料の整理をお手伝いできます。"
            "迷ったときは「この銘柄で最初に見る材料は？」のように聞いてください。"
        )
    if topic:
        return (
            f"「{topic[:40]}」について、SMAIで確認する観点を整理します。"
            "価格・AI予測・ニュース・根拠資料を分けて見て、最後に不足している材料を確認すると判断しやすいです。"
        )
    return (
        "SMAIで確認したいことを、画面名や銘柄名と一緒に送ってください。"
        "見ている材料、注意点、次に確認することの順に整理します。"
    )


def _concept_explanation_answer(question: str) -> str:
    normalized = str(question or "").lower()
    if "セクター" in normalized:
        return (
            "セクターとは、企業を業種や事業領域ごとに分けた分類です。"
            "たとえば、金融、半導体、医薬品、通信、エネルギーなどがあります。\n\n"
            "SMAIでは、ニュースやランキングを見るときに、どの分野に材料が出ているか、"
            "同じ業種の中で銘柄ごとの違いがあるかを整理するために使います。"
        )
    if "per" in normalized:
        return (
            "PERは、株価が1株あたり利益の何倍まで評価されているかを見る指標です。"
            "単独で割安・割高を決めず、同業他社や利益の安定性とあわせて確認します。"
        )
    if "pbr" in normalized:
        return (
            "PBRは、株価が1株あたり純資産の何倍かを見る指標です。"
            "業種差が大きいため、SMAIでは同業比較やROEなどと組み合わせて確認します。"
        )
    if "roe" in normalized:
        return (
            "ROEは、株主資本を使ってどれだけ利益を生み出したかを見る指標です。"
            "高低だけでなく、一時要因や財務リスクもあわせて確認します。"
        )
    if "etf" in normalized:
        return (
            "ETFは、株式市場で売買できる投資信託です。指数連動型などがあり、"
            "SMAIでは個別株とは分けて、連動対象、経費率、値動きの特徴を確認します。"
        )
    return "用語の意味と、SMAIの画面でどう使うかを分けて説明します。"


def _broad_discovery_answer() -> str:
    return (
        "ざっくり候補を探す相談ですね。上がる銘柄を断定するのではなく、"
        "まず市場テーマとセクターを分けて確認するのがよさそうです。\n\n"
        "確認候補は、半導体・AI、金融、防衛・インフラ、高配当・通信などです。"
        "それぞれ決算、設備投資、金利、政策、ニュースの鮮度を確認してください。\n\n"
        "具体的な銘柄候補まで見たい場合は、ランキングで条件を絞って比較できます。"
    )


def _user_name_from_introduction(question: str) -> str | None:
    marker = "私の名前は"
    if marker not in question:
        return None
    candidate = question.split(marker, 1)[1].strip(" 　。！!？?")
    if candidate.endswith("です"):
        candidate = candidate[:-2].strip()
    return candidate[:20] or None


def _intent_fallback_answer(*, intent: CopilotIntent, question: str) -> str:
    if intent == "concept_explanation":
        return _concept_explanation_answer(question)
    if intent == "broad_discovery":
        return _broad_discovery_answer()
    if intent in {"free_chat", "identity", "capability_help"}:
        return _fallback_free_chat_answer(question, greeting=_is_simple_greeting(question))
    if intent == "app_help":
        return (
            "SMAIは、目的別に画面を使い分けると分かりやすいです。"
            "銘柄を深掘りするなら「銘柄コックピット」、候補を探すなら「銘柄ランキング」、"
            "市場全体を見るなら「投資レーダー」を使います。"
            "迷ったら、気になる銘柄名を入れて「何を見ればいい？」と聞いてください。"
        )
    return "確認できる材料を整理しました。未確認の材料がある場合は、追加取得後にもう一度見直してください。"


def _item_limit_for_intent(intent: CopilotIntent) -> int:
    if _is_llm_micro_intent(intent):
        return 1
    return 3


def _is_identity_question(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "あなたの名前",
            "あなたのなまえ",
            "あなたは誰",
            "あなたはだれ",
            "君の名前",
            "君は誰",
            "名前は",
            "名前を教えて",
            "お名前",
            "なまえ",
            "だれ",
            "誰",
            "who are you",
            "your name",
        )
    )


def _is_capability_question(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "何ができる",
            "なにができる",
            "できること",
            "何を相談",
            "何を聞ける",
            "どう使える",
            "どんなことができる",
            "help",
            "capability",
        )
    )


def _is_wellbeing_question(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    return any(
        phrase in normalized
        for phrase in (
            "元気",
            "げんき",
            "調子",
            "ちょうし",
            "how are you",
            "how's it going",
        )
    )


def _is_simple_greeting(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    if normalized in {
        "こんにちは",
        "こんばんは",
        "おはよう",
        "おはようございます",
        "hello",
        "hi",
    }:
        return True
    return any(
        normalized.startswith(prefix)
        for prefix in (
            "こんにちは。",
            "こんにちは、",
            "こんばんは。",
            "こんばんは、",
            "hello ",
            "hi ",
        )
    )


def _safe_response_body(answer: str, *, intent: CopilotIntent | None = None) -> str:
    text = sanitize_presentation_text(str(answer or "").strip())
    blocked_markers = (
        "SMAI Assistant intent:",
        "Tool results already checked",
        "Response instruction:",
        "Boundary:",
        "First, I need",
        "I need to",
        "I should",
        "The answer should",
        "The tool says",
        "We are given",
        "We must return",
        "Final decision:",
        "<think>",
        "</think>",
        "Let me",
        "Wait,",
        "JSON fields",
        "The response should",
    )
    if any(marker in text for marker in blocked_markers):
        return ""
    lines = [line.strip() for line in text.splitlines()]
    filtered: list[str] = []
    repetitive_markers = (
        "売買推奨",
        "投資判断アシスタント",
        "投資判断を補助",
        "判断材料の整理",
        "SMAI Assistant",
        "本レポート",
    )
    for line in lines:
        if (
            intent is not None
            and _is_llm_micro_intent(intent)
            and any(marker in line for marker in repetitive_markers)
        ):
            continue
        filtered.append(line)
    cleaned = "\n".join(filtered).strip()
    if not cleaned:
        return ""
    compact = cleaned.replace("\n", "")
    if intent is not None and _is_llm_micro_intent(intent):
        weak_phrases = (
            "分かる範囲で短く整理します",
            "SMAIの画面、確認材料、注意点について聞いてください",
            "確認材料について聞いてください",
            "確認材料を整理します",
        )
        if len(compact) < 40 or any(phrase in cleaned for phrase in weak_phrases):
            return ""
    if intent in {
        "app_help",
        "forecast_risk_compare",
        "stock_summary",
        "news_materials",
    }:
        if len(compact) < 55:
            return ""
    return cleaned


def _execution_result_html(turn: dict[str, str]) -> str:
    executed = sanitize_presentation_items(_split_lines(turn.get("executed_checks", "")), limit=6)
    if not executed:
        return ""
    items = "".join(f"<li>{html.escape(item)}</li>" for item in executed[:6])
    return (
        '<section class="smai-copilot-tool-result">'
        "<span>実行した確認</span>"
        f"<ul>{items}</ul>"
        "</section>"
    )


def _assistant_action_results_panel_html(turn: dict[str, str]) -> str:
    cards: list[str] = []
    for item in _assistant_action_results_from_state(str(turn.get("assistant_action_results", ""))):
        try:
            cards.append(assistant_action_result_card_html(item))
        except ValueError:
            continue
    return "".join(cards)


def _response_meta_html(turn: dict[str, str]) -> str:
    meta = str(turn.get("response_meta", "")).strip()
    if not meta:
        meta = "SMAI通常回答 / fallback"
    details = [
        ("mode", str(turn.get("conversation_mode", "")).strip()),
        ("source", str(turn.get("response_source", "")).strip()),
        ("model", str(turn.get("model", "")).strip()),
        ("provider", str(turn.get("provider", "")).strip()),
        ("profile", str(turn.get("profile", "")).strip()),
        ("fallback", str(turn.get("fallback_reason", "")).strip()),
        ("gateway_error", str(turn.get("gateway_error_type", "")).strip()),
        ("gateway_message", str(turn.get("gateway_error_message", "")).strip()),
        ("gateway_url", str(turn.get("gateway_url", "")).strip()),
        ("http_status", str(turn.get("http_status", "")).strip()),
        ("provider_error", str(turn.get("provider_error_type", "")).strip()),
        ("provider_message", str(turn.get("provider_error_message", "")).strip()),
        ("latency", str(turn.get("latency_ms", "")).strip()),
        ("request", str(turn.get("request_id", "")).strip()),
        ("planner", str(turn.get("assistant_planner_source", "")).strip()),
        ("planner_type", str(turn.get("assistant_planner_used_plan_type", "")).strip()),
        (
            "planner_fallback",
            str(turn.get("assistant_planner_fallback_reason", "")).strip(),
        ),
        ("planner_status", str(turn.get("assistant_planner_gateway_status", "")).strip()),
        ("planner_provider", str(turn.get("assistant_planner_provider", "")).strip()),
        ("planner_model", str(turn.get("assistant_planner_model", "")).strip()),
        ("planner_profile", str(turn.get("assistant_planner_profile", "")).strip()),
        ("planner_request", str(turn.get("assistant_planner_request_id", "")).strip()),
    ]
    items = "".join(
        f"<li><span>{html.escape(label)}</span><b>{html.escape(value)}</b></li>"
        for label, value in details
        if value
    )
    return (
        '<details class="smai-copilot-response-meta">'
        "<summary>技術情報を表示</summary>"
        f"<p>{html.escape(meta)}</p>"
        f"<ul>{items}</ul>"
        "</details>"
    )


def _assistant_action_links_html(turn: dict[str, str]) -> str:
    actions = _actions_for_turn(turn)
    plain_text = copilot_turn_plain_text(turn)
    markdown = copilot_turn_markdown(turn)
    action_links = "".join(
        _download_action_link_html(
            label=label,
            data=plain_text if kind == "copy" else markdown,
            file_name=(
                _memo_filename(turn, extension="txt") if kind == "copy" else _memo_filename(turn)
            ),
            mime="text/plain" if kind == "copy" else "text/markdown",
        )
        for label, kind in actions
    )
    if not action_links:
        return ""
    return (
        '<div class="smai-copilot-actions-row smai-copilot-actions-row--inside">'
        f"{action_links}"
        "</div>"
    )


def _actions_for_turn(turn: dict[str, str]) -> tuple[tuple[str, str], ...]:
    intent = _normalize_intent(turn.get("intent", ""))
    if _is_llm_micro_intent(intent):
        return (("コピー", "copy"),)
    return (
        ("コピー", "copy"),
        ("Markdownで保存", "memo"),
    )


def _download_action_link_html(*, label: str, data: str, file_name: str, mime: str) -> str:
    encoded = base64.b64encode(data.encode("utf-8")).decode("ascii")
    return (
        '<a class="smai-copilot-action-link" '
        f'href="data:{html.escape(mime)};charset=utf-8;base64,{encoded}" '
        f'download="{html.escape(file_name)}">'
        f"{html.escape(label)}"
        "</a>"
    )


def copilot_turn_plain_text(turn: dict[str, str]) -> str:
    intent = _normalize_intent(turn.get("intent", ""))
    lines = [
        f"相談モード: {turn.get('intent_label', '')}",
        f"対象: {turn.get('context_label', '')}",
        f"質問: {turn.get('question', '')}",
        "",
        sanitize_presentation_text(str(turn.get("answer", "")).strip()),
    ]
    executed = sanitize_presentation_items(_split_lines(turn.get("executed_checks", "")), limit=6)
    if executed:
        lines.extend(["", "実行した確認:"])
        lines.extend(f"- {item}" for item in executed)
    if _is_llm_micro_intent(intent):
        return "\n".join(line for line in lines if line != "").strip() + "\n"
    for title, key in zip(
        _section_titles_for_intent(intent),
        ("reasons", "cautions", "next_checkpoints", "memo_points"),
    ):
        items = sanitize_presentation_items(_split_lines(turn.get(key, "")), limit=3)
        if not items:
            continue
        lines.extend(["", f"{title}:"])
        lines.extend(f"- {item}" for item in items)
    return "\n".join(lines).strip() + "\n"


def copilot_turn_markdown(turn: dict[str, str]) -> str:
    report_markdown = str(turn.get("decision_report_markdown", "")).strip()
    if report_markdown:
        return report_markdown + ("\n" if not report_markdown.endswith("\n") else "")
    context_label = str(turn.get("context_label", "")).strip()
    intent_label = str(turn.get("intent_label", "")).strip()
    created_at = str(turn.get("created_at", "")).strip() or datetime.now().strftime(
        "%Y-%m-%d %H:%M"
    )
    answer = sanitize_presentation_text(str(turn.get("answer", "")).strip())
    reasons = _markdown_list(
        sanitize_presentation_items(_split_lines(turn.get("reasons", "")), limit=3)
    )
    cautions = _markdown_list(
        sanitize_presentation_items(_split_lines(turn.get("cautions", "")), limit=3)
    )
    checkpoints = _markdown_list(
        sanitize_presentation_items(_split_lines(turn.get("next_checkpoints", "")), limit=3)
    )
    memo_points = _markdown_list(
        sanitize_presentation_items(_split_lines(turn.get("memo_points", "")), limit=3)
    )
    executed = _markdown_list(
        sanitize_presentation_items(_split_lines(turn.get("executed_checks", "")), limit=6)
    )
    return (
        "# SMAIアシスタント メモ\n\n"
        "## 対象\n"
        "- 銘柄: 未指定\n"
        f"- 画面: {context_label or 'SMAIアシスタント'}\n"
        f"- 分析モード: {intent_label or '自由相談'}\n"
        f"- 作成日時: {created_at}\n\n"
        "## 実行した確認\n"
        f"{executed}\n\n"
        "## 確認した材料\n"
        f"{reasons}\n\n"
        "## 強気材料\n"
        f"{memo_points}\n\n"
        "## 弱気材料\n"
        f"{cautions}\n\n"
        "## 未確認事項\n"
        f"{cautions}\n\n"
        "## 次に確認すること\n"
        f"{checkpoints}\n\n"
        "## SMAIナビの整理\n"
        f"- {answer or '未入力'}\n\n"
        "---\n\n"
        "本レポートは投資判断を補助するための整理メモであり、"
        "売買を推奨するものではありません。\n"
    )


def _summary_html(context: SmaiAssistantContext) -> str:
    items = [f"{key}: {value}" for key, value in context.summary.items()]
    return _list_html(items or [context.lead])


def _gateway_question(
    *,
    question: str,
    intent: CopilotIntent,
    prompt_instruction: str,
    tool_summaries: list[str],
) -> str:
    if _is_llm_micro_intent(intent):
        return question.strip()[:500]
    tool_block = "\n".join(f"- {summary}" for summary in tool_summaries) or "- なし"
    return (
        f"SMAI Assistant intent: {intent}\n"
        f"User question: {question.strip()}\n"
        f"Response instruction: {prompt_instruction}\n"
        f"Structured research context already checked by SMAI:\n{tool_block}\n"
        "Agent behavior: You are the primary AI chat assistant. Read the user's intent, "
        "use confirmed materials as the answer basis, explicitly separate missing materials, "
        "and ask for the next missing material when the checked results are insufficient.\n"
        "Tone: SMAIナビとして、短く自然な日本語で答える。固定テンプレート、長い自己紹介、"
        "毎回の免責文は避ける。\n"
        "Boundary: 売買推奨、スコア変更、ランキング変更、予測値の変更はしない。"
    )


def _response_meta_label(*, response: AssistantResponse, intent: CopilotIntent) -> str:
    intent_label = intent
    if response.response_source in ("gateway", "llm"):
        model = response.model or "LLM"
        provider = response.provider or "Gateway"
        profile = response.profile or "assistant_profile"
        latency = " / " + str(response.latency_ms) + "ms" if response.latency_ms is not None else ""
        return model + " / live / " + profile + " / " + provider + " / " + intent_label + latency
    if response.response_source in ("fallback", "deterministic_fallback"):
        reason = response.fallback_reason or "gateway_unavailable"
        model = " / " + response.model if response.model else ""
        duration = ""
        if response.latency_ms is not None:
            duration = " / " + str(response.latency_ms) + "ms"
        elif response.timeout_sec is not None:
            duration = " / " + str(response.timeout_sec) + "s"
        return "SMAI通常回答 / fallback: " + reason + model + " / " + intent_label + duration
    return "SMAI通常回答 / deterministic / " + intent_label


def _render_material_status(context: SmaiAssistantContext) -> None:
    status = _material_status(context)
    chips = "".join(
        f'<span class="smai-copilot-chip">{html.escape(label)}: {html.escape(value)}</span>'
        for label, value in status
    )
    st.markdown(
        '<div class="smai-copilot-material-status">'
        "<span>参照中の材料</span>"
        f'<div class="smai-copilot-chip-row">{chips}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _material_status(context: SmaiAssistantContext) -> tuple[tuple[str, str], ...]:
    text = " ".join(
        [
            context.context_id,
            context.page_key,
            context.section_key,
            context.section_label,
            " ".join(str(value) for value in context.summary.values()),
        ]
    ).lower()
    has_news = any(term in text for term in ("news", "ニュース", "開示", "research", "rag"))
    has_research = any(term in text for term in ("research", "rag", "根拠", "材料分析"))
    has_forecast = any(term in text for term in ("forecast", "予測", "ai予測", "cockpit"))
    has_price = any(term in text for term in ("価格", "chart", "cockpit", "ranking"))
    return (
        ("価格", "あり" if has_price else "なし"),
        ("AI予測", "あり" if has_forecast else "なし"),
        ("ニュース", "あり" if has_news else "なし"),
        ("Research Evidence", "あり" if has_research else "なし"),
        ("Decision Report", "下書き可"),
        ("LLM", "Gateway優先 / fallbackあり"),
    )


def _material_status_summary(context: SmaiAssistantContext) -> str:
    status = _material_status(context)
    visible = [(label, value) for label, value in status if label != "LLM"]
    return "参照材料: " + " / ".join(f"{label}={value}" for label, value in visible)


def _active_context_from_history(
    history: list[dict[str, str]],
    context_by_id: dict[str, SmaiAssistantContext],
) -> SmaiAssistantContext:
    if history:
        context = context_by_id.get(str(history[-1].get("context_id", "")))
        if context is not None:
            return context
    preset = _preset_for_intent(_active_intent())
    return context_by_id.get(preset.context_id) or next(iter(context_by_id.values()))


def _active_intent() -> CopilotIntent:
    return _normalize_intent(st.session_state.get(COPILOT_ACTIVE_INTENT_STATE_KEY, "free_chat"))


def _intent_for_research_plan(research_intent: object) -> CopilotIntent:
    mapping: dict[str, CopilotIntent] = {
        "stock_forward_view": "stock_summary",
        "news_research": "news_materials",
        "investment_material_scan": "news_materials",
        "decision_report_request": "decision_report_draft",
        "theme_stock_discovery": "stock_summary",
        "ranking_query": "stock_summary",
        "market_radar_query": "news_materials",
    }
    return mapping.get(str(research_intent), "stock_summary")


def _context_id_for_intent(intent: CopilotIntent) -> str:
    return _preset_for_intent(intent).context_id


def _intent_from_message(message: str, *, fallback: CopilotIntent) -> CopilotIntent:
    if _is_identity_question(message):
        return "identity"
    if _is_capability_question(message):
        return "capability_help"
    if _is_simple_greeting(message):
        return "free_chat"
    decision = detect_assistant_intent(message)
    mapping: dict[str, CopilotIntent] = {
        "smai_how_to_use": "app_help",
        "app_help": "app_help",
        "self_introduction": "identity",
        "identity": "identity",
        "capability_help": "capability_help",
        "stock_analysis": "stock_summary",
        "stock_candidate_search": "stock_summary",
        "stock_summary": "stock_summary",
        "forecast_check": "forecast_risk_compare",
        "forecast_risk_compare": "forecast_risk_compare",
        "chart_check": "stock_summary",
        "news_lookup": "news_materials",
        "news_materials": "news_materials",
        "rag_search": "news_materials",
        "report_creation": "decision_report_draft",
        "decision_report_draft": "decision_report_draft",
        "file_export": "decision_report_draft",
        "concept_explanation": "concept_explanation",
        "theme_or_sector_discovery": "broad_discovery",
        "market_overview": "broad_discovery",
        "smalltalk": "free_chat",
        "free_chat": fallback,
        "unknown_or_ambiguous": "free_chat",
        "unknown": fallback,
    }
    return mapping.get(decision.intent, fallback)


def _normalize_intent(value: object) -> CopilotIntent:
    text = str(value or "").strip()
    valid = {
        "app_help",
        "identity",
        "capability_help",
        "stock_summary",
        "forecast_risk_compare",
        "news_materials",
        "decision_report_draft",
        "free_chat",
        "concept_explanation",
        "broad_discovery",
    }
    return text if text in valid else "free_chat"  # type: ignore[return-value]


def _is_llm_micro_intent(intent: CopilotIntent) -> bool:
    return intent in {
        "free_chat",
        "identity",
        "app_help",
        "capability_help",
        "concept_explanation",
        "broad_discovery",
    }


def _preset_for_intent(intent: CopilotIntent) -> CopilotConversationPreset:
    if intent == "concept_explanation":
        return CopilotConversationPreset(
            intent="free_chat",
            label="用語を知りたい",
            description="用語の意味とSMAIでの使われ方を説明します。",
            context_id="copilot_app_help",
            default_question="用語の意味を教えてください。",
            prompt_instruction="用語を平易に説明し、SMAIでの使われ方だけを短く補足してください。",
        )
    if intent == "broad_discovery":
        return CopilotConversationPreset(
            intent="free_chat",
            label="テーマ・セクター探索",
            description="特定銘柄を決めずに確認候補を整理します。",
            context_id="copilot_news_overview",
            default_question="注目テーマとセクターの確認観点を整理してください。",
            prompt_instruction="売買を断定せず、テーマ、セクター、確認材料を整理してください。",
        )
    for preset in copilot_conversation_presets():
        if preset.intent == intent:
            return preset
    return copilot_conversation_presets()[-1]


def _section_titles_for_intent(intent: CopilotIntent) -> tuple[str, ...]:
    return {
        "app_help": ("目的別の使い方", "注意点", "まずおすすめ"),
        "stock_summary": ("見る材料", "注意点", "次に確認"),
        "forecast_risk_compare": (
            "予測側の見方",
            "リスク側の見方",
            "確認ポイント",
            "矛盾・温度差",
        ),
        "news_materials": ("強気材料", "弱気材料", "次に見る資料", "未確認材料"),
        "decision_report_draft": ("確認した材料", "未確認事項", "次回確認", "メモ"),
        "free_chat": ("SMAIナビの見方", "注意点", "次にできること"),
        "identity": ("SMAIナビの見方", "注意点", "次にできること"),
        "capability_help": ("SMAIナビの使い方", "注意点", "次にできること"),
        "concept_explanation": ("意味", "SMAIでの使い方", "補足"),
        "broad_discovery": ("確認候補", "見る材料", "注意点"),
    }[intent]


def _memo_points_for_intent(intent: CopilotIntent, response: AssistantResponse) -> list[str]:
    if intent == "forecast_risk_compare":
        return ["予測とリスクの向きが一致しているか、期間と根拠をそろえて確認します。"]
    if intent == "news_materials":
        return ["未確認材料は出典、日付、対象銘柄への影響範囲を分けて確認します。"]
    if intent == "decision_report_draft":
        return [response.answer]
    return []


def _memo_filename(turn: dict[str, str], *, extension: str = "md") -> str:
    symbol = _safe_filename_part(str(turn.get("symbol", "")).strip())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    prefix = f"{symbol}_decision_memo" if symbol else "smai_assistant_memo"
    return f"{prefix}_{timestamp}.{extension}"


def _safe_filename_part(value: str) -> str:
    return "".join(ch for ch in value if ch.isascii() and (ch.isalnum() or ch in "-_")).strip("_-")


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _block_html(title: str, body: str) -> str:
    if not body:
        return ""
    return (
        '<section class="smai-copilot-answer-block">'
        f"<span>{html.escape(title)}</span>"
        f"{body}"
        "</section>"
    )


def _list_html(items: list[str]) -> str:
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items[:4]) + "</ul>"


def _markdown_list(items: list[str]) -> str:
    if not items:
        return "-"
    return "\n".join(f"- {item}" for item in items)
