from __future__ import annotations

import base64
import html
import os
import time
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Literal, cast
from uuid import uuid4

import httpx
import streamlit as st

from backend.assistant import (
    AssistantMessage,
    AssistantResearchToolPlan,
    AssistantResponse,
    HttpAssistantGatewayClient,
    build_assistant_research_tool_plan,
    detect_assistant_intent,
    execute_assistant_tool_plan,
    route_assistant_conversation_mode,
)
from backend.assistant.response_sanitizer import (
    sanitize_presentation_items,
    sanitize_presentation_text,
)
from backend.core.config import AssistantGatewayConfig, Settings, get_settings
from ui.components.assistant import (
    SmaiAssistantContext,
    assistant_context_to_report_context,
    assistant_response_for_context,
)
from ui.components.mascot import (
    MASCOT_NAVI_CHAT_ASSET,
    MASCOT_THUMB_ASSET,
    _asset_data_uri,
)

COPILOT_CHAT_HISTORY_STATE_KEY = "smai_copilot_chat_history"
COPILOT_CONVERSATION_ID_STATE_KEY = "smai_copilot_conversation_id"
COPILOT_ACTIVE_INTENT_STATE_KEY = "smai_copilot_active_intent"
COPILOT_PENDING_STREAM_STATE_KEY = "smai_copilot_pending_stream_turn_id"
COPILOT_PENDING_REQUEST_STATE_KEY = "smai_copilot_pending_request"
COPILOT_SUPPRESS_SUBMIT_STATE_KEY = "smai_copilot_suppress_next_submit"
COPILOT_LLM_PROFILE_STATE_KEY = "smai_copilot_llm_profile"
COPILOT_LLM_MODEL_STATE_KEY = "smai_copilot_llm_model"
COPILOT_GATEWAY_DIAGNOSTIC_STATE_KEY = "smai_copilot_gateway_diagnostic"
COPILOT_GATEWAY_DIAGNOSTIC_TTL_SECONDS = 20.0
COPILOT_STREAM_DELAY_SECONDS = 0.16
COPILOT_STREAM_MAX_CHUNKS = 8
COPILOT_PENDING_STEP_DELAY_SECONDS = 0.34

COPILOT_LLM_MODEL_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("notebook_dev", "qwen3:1.7b", "ノートPC / 軽量開発"),
    ("desktop_fast", "qwen3:8b", "デスクトップ通常 / Copilot・要約"),
    ("desktop_analysis", "qwen3:14b", "デスクトップ高精度 / 銘柄分析・RAG"),
    ("desktop_heavy", "qwen3:30b", "高負荷分析 / 週次・月次レポート"),
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
]


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
            return "Gateway未接続"
        if self.readiness_status == "gateway_timeout":
            return "Gateway応答待ち"
        if self.readiness_status == "provider_unavailable":
            return "Ollama未接続"
        if self.readiness_status == "model_missing":
            return "モデル未取得"
        if self.readiness_status == "gateway_error":
            return "Gateway確認エラー"
        return "準備確認中"

    @property
    def readiness_detail(self) -> str:
        if not self.enabled:
            return "deterministic fallback"
        if self.readiness_message:
            return self.readiness_message
        if self.readiness_status == "ready":
            return f"{self.model} 利用可能"
        return "Gateway状態を確認中"


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
    return _with_cached_gateway_diagnostic(runtime_config)


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
    model = str(st.session_state.get(COPILOT_LLM_MODEL_STATE_KEY, default_model))
    return profile, model


def _model_for_profile(profile: str) -> str:
    for option_profile, option_model, _ in COPILOT_LLM_MODEL_OPTIONS:
        if option_profile == profile:
            return option_model
    return "qwen3:1.7b"


def _render_model_selector(
    runtime_config: CopilotGatewayRuntimeConfig,
) -> CopilotGatewayRuntimeConfig:
    labels = [
        f"{profile} / {model} - {purpose}" for profile, model, purpose in COPILOT_LLM_MODEL_OPTIONS
    ]
    current_index = next(
        (
            index
            for index, (profile, model, _) in enumerate(COPILOT_LLM_MODEL_OPTIONS)
            if profile == runtime_config.profile and model == runtime_config.model
        ),
        0,
    )
    with st.popover(runtime_config.model, use_container_width=True):
        st.caption("LLM model")
        selected_label = st.radio(
            "使用モデル",
            labels,
            index=current_index,
            key="smai_copilot_llm_model_radio",
        )
        selected_index = labels.index(selected_label)
        profile, model, purpose = COPILOT_LLM_MODEL_OPTIONS[selected_index]
        st.caption(f"現在: Ollama / {model} / {profile}")
        st.caption(purpose)
        st.session_state[COPILOT_LLM_PROFILE_STATE_KEY] = profile
        st.session_state[COPILOT_LLM_MODEL_STATE_KEY] = model
        return CopilotGatewayRuntimeConfig(
            enabled=runtime_config.enabled,
            base_url=runtime_config.base_url,
            timeout_seconds=runtime_config.timeout_seconds,
            context_answer_path=runtime_config.context_answer_path,
            execution_mode=runtime_config.execution_mode,
            environment_profile=runtime_config.environment_profile,
            provider=runtime_config.provider,
            model=model,
            profile=profile,
        )
    return runtime_config


def _render_chat_composer(
    runtime_config: CopilotGatewayRuntimeConfig,
) -> tuple[str | None, CopilotGatewayRuntimeConfig]:
    st.markdown(
        '<div class="smai-copilot-composer-toolbar" aria-label="SMAI chat composer">',
        unsafe_allow_html=True,
    )
    model_col, input_col = st.columns([0.22, 0.78])
    with model_col:
        selected = _render_model_selector(runtime_config)
    submitted = False
    prompt = ""
    with input_col:
        with st.form("smai_copilot_composer_form", clear_on_submit=True):
            text_col, send_col = st.columns([0.84, 0.16])
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
        st.caption(
            f"LLM: {selected.provider} / {selected.model} / {selected.profile}"
            if selected.enabled
            else "LLM: deterministic fallback"
        )
    st.markdown("</div>", unsafe_allow_html=True)
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
) -> CopilotGatewayRuntimeConfig:
    if not runtime_config.enabled:
        return runtime_config
    if os.getenv("SMAI_SKIP_ASSISTANT_GATEWAY_STATUS_CHECK") == "1":
        return runtime_config

    cache_key = (
        runtime_config.base_url,
        runtime_config.context_answer_path,
        runtime_config.model,
        runtime_config.profile,
    )
    cached = st.session_state.get(COPILOT_GATEWAY_DIAGNOSTIC_STATE_KEY)
    now = time.time()
    if isinstance(cached, dict):
        cached_at = float(cached.get("checked_at", 0.0) or 0.0)
        if (
            cached.get("cache_key") == cache_key
            and now - cached_at < COPILOT_GATEWAY_DIAGNOSTIC_TTL_SECONDS
        ):
            return _runtime_config_from_state(cached.get("runtime_config"))

    diagnosed = _probe_copilot_gateway_runtime(runtime_config)
    st.session_state[COPILOT_GATEWAY_DIAGNOSTIC_STATE_KEY] = {
        "checked_at": now,
        "cache_key": cache_key,
        "runtime_config": _runtime_config_to_state(diagnosed),
    }
    return diagnosed


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
    if _is_llm_micro_intent(intent):
        return _response_meta_html(turn) + _assistant_action_links_html(turn)
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
    return f'<div class="smai-copilot-thread">{rows}</div>'


def render_copilot_workspace_page() -> None:
    contexts = copilot_context_options()
    context_by_id = {context.context_id: context for context in contexts}
    history = _copilot_history()
    runtime_config = copilot_gateway_runtime_config()

    st.markdown(
        _chat_header_html(history_count=len(history), runtime_config=runtime_config),
        unsafe_allow_html=True,
    )
    clear = _render_new_conversation_action()
    _render_material_status(_active_context_from_history(history, context_by_id))

    if clear:
        st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = []
        st.session_state[COPILOT_CONVERSATION_ID_STATE_KEY] = _new_conversation_id()
        st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = "free_chat"
        st.session_state[COPILOT_PENDING_REQUEST_STATE_KEY] = None
        st.session_state[COPILOT_PENDING_STREAM_STATE_KEY] = ""
        st.session_state[COPILOT_SUPPRESS_SUBMIT_STATE_KEY] = False
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
    if _render_tool_plan_actions(
        _copilot_history(),
        context_by_id=context_by_id,
        fallback_context=contexts[0],
        runtime_config=runtime_config,
    ):
        st.rerun()
    suppress_submit = bool(st.session_state.pop(COPILOT_SUPPRESS_SUBMIT_STATE_KEY, False))
    suggestions_placeholder = st.empty()
    with suggestions_placeholder.container():
        suggested = _render_suggestion_buttons(has_history=bool(history))

    if suggested is not None and not suppress_submit:
        context = context_by_id.get(suggested.context_id, contexts[0])
        _queue_copilot_submit(
            context,
            suggested.default_question,
            intent=suggested.intent,
            prompt_instruction=suggested.prompt_instruction,
            visible_question=suggested.label,
            runtime_config=runtime_config,
        )
        suggestions_placeholder.empty()
        _process_queued_copilot_request_inline(
            chat_placeholder=chat_placeholder,
            context_by_id=context_by_id,
            fallback_context=contexts[0],
        )
        history = _copilot_history()

    prompt, runtime_config = _render_chat_composer(runtime_config)

    if prompt and not suppress_submit:
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
        )
        suggestions_placeholder.empty()
        _process_queued_copilot_request_inline(
            chat_placeholder=chat_placeholder,
            context_by_id=context_by_id,
            fallback_context=contexts[0],
        )
        history = _copilot_history()

    st.caption(
        "SMAIアシスタントは判断材料の整理を補助します。売買推奨、スコア変更、"
        "ランキング順位変更は行いません。"
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
        return

    _render_streaming_turn(turns[:pending_index], turns[pending_index], placeholder=placeholder)
    st.session_state[COPILOT_PENDING_STREAM_STATE_KEY] = ""


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
) -> None:
    normalized_question = question.strip()
    if not normalized_question:
        st.warning("質問を入力してください。")
        return
    turn_id = uuid4().hex
    history = _copilot_history()
    history.append(
        _pending_turn(
            turn_id=turn_id,
            context=context,
            visible_question=visible_question,
            intent=intent,
            runtime_config=runtime_config,
        )
    )
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = history
    st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = intent
    st.session_state[COPILOT_PENDING_REQUEST_STATE_KEY] = {
        "turn_id": turn_id,
        "context_id": context.context_id,
        "question": normalized_question,
        "intent": intent,
        "prompt_instruction": prompt_instruction,
        "visible_question": visible_question,
        "runtime_config": _runtime_config_to_state(runtime_config),
    }


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
    )
    st.session_state[COPILOT_SUPPRESS_SUBMIT_STATE_KEY] = True
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
            "approval_reason": research_plan.approval_reason,
            "tool_plan_tools": _tool_plan_tools_state(research_plan),
            "approval_choice": "",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = history
    st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = intent


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
        ("approve", "はい、取得して分析する"),
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

    _queue_copilot_submit(
        context,
        question,
        intent=intent,
        prompt_instruction=_tool_plan_followup_instruction(turn=turn, choice=choice),
        visible_question=label,
        runtime_config=runtime_config,
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
            "answer": "調査を中止しました。必要になったら、銘柄名や見たい材料を指定してもう一度聞いてください。",
            "reasons": "",
            "cautions": "",
            "next_checkpoints": "",
            "memo_points": "",
            "executed_checks": "ユーザーが調査をキャンセル",
            "tool_statuses": "",
            "response_source": "deterministic_fallback",
            "fallback_reason": "research_cancelled",
            "response_meta": "SMAI通常回答 / research_cancelled / free_chat",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    )
    st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = history


def _tool_plan_followup_instruction(*, turn: dict[str, str], choice: str) -> str:
    tools = _tool_plan_tools_from_turn(turn)
    labels = "、".join(str(tool["label"]) for tool in tools) or "取得済み材料"
    if choice == "cached_only":
        return (
            "ユーザーは外部取得を行わず、取得済み情報だけで回答することを選びました。"
            f"対象材料: {labels}。不足している材料は未確認として明示してください。"
            "売買推奨、スコア変更、ランキング変更、予測値変更はしないでください。"
        )
    return (
        "ユーザーはTool Planを承認しました。今回の初期実装では、SMAI側のread-only文脈と"
        "取得済み材料を使って整理し、外部取得が未接続の材料は未確認として明示してください。"
        f"計画された材料: {labels}。売買推奨、スコア変更、ランキング変更、予測値変更はしないでください。"
    )


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
    tool_summaries = [result.summary for result in tool_plan.executed] if tool_plan else []
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
    turn = _turn_from_response(
        context,
        visible_question,
        response,
        intent=intent,
        turn_id=pending_turn_id,
        executed_checks=[
            *([] if _is_llm_micro_intent(intent) else [_material_status_summary(context)]),
            *tool_summaries,
        ],
        tool_statuses=[
            f"{result.name}: {result.status}"
            for result in (tool_plan.executed if tool_plan else ())
        ],
    )
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
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


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
) -> str:
    runtime_config = runtime_config or CopilotGatewayRuntimeConfig(
        enabled=True,
        base_url="http://127.0.0.1:8088",
        timeout_seconds=90.0,
        context_answer_path="/api/v1/context-answer",
        execution_mode="auto",
        environment_profile="notebook",
    )
    status_label = runtime_config.readiness_label
    if history_count and runtime_config.readiness_status == "ready":
        status_label = "確認中"
    status_detail = runtime_config.readiness_detail
    if history_count and runtime_config.readiness_status in {"ready", "unchecked"}:
        status_detail = f"会話 {history_count}件"
    llm_label = (
        f"LLM: {runtime_config.provider} / {runtime_config.model} / {runtime_config.profile}"
        if runtime_config.enabled
        else "LLM: deterministic fallback"
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
        '<div class="smai-copilot-statusbar">'
        '<span class="smai-copilot-chat-status-dot"></span>'
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
    subject = plan.symbol or plan.symbol_query or "この相談"
    return (
        f"{subject}について、確認する材料の計画を作りました。"
        "外部情報の取得が含まれる場合があるため、実行前に確認します。"
    )


def _tool_plan_detail_html(turn: dict[str, str]) -> str:
    tools = _tool_plan_tools_from_turn(turn)
    subject = str(turn.get("symbol", "") or turn.get("symbol_query", "") or "未指定").strip()
    approval = str(turn.get("approval_reason", "")).strip()
    reason = str(turn.get("conversation_reason", "")).strip()
    approval_choice = str(turn.get("approval_choice", "")).strip()
    items = "".join(
        (
            "<li>"
            f'<b>{html.escape(str(tool["label"]))}</b>'
            f'<span>{html.escape(str(tool["reason"]))}</span>'
            f'<small>{"外部取得あり" if bool(tool["external"]) else "SMAI内確認"}'
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
        f"<p>{html.escape(reason)}</p>"
        f"<p>{html.escape(approval)}</p>"
        f"<ul>{items}</ul>"
        f"{choice_html}"
        "</section>"
    )


def _tool_plan_tools_state(plan: AssistantResearchToolPlan) -> str:
    return "\n".join(
        "\t".join(
            (
                tool.name,
                tool.label,
                tool.reason,
                "1" if tool.external else "0",
                "1" if tool.required else "0",
            )
        )
        for tool in plan.tools
    )


def _tool_plan_tools_from_turn(turn: dict[str, str]) -> list[dict[str, object]]:
    tools: list[dict[str, object]] = []
    for line in str(turn.get("tool_plan_tools", "")).splitlines():
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
    if intent in {"free_chat", "identity", "capability_help"}:
        if _is_simple_greeting(question):
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
        return (
            "こんにちは。SMAIナビです。SMAIの使い方、銘柄の確認材料、"
            "AI予測やニュースの見方を短く整理できます。"
        )
    topic = str(question or "").strip()
    if _is_identity_question(topic):
        return (
            "私はSMAIナビです。Smart Market AIの中で、銘柄の見方、AI予測、ニュース、"
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


def _intent_fallback_answer(*, intent: CopilotIntent, question: str) -> str:
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


def _response_meta_html(turn: dict[str, str]) -> str:
    meta = str(turn.get("response_meta", "")).strip()
    if not meta:
        meta = "SMAI通常回答 / fallback"
    details = [
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
    if intent == "decision_report_draft":
        return (
            ("コピー", "copy"),
            ("Markdownで保存", "memo"),
            ("Decision Reportに追加", "report"),
        )
    return (
        ("コピー", "copy"),
        ("Markdownで保存", "memo"),
        ("Decision Reportに追加", "report"),
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
        f"Tool results already checked by SMAI:\n{tool_block}\n"
        "Agent behavior: You are the primary AI chat assistant. Read the user's intent, "
        "use the SMAI tool results only when they help answer the question, and ask for "
        "the next missing material when the checked results are insufficient.\n"
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
        "app_help": "app_help",
        "identity": "identity",
        "capability_help": "capability_help",
        "stock_summary": "stock_summary",
        "forecast_check": "forecast_risk_compare",
        "forecast_risk_compare": "forecast_risk_compare",
        "chart_check": "stock_summary",
        "news_materials": "news_materials",
        "rag_search": "news_materials",
        "decision_report_draft": "decision_report_draft",
        "file_export": "decision_report_draft",
        "free_chat": fallback,
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
    }
    return text if text in valid else "free_chat"  # type: ignore[return-value]


def _is_llm_micro_intent(intent: CopilotIntent) -> bool:
    return intent in {"free_chat", "identity", "app_help", "capability_help"}


def _preset_for_intent(intent: CopilotIntent) -> CopilotConversationPreset:
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
