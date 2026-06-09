from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Mapping, Sequence, cast
from urllib.parse import urlencode

import streamlit as st

from backend.assistant import (
    AssistantRequest,
    AssistantResponse,
    TemplateAssistantService,
)
from backend.reporting import (
    DecisionReportContext,
    ReportSourceKind,
    build_decision_report_context,
    build_report_section,
)
from ui.components.mascot import MASCOT_THUMB_ASSET, _asset_data_uri

ASSISTANT_CONTEXTS_STATE_KEY = "smai_assistant_contexts"
ASSISTANT_CONTEXT_ORDER_STATE_KEY = "smai_assistant_context_order"
ASSISTANT_QUERY_CONTEXT_KEY = "smai_assistant_context"
ASSISTANT_QUERY_OPEN_KEY = "smai_assistant_open"
ASSISTANT_QUERY_QUESTION_KEY = "smai_assistant_question"


@dataclass(frozen=True)
class SmaiAssistantContext:
    """Current UI context that the local assistant can explain."""

    context_id: str
    page_key: str
    page_label: str
    section_key: str
    section_label: str
    lead: str
    summary: Mapping[str, object] = field(default_factory=dict)
    rows: Sequence[Mapping[str, object]] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    notes: Sequence[str] = field(default_factory=tuple)
    suggested_questions: Sequence[str] = field(default_factory=tuple)
    priority: int = 50


def reset_assistant_contexts() -> None:
    """Start each Streamlit render with fresh page-local assistant contexts."""

    st.session_state[ASSISTANT_CONTEXTS_STATE_KEY] = {}
    st.session_state[ASSISTANT_CONTEXT_ORDER_STATE_KEY] = []


def register_assistant_context(context: SmaiAssistantContext) -> None:
    contexts = _assistant_contexts()
    order = _assistant_context_order()
    contexts[context.context_id] = context
    if context.context_id not in order:
        order.append(context.context_id)


def render_floating_assistant(*, page_key: str, page_label: str) -> None:
    """Render the floating SMAI Copilot for the current screen."""

    context = _selected_context(page_key=page_key, page_label=page_label)
    query_targets_context = _query_targets_current_context(context)
    question = _query_param_text(ASSISTANT_QUERY_QUESTION_KEY) if query_targets_context else ""
    response = _assistant_response(context, question) if question else None
    open_panel = bool(
        query_targets_context and (response or _query_param_text(ASSISTANT_QUERY_OPEN_KEY))
    )
    st.markdown(
        floating_assistant_html(
            context,
            response=response,
            selected_question=question,
            open_panel=open_panel,
            sibling_contexts=_page_contexts(context.page_key),
        ),
        unsafe_allow_html=True,
    )


def floating_assistant_html(
    context: SmaiAssistantContext,
    *,
    response: AssistantResponse | None = None,
    selected_question: str = "",
    open_panel: bool = False,
    sibling_contexts: Sequence[SmaiAssistantContext] = (),
) -> str:
    image = _asset_data_uri(MASCOT_THUMB_ASSET)
    open_checked = " checked" if open_panel else ""
    visual_key = _assistant_visual_key(context)
    trigger_label = _assistant_trigger_label(context)
    trigger_aria = f"SMAI Copilot: {trigger_label}（{context.section_label}）"
    toggle_id = f"{_assistant_dom_id(context.context_id)}-open"
    local_questions = _local_question_switcher_html(
        context,
        response=response,
        selected_question=selected_question,
    )
    context_links = "".join(
        _context_link_html(item)
        for item in sibling_contexts
        if item.context_id != context.context_id
    )
    context_switcher = (
        '<div class="smai-floating-assistant-contexts">'
        "<span>関連セクション</span>"
        f"{context_links}"
        "</div>"
        if context_links
        else ""
    )
    return (
        '<div class="smai-floating-assistant">'
        '<input class="smai-floating-assistant-toggle" type="checkbox" '
        f'id="{html.escape(toggle_id, quote=True)}"{open_checked} '
        'aria-label="SMAI Copilotを開閉" />'
        '<div class="smai-floating-assistant-body" role="dialog" aria-label="SMAI Copilot">'
        '<div class="smai-floating-assistant-head">'
        "<div>"
        '<div class="smai-floating-assistant-kicker">SMAI Copilot</div>'
        f"<h3>{html.escape(context.page_label)}</h3>"
        "</div>"
        f"<span>{html.escape(context.section_label)}</span>"
        "</div>"
        f'<p class="smai-floating-assistant-lead">{html.escape(context.lead)}</p>'
        f"{local_questions}"
        f"{context_switcher}"
        "</div>"
        '<label class="smai-floating-assistant-backdrop" '
        f'for="{html.escape(toggle_id, quote=True)}" '
        'aria-label="SMAI Copilotを閉じる"></label>'
        '<label class="smai-floating-assistant-trigger" '
        f'for="{html.escape(toggle_id, quote=True)}" '
        f'aria-label="{html.escape(trigger_aria, quote=True)}" role="button">'
        f'<span class="smai-floating-assistant-avatar '
        f'smai-floating-assistant-avatar--{visual_key}" aria-hidden="true">'
        '<span class="smai-floating-assistant-stage">'
        '<span class="smai-assistant-orbit"></span>'
        '<span class="smai-assistant-holo-chart">'
        '<span class="smai-assistant-holo-range"></span>'
        '<span class="smai-assistant-holo-line line-a"></span>'
        '<span class="smai-assistant-holo-line line-b"></span>'
        '<span class="smai-assistant-holo-line line-c"></span>'
        "</span>"
        '<span class="smai-assistant-rank-bars">'
        "<span></span><span></span><span></span>"
        "</span>"
        f'<img class="smai-floating-assistant-character" src="{image}" alt="" loading="lazy" />'
        "</span>"
        "</span>"
        '<span class="smai-floating-assistant-trigger-copy">'
        '<span class="smai-floating-assistant-kicker">SMAI Copilot</span>'
        f"<strong>{html.escape(trigger_label)}</strong>"
        "</span>"
        "</label>"
        "</div>"
    )


def _assistant_trigger_label(context: SmaiAssistantContext) -> str:
    labels_by_context = {
        "cockpit_setup": "取得前の確認を聞く",
        "cockpit_forecast": "予測の読み方を聞く",
        "cockpit_direction": "シグナルの理由を聞く",
        "cockpit_report": "残す確認点を聞く",
        "ranking_setup": "条件設定を確認する",
        "ranking_results": "上位理由を聞く",
        "ranking_deep_dive": "候補の比べ方を聞く",
        "news_overview": "ニュースの見方を聞く",
        "rebalance_overview": "配分見直しを聞く",
        "settings_overview": "データ設定を確認する",
    }
    if context.context_id in labels_by_context:
        return labels_by_context[context.context_id]

    text = f"{context.page_key} {context.section_key} {context.section_label}".lower()
    if any(term in text for term in ("forecast", "予測", "insight", "インサイト")):
        return "予測の読み方を聞く"
    if any(term in text for term in ("direction", "signal", "上昇", "下降", "警戒")):
        return "シグナルの理由を聞く"
    if any(term in text for term in ("deep_dive", "candidate", "候補", "深掘り")):
        return "候補の比べ方を聞く"
    if any(term in text for term in ("ranking", "ランキング", "順位", "score", "スコア")):
        return "上位理由を聞く"
    if any(term in text for term in ("report", "レポート", "memo", "メモ")):
        return "残す確認点を聞く"
    if any(term in text for term in ("setup", "取得", "設定", "before")):
        return "まず設定を確認"
    if "news" in text or "投資レーダー" in text or "ニュース" in text:
        return "ニュースの見方を聞く"
    if any(term in text for term in ("research", "rag", "根拠", "調査", "ニュース", "news")):
        return "根拠の見方を聞く"
    if any(term in text for term in ("risk", "リスク")):
        return "リスクの見方を聞く"
    if any(term in text for term in ("rebalance", "リバランス", "配分", "調整")):
        return "調整ポイントを聞く"
    return "この画面の見どころを聞く"


def _assistant_visual_key(context: SmaiAssistantContext) -> str:
    text = f"{context.page_key} {context.section_key} {context.section_label}".lower()
    if any(term in text for term in ("forecast", "予測", "insight", "インサイト")):
        return "forecast"
    if any(term in text for term in ("ranking", "ランキング", "順位", "候補", "deep_dive")):
        return "ranking"
    if any(term in text for term in ("direction", "上昇", "下降", "警戒", "signal")):
        return "direction"
    if any(term in text for term in ("report", "レポート")):
        return "report"
    return "setup"


def _assistant_response(
    context: SmaiAssistantContext,
    question: str,
) -> AssistantResponse:
    return TemplateAssistantService().answer(
        AssistantRequest(
            question=question,
            report_context=_context_to_report_context(context),
            max_points=5,
        )
    )


def _context_to_report_context(context: SmaiAssistantContext) -> DecisionReportContext:
    summary = {
        "画面": context.page_label,
        "セクション": context.section_label,
        "見方": context.lead,
        **{str(key): value for key, value in context.summary.items()},
    }
    source_kind = _report_source_kind(context.page_key)
    section = build_report_section(
        title=f"{context.page_label} / {context.section_label}",
        source_kind=source_kind,
        summary=summary,
        rows=context.rows,
        warnings=[str(value) for value in context.warnings if str(value).strip()],
        notes=[
            context.lead,
            *[str(value) for value in context.notes if str(value).strip()],
        ],
    )
    return build_decision_report_context(
        title=f"SMAI Assistant - {context.page_label}",
        sections=[section],
        tags=["assistant", context.page_key, context.section_key],
    )


def _report_source_kind(page_key: str) -> ReportSourceKind:
    if page_key in {"cockpit", "ranking", "rebalance"}:
        return cast(ReportSourceKind, page_key)
    if page_key == "news":
        return "research"
    return "manual"


def _assistant_empty_state_html(context: SmaiAssistantContext) -> str:
    return (
        '<div class="smai-floating-assistant-answer">'
        "<strong>この場所でよく聞かれること</strong>"
        f"<p>{html.escape(context.section_label)}の数値や注意点を、質問チップから確認できます。</p>"
        "</div>"
    )


def _local_question_switcher_html(
    context: SmaiAssistantContext,
    *,
    response: AssistantResponse | None,
    selected_question: str,
) -> str:
    questions = tuple(_assistant_questions(context))
    if response is not None and selected_question and selected_question not in questions:
        questions = (selected_question, *questions)
    if not questions:
        return _assistant_empty_state_html(context)

    selected_index = questions.index(selected_question) if selected_question in questions else 0
    base_id = _assistant_dom_id(context.context_id)
    group_name = f"{base_id}-question"
    labels: list[str] = []
    panels: list[str] = []

    for index, question in enumerate(questions):
        input_id = f"{base_id}-question-{index}"
        checked = " checked" if index == selected_index else ""
        question_position = index + 1
        labels.append(
            '<label class="smai-floating-assistant-chip '
            f'smai-floating-assistant-chip--{question_position}">'
            '<input class="smai-floating-assistant-question-input '
            f'smai-floating-assistant-question-input--{question_position}" '
            f'type="radio" name="{html.escape(group_name, quote=True)}" '
            f'id="{html.escape(input_id, quote=True)}"{checked} />'
            f"<span>{html.escape(question)}</span>"
            "</label>"
        )
        answer = (
            response
            if response is not None and question == selected_question
            else _assistant_response(context, question)
        )
        panels.append(
            '<div class="smai-floating-assistant-answer-panel '
            f'smai-floating-assistant-answer-panel--{question_position}">'
            f"{_assistant_response_html(answer, question)}"
            "</div>"
        )

    return (
        '<div class="smai-floating-assistant-localqa">'
        '<div class="smai-floating-assistant-chips">'
        f"{''.join(labels)}"
        "</div>"
        '<div class="smai-floating-assistant-answers">'
        f"{''.join(panels)}"
        "</div>"
        "</div>"
    )


def _assistant_response_html(response: AssistantResponse, question: str) -> str:
    reasons = _list_html(response.reasons[:4])
    cautions = _list_html(response.cautions[:3])
    checkpoints = _list_html(response.next_checkpoints[:4])
    return (
        '<div class="smai-floating-assistant-chat">'
        f'<div class="smai-floating-assistant-user">{html.escape(question)}</div>'
        '<div class="smai-floating-assistant-answer">'
        f"<strong>{html.escape(response.answer)}</strong>"
        f'{_assistant_block_html("見る材料", reasons)}'
        f'{_assistant_block_html("注意点", cautions)}'
        f'{_assistant_block_html("次に確認すること", checkpoints)}'
        "</div>"
        "</div>"
    )


def _assistant_block_html(title: str, content: str) -> str:
    if not content:
        return ""
    return (
        '<div class="smai-floating-assistant-block">'
        f"<span>{html.escape(title)}</span>"
        f"{content}"
        "</div>"
    )


def _list_html(items: Sequence[str]) -> str:
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def _context_link_html(context: SmaiAssistantContext) -> str:
    href = _assistant_context_href(context.context_id)
    return (
        '<a class="smai-floating-assistant-context-link" '
        f'href="{html.escape(href, quote=True)}" target="_self">'
        f"{html.escape(context.section_label)}</a>"
    )


def _assistant_context_href(context_id: str) -> str:
    return "?" + urlencode(
        {
            ASSISTANT_QUERY_CONTEXT_KEY: context_id,
            ASSISTANT_QUERY_OPEN_KEY: "1",
        }
    )


def _assistant_questions(context: SmaiAssistantContext) -> Sequence[str]:
    if context.suggested_questions:
        return context.suggested_questions
    if context.page_key == "ranking":
        return (
            "なぜこの候補が上位？",
            "深掘り候補の比較ポイントは？",
            "AI総合・上昇気配・下降警戒の違いは？",
            "低信頼データはどう読む？",
        )
    if context.page_key == "cockpit":
        return (
            "この銘柄でまず見るべき点は？",
            "AI予測インサイトをどう読む？",
            "上昇気配・下降警戒の理由は？",
            "Decision Reportに残す確認ポイントは？",
        )
    return (
        "この画面でまず見る点は？",
        "注意して確認する点は？",
        "次に確認することは？",
    )


def _assistant_dom_id(value: str) -> str:
    safe = "".join(
        character.lower() if character.isascii() and character.isalnum() else "-"
        for character in value
    )
    compact = "-".join(part for part in safe.split("-") if part)
    return f"smai-assistant-{compact or 'context'}"


def _selected_context(*, page_key: str, page_label: str) -> SmaiAssistantContext:
    contexts = _page_contexts(page_key)
    query_context_id = _query_param_text(ASSISTANT_QUERY_CONTEXT_KEY)
    for context in contexts:
        if context.context_id == query_context_id:
            return context
    if contexts:
        return sorted(
            contexts,
            key=lambda item: (
                item.priority,
                _assistant_context_order_index(item.context_id),
            ),
            reverse=True,
        )[0]
    return _fallback_assistant_context(page_key=page_key, page_label=page_label)


def _fallback_assistant_context(*, page_key: str, page_label: str) -> SmaiAssistantContext:
    presets = {
        "news": {
            "section_label": "ニュース確認",
            "lead": "市場ニュース、カテゴリ別材料、関連銘柄、出典の鮮度を確認します。",
            "questions": (
                "ニュースはどこから見る？",
                "関連銘柄はどう読む？",
                "出典と鮮度で何を見る？",
            ),
        },
        "rebalance": {
            "section_label": "配分見直し",
            "lead": "現在比率と目標比率のズレ、提案取引、リスク警告を確認します。",
            "questions": (
                "まずどのズレを見る？",
                "提案取引はどう読む？",
                "リスク警告は何を確認する？",
            ),
        },
        "settings": {
            "section_label": "データ設定",
            "lead": "データ取得元、ローカル資料、キャッシュ状態を確認します。",
            "questions": (
                "データ取得元はどう選ぶ？",
                "ローカル資料は何に使う？",
                "キャッシュ状態はどう見る？",
            ),
        },
    }
    preset = presets.get(
        page_key,
        {
            "section_label": "画面の見方",
            "lead": "この画面の確認順をSMAIが整理します。",
            "questions": _assistant_questions(
                SmaiAssistantContext(
                    context_id=f"{page_key}_fallback",
                    page_key=page_key,
                    page_label=page_label,
                    section_key="fallback",
                    section_label="画面の見方",
                    lead="",
                )
            ),
        },
    )
    return SmaiAssistantContext(
        context_id=f"{page_key}_overview",
        page_key=page_key,
        page_label=page_label,
        section_key="overview",
        section_label=str(preset["section_label"]),
        lead=str(preset["lead"]),
        suggested_questions=cast(Sequence[str], preset["questions"]),
        priority=0,
    )


def _query_targets_current_context(context: SmaiAssistantContext) -> bool:
    return _query_param_text(ASSISTANT_QUERY_CONTEXT_KEY) == context.context_id


def _page_contexts(page_key: str) -> list[SmaiAssistantContext]:
    return [context for context in _assistant_contexts().values() if context.page_key == page_key]


def _assistant_contexts() -> dict[str, SmaiAssistantContext]:
    contexts = st.session_state.get(ASSISTANT_CONTEXTS_STATE_KEY)
    if not isinstance(contexts, dict):
        contexts = {}
        st.session_state[ASSISTANT_CONTEXTS_STATE_KEY] = contexts
    return cast(dict[str, SmaiAssistantContext], contexts)


def _assistant_context_order() -> list[str]:
    order = st.session_state.get(ASSISTANT_CONTEXT_ORDER_STATE_KEY)
    if not isinstance(order, list):
        order = []
        st.session_state[ASSISTANT_CONTEXT_ORDER_STATE_KEY] = order
    return cast(list[str], order)


def _assistant_context_order_index(context_id: str) -> int:
    try:
        return _assistant_context_order().index(context_id)
    except ValueError:
        return -1


def _query_param_text(key: str) -> str:
    params = getattr(st, "query_params", None)
    if params is None:
        return ""
    getter = getattr(params, "get", None)
    try:
        value = getter(key) if callable(getter) else params[key]  # type: ignore[index]
    except (KeyError, TypeError):
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value or "").strip()
