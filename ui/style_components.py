from __future__ import annotations

import html
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation

import altair as alt
import streamlit as st

CARD_TONES = {"neutral", "info", "score", "success", "forecast", "caution", "risk"}
CARD_EMPHASIS = {"normal", "spotlight"}


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
    safe_tone = tone if tone in {"info", "success", "caution", "danger", "neutral"} else "neutral"
    return f'<span class="smai-badge {safe_tone}">{html.escape(label)}</span>'


def metric_progress_from_value(value: object) -> int | None:
    text = str(value or "").strip().removesuffix("%").replace(",", "")
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    clamped = min(Decimal("100"), max(Decimal("0"), number))
    return int(clamped.to_integral_value(rounding="ROUND_HALF_UP"))


def metric_card_html(
    label: str,
    value: object,
    *,
    caption: str = "",
    help_text: str = "",
    badges: tuple[str, ...] = (),
    tone: str = "neutral",
    emphasis: str = "normal",
    progress: int | None = None,
) -> str:
    badge_row = f'<div class="smai-badge-row">{"".join(badges)}</div>' if badges else ""
    progress_bar = ""
    if progress is not None:
        safe_progress = min(100, max(0, int(progress)))
        progress_bar = (
            '<div class="smai-score-track" aria-hidden="true">'
            f'<div class="smai-score-fill" style="--smai-score-width: {safe_progress}%"></div>'
            "</div>"
        )
    caption_html = (
        f'<div class="smai-card-caption" title="{html.escape(caption)}">'
        f"{html.escape(truncate_text(caption, max_chars=82, fallback=''))}</div>"
        if caption
        else ""
    )
    if help_text:
        label_html = (
            '<div class="smai-card-label-row">'
            f'<div class="smai-card-label">{html.escape(label)}</div>'
            '<span class="smai-card-help" '
            f'title="{html.escape(help_text, quote=True)}" '
            f'aria-label="{html.escape(label, quote=True)} の説明">?</span>'
            "</div>"
        )
    else:
        label_html = f'<div class="smai-card-label">{html.escape(label)}</div>'
    safe_tone = tone if tone in CARD_TONES else "neutral"
    safe_emphasis = emphasis if emphasis in CARD_EMPHASIS else "normal"
    return (
        '<div class="smai-metric-card" '
        f'data-tone="{safe_tone}" data-emphasis="{safe_emphasis}">'
        f"{label_html}"
        f'<div class="smai-card-value">{html.escape(compact_display_value(value))}</div>'
        f"{progress_bar}{caption_html}{badge_row}</div>"
    )


def render_metric_card(
    label: str,
    value: object,
    *,
    caption: str = "",
    help_text: str = "",
    badges: tuple[str, ...] = (),
    tone: str = "neutral",
    emphasis: str = "normal",
    progress: int | None = None,
) -> None:
    st.markdown(
        metric_card_html(
            label,
            value,
            caption=caption,
            help_text=help_text,
            badges=badges,
            tone=tone,
            emphasis=emphasis,
            progress=progress,
        ),
        unsafe_allow_html=True,
    )


def dashboard_header_html(
    title: str, subtitle: str = "", *, chips: Iterable[tuple[str, str]] = ()
) -> str:
    chip_html = "".join(
        '<span class="smai-dashboard-chip">'
        f'<span class="smai-chip-label">{html.escape(label)}</span>'
        f"<span>{html.escape(value)}</span></span>"
        for label, value in chips
        if str(value or "").strip()
    )
    chip_row = f'<div class="smai-dashboard-chip-row">{chip_html}</div>' if chip_html else ""
    subtitle_html = (
        f'<p class="smai-dashboard-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    )
    return (
        '<section class="smai-dashboard-header">'
        f'<h2 class="smai-dashboard-title">{html.escape(title)}</h2>'
        f"{subtitle_html}{chip_row}</section>"
    )


def render_dashboard_header(
    title: str, subtitle: str = "", *, chips: Iterable[tuple[str, str]] = ()
) -> None:
    st.markdown(dashboard_header_html(title, subtitle, chips=chips), unsafe_allow_html=True)


def section_heading_html(title: str) -> str:
    return f'<div class="smai-section-title">{html.escape(title)}</div>'


def render_section_heading(title: str) -> None:
    st.markdown(section_heading_html(title), unsafe_allow_html=True)


def style_altair_chart(chart: alt.Chart, theme_colors: dict[str, str]) -> alt.Chart:
    return (
        chart.configure(background=theme_colors["bg_surface"])
        .configure_view(fill=theme_colors["bg_card"], stroke=theme_colors["border_default"])
        .configure_axis(
            domainColor=theme_colors["border_strong"],
            gridColor=theme_colors["chart_grid"],
            labelColor=theme_colors["text_caption"],
            titleColor=theme_colors["text_label"],
            tickColor=theme_colors["border_strong"],
        )
        .configure_legend(
            labelColor=theme_colors["text_secondary"], titleColor=theme_colors["text_heading"]
        )
        .configure_title(color=theme_colors["text_heading"], fontSize=13, anchor="start", offset=8)
    )
