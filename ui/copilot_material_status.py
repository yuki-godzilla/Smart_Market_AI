from __future__ import annotations

import html

import streamlit as st

from ui.components.assistant import SmaiAssistantContext


def material_status(context: SmaiAssistantContext) -> tuple[tuple[str, str], ...]:
    text = " ".join(
        [
            context.context_id,
            context.page_key,
            context.section_key,
            context.section_label,
            " ".join(str(value) for value in context.summary.values()),
        ]
    ).lower()
    # Static screen descriptions are navigation context, not acquired market data.
    has_data = bool(context.rows)
    has_news = has_data and any(term in text for term in ("news", "ニュース", "開示"))
    has_research = has_data and any(term in text for term in ("research", "rag", "根拠"))
    has_forecast = has_data and any(term in text for term in ("forecast", "予測", "ai予測"))
    has_price = has_data and any(term in text for term in ("価格", "chart", "cockpit", "ranking"))
    return (
        ("価格", "あり" if has_price else "なし"),
        ("AI予測", "あり" if has_forecast else "なし"),
        ("ニュース", "あり" if has_news else "なし"),
        ("Research Evidence", "あり" if has_research else "なし"),
        ("Decision Report", "下書き可"),
        ("LLM", "Gateway優先 / fallbackあり"),
    )


def material_status_summary(context: SmaiAssistantContext) -> str:
    visible = [
        (label, value)
        for label, value in material_status(context)
        if label not in {"Decision Report", "LLM"}
    ]
    return "この会話の参照材料: " + " / ".join(f"{label}={value}" for label, value in visible)


def render_material_status(context: SmaiAssistantContext) -> None:
    visible = [
        (label, value)
        for label, value in material_status(context)
        if label not in {"Decision Report", "LLM"}
    ]
    chips = "".join(
        f'<span class="smai-copilot-chip">{html.escape(label)}: {html.escape(value)}</span>'
        for label, value in visible
    )
    st.markdown(
        '<div class="smai-copilot-material-status">'
        "<span>この会話の参照状況</span>"
        f'<div class="smai-copilot-chip-row">{chips}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
