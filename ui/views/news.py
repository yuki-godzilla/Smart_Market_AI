from __future__ import annotations

import html
from collections.abc import Callable
from datetime import UTC, datetime

import altair as alt
import pandas as pd
import streamlit as st

from backend.news import (
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    NewsUpdateStatus,
    build_demo_news_dashboard_snapshot,
    get_news_cache_file_size,
    load_cached_news_dashboard_snapshot,
    load_news_update_status,
    news_snapshot_item_count,
    refresh_news_dashboard_cache,
)
from ui.components.mascot import render_page_title
from ui.styles import THEME_COLORS, render_metric_card, style_altair_chart, truncate_text

OpenSymbolCallback = Callable[[str], None]

NEWS_DASHBOARD_REFRESH_STATE_KEY = "investment_news_dashboard_refresh_message"

_FRESHNESS_LABELS = {
    "latest": "最新",
    "recent": "近日",
    "stale": "古め",
    "unknown": "未確認",
}

_MATERIAL_LABELS = {
    "earnings": "決算・業績",
    "fund_flow": "資金フロー",
    "macro": "マクロ",
    "policy": "政策",
    "risk": "リスク材料",
    "shareholder_return": "株主還元",
    "theme": "テーマ",
}

_MATERIAL_TONES = {
    "earnings": "positive",
    "fund_flow": "neutral",
    "macro": "important",
    "policy": "important",
    "risk": "risk",
    "shareholder_return": "positive",
    "theme": "news",
}


def render_news_dashboard_page(
    *,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    """Render the Investment Radar dashboard MVP."""

    render_page_title(
        "投資レーダー",
        "市場ニュースの流れ、加熱テーマ、カテゴリ別材料を確認し、気になる銘柄を深掘りします。",
        "investment_radar",
    )

    snapshot, status, using_demo = _load_dashboard_snapshot()
    _render_refresh_controls()
    _render_status_message()
    _render_dashboard_status(snapshot, status, using_demo=using_demo)
    _render_news_stream(snapshot, open_symbol_callback=open_symbol_callback)
    _render_heatmap(snapshot)
    _render_category_lanes(snapshot, open_symbol_callback=open_symbol_callback)


def news_dashboard_status_items(
    snapshot: NewsDashboardSnapshot,
    status: NewsUpdateStatus,
    *,
    using_demo: bool,
    cache_size_bytes: int | None = None,
) -> list[dict[str, str]]:
    """Return compact status cards for the news dashboard header."""

    cache_size = cache_size_bytes
    if cache_size is None:
        cache_size = status.cache_file_size_bytes
    return [
        {
            "label": "表示ニュース",
            "value": f"{news_snapshot_item_count(snapshot)}件",
            "caption": "保存済み + カテゴリ表示",
        },
        {
            "label": "加熱テーマ",
            "value": f"{len(snapshot.heatmap_cells)}件",
            "caption": "ニュース量と鮮度で集計",
        },
        {
            "label": "鮮度",
            "value": _freshness_label(snapshot.freshness_status),
            "caption": _datetime_label(snapshot.generated_at),
        },
        {
            "label": "表示元",
            "value": "デモ" if using_demo else "キャッシュ",
            "caption": _cache_size_label(cache_size),
        },
    ]


def news_dashboard_heatmap_frame(snapshot: NewsDashboardSnapshot) -> pd.DataFrame:
    """Return the heatmap frame used by the Investment News chart."""

    return pd.DataFrame(
        [
            {
                "カテゴリ": cell.category,
                "地域": cell.region or "全体",
                "加熱度": cell.heat_score,
                "ニュース件数": cell.news_count,
                "リスク材料": cell.risk_count,
                "ポジティブ材料": cell.positive_count,
                "公式開示": cell.official_source_count,
                "鮮度比率": round(cell.freshness_ratio * 100, 1),
                "主な材料": _material_label(cell.dominant_material_type),
            }
            for cell in snapshot.heatmap_cells
        ]
    )


def news_headline_card_html(
    card: NewsHeadlineCard,
    *,
    compact: bool = False,
) -> str:
    """Return a display card for a news headline without exposing raw URL text."""

    tone = _MATERIAL_TONES.get(card.material_type, "news")
    source = card.source_name or _source_type_label(card.source_type)
    freshness = _freshness_label(card.freshness_status)
    summary = card.summary or "概要は未取得です。元記事と公式資料で確認してください。"
    comment = card.ai_comment or "関連する公式資料と銘柄コックピットで前提を確認します。"
    checkpoint_items = "".join(
        f"<li>{html.escape(checkpoint)}</li>" for checkpoint in card.investment_checkpoints[:3]
    )
    official_badge = (
        '<span class="investment-news-chip official">公式系</span>'
        if card.is_official_source
        else ""
    )
    link_label = "元記事を見る" if card.url else "URL未取得"
    link_attrs = (
        f'href="{html.escape(card.url)}" target="_blank" rel="noopener noreferrer"'
        if card.url
        else 'href="#" aria-disabled="true"'
    )
    compact_class = " compact" if compact else ""
    published = _datetime_label(card.published_at)
    return (
        f'<article class="investment-news-card {tone}{compact_class}">'
        '<div class="investment-news-card-main">'
        '<div class="investment-news-card-chips">'
        f'<span class="investment-news-chip primary">{html.escape(_material_label(card.material_type))}</span>'
        f'<span class="investment-news-chip">{html.escape(freshness)}</span>'
        f'<span class="investment-news-chip">{html.escape(source)}</span>'
        f"{official_badge}"
        "</div>"
        f'<h3 class="investment-news-card-title">{html.escape(card.title)}</h3>'
        '<div class="investment-news-card-meta">'
        f"<span>{html.escape(card.category)}</span>"
        f"<span>{html.escape(card.region or '全体')}</span>"
        f"<span>公開 {html.escape(published)}</span>"
        "</div>"
        f'<p class="investment-news-card-summary">{html.escape(summary)}</p>'
        f'<p class="investment-news-card-comment">{html.escape(comment)}</p>'
        f'<ul class="investment-news-card-checkpoints">{checkpoint_items}</ul>'
        "</div>"
        '<div class="investment-news-card-aside">'
        f'<a class="investment-news-source-link" {link_attrs}>{html.escape(link_label)} ↗</a>'
        "</div>"
        "</article>"
    )


def news_dashboard_handoff_symbols(snapshot: NewsDashboardSnapshot) -> list[str]:
    """Return unique related symbols in display order for handoff tests and UI."""

    symbols: list[str] = []
    seen: set[str] = set()
    for card in snapshot.stream_headlines:
        for symbol in card.related_symbols:
            normalized = symbol.strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            symbols.append(normalized)
    return symbols


def _load_dashboard_snapshot() -> tuple[NewsDashboardSnapshot, NewsUpdateStatus, bool]:
    status = load_news_update_status()
    snapshot = load_cached_news_dashboard_snapshot()
    if snapshot is not None:
        return snapshot, status, False
    return build_demo_news_dashboard_snapshot(), status, True


def _render_refresh_controls() -> None:
    col_action, col_note = st.columns([0.8, 2.2])
    with col_action:
        if st.button("ニュース表示を更新", key="investment_news_refresh", type="secondary"):
            result = refresh_news_dashboard_cache(
                lambda: build_demo_news_dashboard_snapshot(now=datetime.now(UTC)),
                force=True,
            )
            if result.refreshed:
                st.session_state[NEWS_DASHBOARD_REFRESH_STATE_KEY] = "ニュース表示を更新しました。"
            elif result.used_fallback_cache:
                st.session_state[NEWS_DASHBOARD_REFRESH_STATE_KEY] = (
                    "更新に失敗したため、前回保存データを表示しています。"
                )
            else:
                st.session_state[NEWS_DASHBOARD_REFRESH_STATE_KEY] = (
                    "ニュース表示を更新できませんでした。"
                )
            st.rerun()
    with col_note:
        st.caption(
            "ニュースは市場テーマと確認材料の入口です。スコアやランキング順位は変更しません。"
        )


def _render_status_message() -> None:
    message = st.session_state.pop(NEWS_DASHBOARD_REFRESH_STATE_KEY, None)
    if message:
        st.toast(str(message), icon="✅")


def _render_dashboard_status(
    snapshot: NewsDashboardSnapshot,
    status: NewsUpdateStatus,
    *,
    using_demo: bool,
) -> None:
    items = news_dashboard_status_items(
        snapshot,
        status,
        using_demo=using_demo,
        cache_size_bytes=get_news_cache_file_size(),
    )
    cols = st.columns(4)
    for col, item in zip(cols, items, strict=True):
        with col:
            render_metric_card(
                item["label"],
                item["value"],
                caption=item["caption"],
                tone="forecast" if item["label"] in {"鮮度", "表示元"} else "info",
            )
    if status.last_error_type:
        st.warning(
            "ニュース更新で確認が必要な状態です。前回保存データまたはデモ表示を使っています。"
        )


def _render_news_stream(
    snapshot: NewsDashboardSnapshot,
    *,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    st.markdown("### マーケットニュースストリーム")
    st.markdown(_news_ticker_html(snapshot.stream_headlines[:8]), unsafe_allow_html=True)
    featured = snapshot.stream_headlines[:3]
    if not featured:
        st.info("表示できるニュースはまだありません。")
        return
    cols = st.columns(len(featured))
    for index, card in enumerate(featured):
        with cols[index]:
            st.markdown(news_headline_card_html(card, compact=True), unsafe_allow_html=True)
            _render_symbol_handoff_buttons(
                card,
                key_prefix=f"stream_{index}",
                open_symbol_callback=open_symbol_callback,
            )


def _render_heatmap(snapshot: NewsDashboardSnapshot) -> None:
    st.markdown("### ニュース加熱テーマ")
    frame = news_dashboard_heatmap_frame(snapshot)
    if frame.empty:
        st.info("加熱テーマを集計できるニュースはまだありません。")
        return
    base = alt.Chart(frame).encode(
        x=alt.X("カテゴリ:N", title=None, sort="-color"),
        y=alt.Y("地域:N", title=None),
        tooltip=[
            alt.Tooltip("カテゴリ:N"),
            alt.Tooltip("地域:N"),
            alt.Tooltip("加熱度:Q", format=".1f"),
            alt.Tooltip("ニュース件数:Q"),
            alt.Tooltip("リスク材料:Q"),
            alt.Tooltip("ポジティブ材料:Q"),
            alt.Tooltip("公式開示:Q"),
            alt.Tooltip("鮮度比率:Q", format=".1f"),
            alt.Tooltip("主な材料:N"),
        ],
    )
    rect = base.mark_rect(cornerRadius=4).encode(
        color=alt.Color(
            "加熱度:Q",
            title="加熱度",
            scale=alt.Scale(
                range=[
                    THEME_COLORS["bg_card_hover"],
                    THEME_COLORS["ai_cyan"],
                    THEME_COLORS["signal_risk"],
                ]
            ),
        )
    )
    text = base.mark_text(
        color=THEME_COLORS["text_title"],
        fontWeight="bold",
        fontSize=12,
    ).encode(text=alt.Text("ニュース件数:Q"))
    chart = (rect + text).properties(height=max(180, 42 * frame["地域"].nunique()))
    st.altair_chart(style_altair_chart(chart), use_container_width=True)


def _render_category_lanes(
    snapshot: NewsDashboardSnapshot,
    *,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    st.markdown("### カテゴリ別ニュースレーン")
    if not snapshot.category_lanes:
        st.info("カテゴリ別に表示できるニュースはまだありません。")
        return
    for lane_index, lane in enumerate(snapshot.category_lanes[:6]):
        st.markdown(f"#### {lane.category}")
        cards = lane.headlines[:3]
        cols = st.columns(max(1, len(cards)))
        for card_index, card in enumerate(cards):
            with cols[card_index]:
                st.markdown(news_headline_card_html(card, compact=True), unsafe_allow_html=True)
                _render_symbol_handoff_buttons(
                    card,
                    key_prefix=f"lane_{lane_index}_{card_index}",
                    open_symbol_callback=open_symbol_callback,
                )


def _render_symbol_handoff_buttons(
    card: NewsHeadlineCard,
    *,
    key_prefix: str,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    symbols = [symbol.strip().upper() for symbol in card.related_symbols if symbol.strip()]
    if not symbols:
        return
    st.caption("関連銘柄")
    cols = st.columns(min(3, len(symbols)))
    for index, symbol in enumerate(symbols[:3]):
        with cols[index % len(cols)]:
            st.button(
                truncate_text(symbol, max_chars=12),
                key=f"investment_news_open_{key_prefix}_{symbol}",
                help="銘柄コックピットで確認します。",
                use_container_width=True,
                on_click=open_symbol_callback,
                args=(symbol,),
            )


def _news_ticker_html(cards: list[NewsHeadlineCard]) -> str:
    if not cards:
        return ""
    items = "".join(
        '<span class="investment-news-ticker-item">'
        f'<span class="investment-news-ticker-category">{html.escape(card.category)}</span>'
        f"{html.escape(card.title)}"
        "</span>"
        for card in cards
    )
    return (
        '<section class="investment-news-ticker" aria-label="market news stream">'
        f'<div class="investment-news-ticker-track">{items}{items}</div>'
        "</section>"
    )


def _freshness_label(status: str) -> str:
    return _FRESHNESS_LABELS.get(status, status or "未確認")


def _material_label(material_type: str | None) -> str:
    if material_type is None:
        return "未分類"
    return _MATERIAL_LABELS.get(material_type, material_type)


def _source_type_label(source_type: str) -> str:
    return {
        "disclosure": "開示",
        "ir": "IR",
        "news": "ニュース",
        "provider": "Provider",
    }.get(source_type, source_type)


def _datetime_label(value: datetime | None) -> str:
    if value is None:
        return "未確認"
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _cache_size_label(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "保存なし"
    if size_bytes < 1024:
        return f"{size_bytes}B"
    return f"{size_bytes / 1024:.1f}KB"
