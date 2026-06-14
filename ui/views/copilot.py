from __future__ import annotations

import base64
import html
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import uuid4

import streamlit as st

from backend.assistant import (
    AssistantMessage,
    AssistantResponse,
    detect_assistant_intent,
    execute_assistant_tool_plan,
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
COPILOT_LLM_PROFILE_STATE_KEY = "smai_copilot_llm_profile"
COPILOT_LLM_MODEL_STATE_KEY = "smai_copilot_llm_model"

COPILOT_LLM_MODEL_OPTIONS: tuple[tuple[str, str, str], ...] = (
    ("notebook_dev", "qwen3:4b", "ノートPC / 軽量開発"),
    ("desktop_fast", "qwen3:8b", "デスクトップ通常 / Copilot・要約"),
    ("desktop_analysis", "qwen3:14b", "デスクトップ高精度 / 銘柄分析・RAG"),
    ("desktop_heavy", "qwen3:30b", "高負荷分析 / 週次・月次レポート"),
)

CopilotIntent = Literal[
    "app_help",
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
    model: str = "qwen3:4b"
    profile: str = "notebook_dev"

    @property
    def mode_label(self) -> str:
        return "LLM Gateway" if self.enabled else "deterministic"

    @property
    def status_label(self) -> str:
        return "LLM接続: ON" if self.enabled else "LLM接続: OFF"


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

    return CopilotGatewayRuntimeConfig(
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
    return "qwen3:4b"


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


def _render_composer_toolbar(
    runtime_config: CopilotGatewayRuntimeConfig,
) -> CopilotGatewayRuntimeConfig:
    st.markdown(
        '<div class="smai-copilot-composer-toolbar" aria-label="LLM model selector">',
        unsafe_allow_html=True,
    )
    model_col, status_col = st.columns([0.28, 0.72])
    with model_col:
        selected = _render_model_selector(runtime_config)
    with status_col:
        st.caption(
            f"LLM: {selected.provider} / {selected.model} / {selected.profile}"
            if selected.enabled
            else "LLM: deterministic fallback"
        )
    st.markdown("</div>", unsafe_allow_html=True)
    return selected


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
        execution_mode=runtime_config.execution_mode,
        environment_profile=runtime_config.environment_profile,
        preferred_profile=runtime_config.profile,  # type: ignore[arg-type]
    )
    assistant_config = settings.assistant.model_copy(update={"gateway": gateway})
    return settings.model_copy(update={"assistant": assistant_config})


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
    if intent == "free_chat":
        return _response_meta_html(turn)
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
    )


def copilot_turn_html(turn: dict[str, str]) -> str:
    context_label = str(turn.get("context_label", "")).strip()
    question = str(turn.get("question", "")).strip()
    answer = str(turn.get("answer", "")).strip()
    return (
        '<div class="smai-copilot-thread">'
        f"{_user_bubble_html(context_label=context_label, question=question)}"
        f"{_assistant_bubble_html(answer=answer, detail_html=copilot_answer_detail_html(turn))}"
        "</div>"
    )


def render_copilot_workspace_page() -> None:
    contexts = copilot_context_options()
    context_by_id = {context.context_id: context for context in contexts}
    history = _copilot_history()
    runtime_config = copilot_gateway_runtime_config()

    _, clear_col = st.columns([0.82, 0.18])
    with clear_col:
        clear = st.button("新しい会話", use_container_width=True)

    st.markdown(
        _chat_header_html(history_count=len(history), runtime_config=runtime_config),
        unsafe_allow_html=True,
    )
    _render_material_status(_active_context_from_history(history, context_by_id))

    if clear:
        st.session_state[COPILOT_CHAT_HISTORY_STATE_KEY] = []
        st.session_state[COPILOT_CONVERSATION_ID_STATE_KEY] = _new_conversation_id()
        st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = "free_chat"
        st.rerun()

    runtime_config = _render_composer_toolbar(runtime_config)

    prompt = st.chat_input(
        "価格・予測・ニュース・根拠資料について確認したいことを入力...",
        key="smai_copilot_chat_input",
        max_chars=240,
    )

    if prompt:
        intent = _intent_from_message(prompt, fallback=_active_intent())
        preset = _preset_for_intent(intent)
        context = context_by_id.get(preset.context_id, contexts[0])
        with st.spinner("SMAIナビが必要な材料を確認しています... LLMで回答を生成中"):
            _handle_copilot_submit(
                context,
                prompt,
                intent=intent,
                prompt_instruction=preset.prompt_instruction,
                visible_question=prompt,
                runtime_config=runtime_config,
            )
        st.rerun()

    _render_chat_thread(history)
    suggested = _render_suggestion_buttons(has_history=bool(history))

    if suggested is not None:
        context = context_by_id.get(suggested.context_id, contexts[0])
        with st.spinner("SMAIナビが必要な材料を確認しています... LLMで回答を生成中"):
            _handle_copilot_submit(
                context,
                suggested.default_question,
                intent=suggested.intent,
                prompt_instruction=suggested.prompt_instruction,
                visible_question=suggested.label,
                runtime_config=runtime_config,
            )
        st.rerun()

    st.caption(
        "SMAIアシスタントは判断材料の整理を補助します。売買推奨、スコア変更、"
        "ランキング順位変更は行いません。"
    )


def _render_chat_thread(turns: list[dict[str, str]]) -> None:
    if not turns:
        return

    pending_turn_id = str(st.session_state.get(COPILOT_PENDING_STREAM_STATE_KEY, "") or "")
    for index, turn in enumerate(turns):
        if pending_turn_id and str(turn.get("turn_id", "")) == pending_turn_id:
            _render_streaming_turn(turn)
            st.session_state[COPILOT_PENDING_STREAM_STATE_KEY] = ""
        else:
            st.markdown(copilot_turn_html(turn), unsafe_allow_html=True)
        _render_turn_actions(turn, index=index)


def _render_suggestion_buttons(
    *,
    has_history: bool,
) -> CopilotConversationPreset | None:
    heading = "続けて相談" if has_history else "今日は何を相談しますか？"
    st.markdown(
        f'<div class="smai-copilot-suggestions-title">{html.escape(heading)}</div>',
        unsafe_allow_html=True,
    )
    _, suggestions_col, _ = st.columns([0.14, 0.72, 0.14])
    with suggestions_col:
        if has_history:
            return _render_followup_buttons()
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


def _render_followup_buttons() -> CopilotConversationPreset | None:
    followups: tuple[tuple[str, CopilotIntent], ...] = (
        ("予測だけ確認", "forecast_risk_compare"),
        ("ニュースだけ再確認", "news_materials"),
        ("Decision Report下書きへ", "decision_report_draft"),
    )
    columns = st.columns(len(followups))
    for index, (label, intent) in enumerate(followups):
        preset = _preset_for_intent(intent)
        with columns[index]:
            if st.button(
                label,
                key=f"smai_copilot_followup_{intent}",
                use_container_width=True,
                help=preset.description,
            ):
                st.session_state[COPILOT_ACTIVE_INTENT_STATE_KEY] = intent
                return preset
    return None


def _handle_copilot_submit(
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

    history = _copilot_history()
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
        if intent != "free_chat"
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
        message_history=() if intent == "free_chat" else copilot_history_messages(history),
        referenced_context_ids=[] if intent == "free_chat" else [context.context_id],
        gateway_task_type=intent,
        settings=copilot_settings_from_gateway_runtime(runtime_config),
    )
    turn = _turn_from_response(
        context,
        visible_question,
        response,
        intent=intent,
        executed_checks=[
            *([] if intent == "free_chat" else [_material_status_summary(context)]),
            *tool_summaries,
        ],
        tool_statuses=[
            f"{result.name}: {result.status}"
            for result in (tool_plan.executed if tool_plan else ())
        ],
    )
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
    if intent != "free_chat":
        return context
    return SmaiAssistantContext(
        context_id="copilot_free_chat_minimal",
        page_key="assistant",
        page_label="SMAIアシスタント",
        section_key="free_chat",
        section_label="自由会話",
        lead="SMAIナビとの短い会話です。",
        summary={
            "role": "SMAIナビ",
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
    executed_checks: list[str] | None = None,
    tool_statuses: list[str] | None = None,
) -> dict[str, str]:
    return {
        "turn_id": uuid4().hex,
        "context_id": context.context_id,
        "context_label": copilot_context_label(context),
        "intent": intent,
        "intent_label": _preset_for_intent(intent).label,
        "question": question,
        "answer": _conversation_answer(intent=intent, question=question, response=response),
        "reasons": "\n".join(response.reasons),
        "cautions": "\n".join(response.cautions),
        "next_checkpoints": "\n".join(response.next_checkpoints),
        "memo_points": "\n".join(_memo_points_for_intent(intent, response)),
        "executed_checks": "\n".join(executed_checks or ()),
        "tool_statuses": "\n".join(tool_statuses or ()),
        "response_source": response.response_source,
        "model": response.model or "",
        "provider": response.provider or "",
        "profile": response.profile or "",
        "latency_ms": str(response.latency_ms or ""),
        "gateway_status": response.gateway_status or "",
        "fallback_reason": response.fallback_reason or "",
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
    status_label = "準備完了" if history_count == 0 else "確認中"
    status_detail = "SMAIナビ" if history_count == 0 else f"会話 {history_count}件"
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
        "<div>"
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


def _assistant_bubble_html(*, answer: str, detail_html: str) -> str:
    image = _asset_data_uri(MASCOT_THUMB_ASSET)
    return (
        '<section class="smai-copilot-message-row smai-copilot-message-row--assistant">'
        '<div class="smai-copilot-assistant-avatar" aria-hidden="true">'
        f'<img class="smai-copilot-assistant-avatar-image '
        f'smai-copilot-assistant-avatar-image--reply" src="{image}" alt="" loading="lazy" />'
        "</div>"
        '<div class="smai-copilot-message-card smai-copilot-message-card--assistant">'
        '<div class="smai-copilot-message-meta">SMAIナビ</div>'
        f'<p class="smai-copilot-natural-lead">{html.escape(answer)}</p>'
        f"{detail_html}"
        "</div>"
        "</section>"
    )


def _render_streaming_turn(turn: dict[str, str]) -> None:
    context_label = str(turn.get("context_label", "")).strip()
    question = str(turn.get("question", "")).strip()
    answer = str(turn.get("answer", "")).strip()
    st.markdown(
        _user_bubble_html(context_label=context_label, question=question),
        unsafe_allow_html=True,
    )
    placeholder = st.empty()
    for partial in _stream_chunks(answer):
        placeholder.markdown(
            _assistant_bubble_html(answer=partial, detail_html=""),
            unsafe_allow_html=True,
        )
        time.sleep(0.006)
    placeholder.markdown(
        _assistant_bubble_html(answer=answer, detail_html=copilot_answer_detail_html(turn)),
        unsafe_allow_html=True,
    )


def _stream_chunks(text: str) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return [""]
    chunk_size = max(12, min(28, len(normalized) // 8 or 12))
    chunks = [normalized[:index] for index in range(chunk_size, len(normalized), chunk_size)]
    chunks.append(normalized)
    return chunks[:16]


def _action_card_intro_html(*, preset: CopilotConversationPreset) -> str:
    return (
        '<div class="smai-copilot-action-card">'
        f'<span class="smai-copilot-action-label">{html.escape(preset.label)}</span>'
        f"<p>{html.escape(preset.description)}</p>"
        "</div>"
    )


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
    if intent == "free_chat" and _is_simple_greeting(question):
        return "こんにちは。SMAIナビです。何を相談しますか？"
    if intent == "app_help" and response.response_source not in {"gateway", "llm"}:
        return (
            "SMAIは、目的別に画面を使い分けると分かりやすいです。\n\n"
            "- 銘柄を深掘りする: 銘柄コックピット\n"
            "- 候補を探す: 銘柄ランキング\n"
            "- 市場全体の材料を見る: 投資レーダー\n"
            "- 判断メモを残す: Decision Report"
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


def _is_simple_greeting(question: str) -> bool:
    normalized = str(question or "").strip().lower()
    return normalized in {
        "こんにちは",
        "こんばんは",
        "おはよう",
        "おはようございます",
        "hello",
        "hi",
    }


def _safe_response_body(answer: str, *, intent: CopilotIntent | None = None) -> str:
    text = str(answer or "").strip()
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
        "</think>",
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
        if intent in {"free_chat", "app_help"} and any(
            marker in line for marker in repetitive_markers
        ):
            continue
        filtered.append(line)
    return "\n".join(filtered).strip()


def _execution_result_html(turn: dict[str, str]) -> str:
    executed = _split_lines(turn.get("executed_checks", ""))
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
    return f'<div class="smai-copilot-response-meta">{html.escape(meta)}</div>'


def _render_turn_actions(turn: dict[str, str], *, index: int) -> None:
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
    st.markdown(
        (
            '<div class="smai-copilot-thread smai-copilot-actions-thread">'
            '<div class="smai-copilot-actions-row">'
            f"{action_links}"
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _actions_for_turn(turn: dict[str, str]) -> tuple[tuple[str, str], ...]:
    intent = _normalize_intent(turn.get("intent", ""))
    if intent == "free_chat":
        return (("コピー", "copy"),)
    if intent == "app_help":
        return (("コピー", "copy"), ("Markdownで保存", "memo"))
    if intent == "decision_report_draft":
        return (("Markdownで保存", "memo"), ("Decision Reportに追加", "report"))
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
    lines = [
        f"相談モード: {turn.get('intent_label', '')}",
        f"対象: {turn.get('context_label', '')}",
        f"質問: {turn.get('question', '')}",
        "",
        str(turn.get("answer", "")).strip(),
    ]
    executed = _split_lines(turn.get("executed_checks", ""))
    if executed:
        lines.extend(["", "実行した確認:"])
        lines.extend(f"- {item}" for item in executed)
    for title, key in zip(
        _section_titles_for_intent(_normalize_intent(turn.get("intent", ""))),
        ("reasons", "cautions", "next_checkpoints", "memo_points"),
    ):
        items = _split_lines(turn.get(key, ""))
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
    answer = str(turn.get("answer", "")).strip()
    reasons = _markdown_list(_split_lines(turn.get("reasons", "")))
    cautions = _markdown_list(_split_lines(turn.get("cautions", "")))
    checkpoints = _markdown_list(_split_lines(turn.get("next_checkpoints", "")))
    memo_points = _markdown_list(_split_lines(turn.get("memo_points", "")))
    executed = _markdown_list(_split_lines(turn.get("executed_checks", "")))
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
    if intent == "free_chat":
        return question.strip()[:800]
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


def _intent_from_message(message: str, *, fallback: CopilotIntent) -> CopilotIntent:
    decision = detect_assistant_intent(message)
    mapping: dict[str, CopilotIntent] = {
        "app_help": "app_help",
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
    valid = {preset.intent for preset in copilot_conversation_presets()}
    return text if text in valid else "free_chat"  # type: ignore[return-value]


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
