from __future__ import annotations

import html
from decimal import Decimal, InvalidOperation

import altair as alt
import streamlit as st

SMAI_GLOBAL_CSS = """
<style>
:root {
    --smai-bg: #0b1020;
    --smai-panel: #111827;
    --smai-card: #151b2e;
    --smai-card-soft: #1f2937;
    --smai-border: rgba(148, 163, 184, 0.18);
    --smai-border-strong: rgba(148, 163, 184, 0.28);
    --smai-text: #e5e7eb;
    --smai-muted: #9ca3af;
    --smai-accent: #38bdf8;
    --smai-accent-soft: rgba(56, 189, 248, 0.12);
    --smai-green: #22c55e;
    --smai-amber: #f59e0b;
    --smai-gray: #64748b;
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(56, 189, 248, 0.08), transparent 30rem),
        linear-gradient(180deg, #0b1020 0%, #111827 100%);
    color: var(--smai-text);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1020 0%, #111827 100%);
    border-right: 1px solid var(--smai-border);
}

[data-testid="stSidebar"] [data-testid="stButton"] button {
    border-radius: 8px;
    border: 1px solid var(--smai-border);
    background: rgba(21, 27, 46, 0.78);
    color: var(--smai-text);
}

[data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] {
    border-color: rgba(56, 189, 248, 0.45);
    background: rgba(56, 189, 248, 0.14);
}

[data-testid="stMetric"] {
    padding: 0.84rem 0.9rem;
    border: 1px solid var(--smai-border);
    border-radius: 8px;
    background: linear-gradient(180deg, rgba(31, 41, 55, 0.88), rgba(17, 24, 39, 0.86));
}

[data-testid="stMetricLabel"] {
    color: var(--smai-muted);
}

[data-testid="stMetricValue"] {
    color: var(--smai-text);
    letter-spacing: 0;
}

[data-testid="stExpander"] {
    border-color: var(--smai-border);
    background: rgba(17, 24, 39, 0.42);
}

.smai-section-card {
    border: 1px solid var(--smai-border);
    border-radius: 8px;
    background: linear-gradient(180deg, rgba(31, 41, 55, 0.72), rgba(17, 24, 39, 0.72));
    padding: 0.95rem 1rem;
    margin: 0.35rem 0 0.7rem 0;
}

.smai-metric-card {
    min-height: 9.2rem;
    border: 1px solid var(--smai-border);
    border-radius: 8px;
    background: linear-gradient(180deg, rgba(31, 41, 55, 0.82), rgba(17, 24, 39, 0.86));
    padding: 0.88rem 0.95rem;
}

.smai-card-label {
    color: var(--smai-muted);
    font-size: 0.78rem;
    line-height: 1.3;
    margin-bottom: 0.35rem;
}

.smai-card-value {
    color: var(--smai-text);
    font-size: 1.28rem;
    line-height: 1.25;
    font-weight: 760;
    overflow-wrap: anywhere;
}

.smai-card-caption {
    color: var(--smai-muted);
    font-size: 0.82rem;
    line-height: 1.45;
    margin-top: 0.5rem;
}

.smai-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.32rem;
    margin-top: 0.58rem;
}

.smai-badge {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.14rem 0.48rem;
    border: 1px solid transparent;
    font-size: 0.72rem;
    font-weight: 680;
    line-height: 1.3;
}

.smai-badge.info {
    color: #bae6fd;
    background: rgba(56, 189, 248, 0.12);
    border-color: rgba(56, 189, 248, 0.22);
}

.smai-badge.success {
    color: #bbf7d0;
    background: rgba(34, 197, 94, 0.12);
    border-color: rgba(34, 197, 94, 0.22);
}

.smai-badge.caution {
    color: #fde68a;
    background: rgba(245, 158, 11, 0.12);
    border-color: rgba(245, 158, 11, 0.24);
}

.smai-badge.neutral {
    color: #cbd5e1;
    background: rgba(100, 116, 139, 0.14);
    border-color: rgba(148, 163, 184, 0.18);
}
</style>
"""


def render_global_styles() -> None:
    st.markdown(SMAI_GLOBAL_CSS, unsafe_allow_html=True)


def compact_display_value(value: object, fallback: str = "-") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    suffix = "%" if text.endswith("%") else ""
    numeric_text = text.removesuffix("%").replace(",", "").strip()
    try:
        number = Decimal(numeric_text)
    except InvalidOperation:
        return text
    if not number.is_finite():
        return fallback
    if number == number.to_integral_value():
        formatted = f"{number:.0f}"
    else:
        formatted = f"{number:.1f}".rstrip("0").rstrip(".")
    return f"{formatted}{suffix}"


def truncate_text(value: object, *, max_chars: int = 48, fallback: str = "-") -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return fallback
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 1].rstrip()}…"


def badge_html(label: str, tone: str = "neutral") -> str:
    safe_tone = tone if tone in {"info", "success", "caution", "neutral"} else "neutral"
    return f'<span class="smai-badge {safe_tone}">{html.escape(label)}</span>'


def metric_card_html(
    label: str,
    value: object,
    *,
    caption: str = "",
    badges: tuple[str, ...] = (),
) -> str:
    badge_row = ""
    if badges:
        badge_row = f'<div class="smai-badge-row">{"".join(badges)}</div>'
    caption_html = (
        f'<div class="smai-card-caption" title="{html.escape(caption)}">'
        f"{html.escape(truncate_text(caption, max_chars=82, fallback=''))}</div>"
        if caption
        else ""
    )
    return (
        '<div class="smai-metric-card">'
        f'<div class="smai-card-label">{html.escape(label)}</div>'
        f'<div class="smai-card-value">{html.escape(compact_display_value(value))}</div>'
        f"{caption_html}"
        f"{badge_row}"
        "</div>"
    )


def render_metric_card(
    label: str,
    value: object,
    *,
    caption: str = "",
    badges: tuple[str, ...] = (),
) -> None:
    st.markdown(
        metric_card_html(label, value, caption=caption, badges=badges),
        unsafe_allow_html=True,
    )


def style_altair_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure(background="#0b1020")
        .configure_view(fill="#111827", stroke="rgba(148, 163, 184, 0.22)")
        .configure_axis(
            domainColor="rgba(148, 163, 184, 0.38)",
            gridColor="rgba(148, 163, 184, 0.14)",
            labelColor="#cbd5e1",
            titleColor="#e5e7eb",
            tickColor="rgba(148, 163, 184, 0.38)",
        )
        .configure_legend(labelColor="#cbd5e1", titleColor="#e5e7eb")
        .configure_title(color="#e5e7eb", fontSize=13, anchor="start", offset=8)
    )
