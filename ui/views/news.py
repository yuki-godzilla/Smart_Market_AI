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
    refresh_news_dashboard_cache,
)
from ui.components.mascot import render_page_title
from ui.styles import THEME_COLORS, render_metric_card, style_altair_chart, truncate_text
from ui.symbol_universe import symbol_name

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
        "市場ニュースの流れ、投資ヒートマップ、カテゴリ別材料を確認し、気になる銘柄を深掘りします。",
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
            "value": f"{news_dashboard_unique_headline_count(snapshot)}件",
            "caption": "重複を除いた見出し数",
        },
        {
            "label": "ヒートマップ",
            "value": f"{len(snapshot.heatmap_cells)}件",
            "caption": "値動き + 取引量 + ニュース",
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

    return pd.DataFrame([_heatmap_cell_row(cell) for cell in snapshot.heatmap_cells])


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


def news_dashboard_lane_card_items(
    snapshot: NewsDashboardSnapshot,
    *,
    max_lanes: int = 6,
    max_cards_per_lane: int = 1,
) -> list[tuple[int, int, str, NewsHeadlineCard]]:
    """Return bounded category lane cards for the responsive lane grid."""

    items: list[tuple[int, int, str, NewsHeadlineCard]] = []
    for lane_index, lane in enumerate(snapshot.category_lanes[:max_lanes]):
        for card_index, card in enumerate(lane.headlines[:max_cards_per_lane]):
            items.append((lane_index, card_index, lane.category, card))
    return items


def news_dashboard_unique_headline_count(snapshot: NewsDashboardSnapshot) -> int:
    """Return unique headline count for user-facing status display."""

    seen: set[tuple[str, str, str]] = set()
    cards = list(snapshot.stream_headlines)
    for lane in snapshot.category_lanes:
        cards.extend(lane.headlines)
    for card in cards:
        published = card.published_at.isoformat() if card.published_at else ""
        seen.add((card.title.strip(), card.url or "", published))
    return len(seen)


def _heatmap_cell_row(cell: object) -> dict[str, object]:
    actual_price_change_pct = _optional_float_attr(cell, "price_change_pct")
    actual_volume_activity_score = _optional_float_attr(cell, "volume_activity_score")
    price_change_pct = (
        actual_price_change_pct
        if actual_price_change_pct is not None
        else _fallback_price_signal(cell)
    )
    volume_activity_score = (
        actual_volume_activity_score
        if actual_volume_activity_score is not None
        else _fallback_volume_signal(cell)
    )
    metric_source = (
        "市場データ"
        if actual_price_change_pct is not None and actual_volume_activity_score is not None
        else "ニュース代理"
    )
    region = getattr(cell, "region", None) or "全体"
    return {
        "カテゴリ": getattr(cell, "category"),
        "投資カテゴリ": getattr(cell, "category"),
        "地域": region,
        "分野": region,
        "加熱度": getattr(cell, "heat_score"),
        "市場指標": metric_source,
        "値動き": price_change_pct,
        "値動きスコア": price_change_pct,
        "値動き表示": _price_change_label(
            price_change_pct,
            inferred=actual_price_change_pct is None,
        ),
        "取引量": volume_activity_score,
        "取引量スコア": volume_activity_score,
        "取引量目安": _volume_label(
            volume_activity_score,
            inferred=actual_volume_activity_score is None,
        ),
        "ニュース件数": getattr(cell, "news_count"),
        "リスク材料": getattr(cell, "risk_count"),
        "ポジティブ材料": getattr(cell, "positive_count"),
        "公式開示": getattr(cell, "official_source_count"),
        "鮮度比率": round(getattr(cell, "freshness_ratio") * 100, 1),
        "主な材料": _material_label(getattr(cell, "dominant_material_type")),
    }


def _optional_float_attr(value: object, name: str) -> float | None:
    raw_value = getattr(value, name, None)
    if raw_value is None:
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _fallback_price_signal(cell: object) -> float:
    risk_count = _int_attr(cell, "risk_count")
    positive_count = _int_attr(cell, "positive_count")
    official_count = _int_attr(cell, "official_source_count")
    material_type = getattr(cell, "dominant_material_type", None)
    signal = (positive_count - risk_count) * 0.85 + official_count * 0.2
    if material_type == "risk":
        signal -= 1.15
    elif material_type in {"earnings", "theme", "shareholder_return"}:
        signal += 0.85
    elif material_type == "fund_flow":
        signal += 0.25
    elif material_type in {"macro", "policy"}:
        signal -= 0.2
    if signal == 0:
        signal = min(1.0, _float_attr(cell, "heat_score") / 6.0)
    return round(max(-3.0, min(3.0, signal)), 1)


def _fallback_volume_signal(cell: object) -> float:
    heat_score = _float_attr(cell, "heat_score")
    news_count = _int_attr(cell, "news_count")
    signal = 1.0 + min(1.25, heat_score / 10.0 + news_count * 0.08)
    return round(max(1.0, min(2.3, signal)), 2)


def _float_attr(value: object, name: str) -> float:
    raw_value = getattr(value, name, 0.0)
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.0


def _int_attr(value: object, name: str) -> int:
    raw_value = getattr(value, name, 0)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return 0


def news_symbol_handoff_label(symbol: str) -> str:
    """Return a symbol handoff label with known company name."""

    normalized = symbol.strip().upper()
    try:
        name = symbol_name(normalized)
    except OSError:
        name = None
    if name and name.strip().upper() != normalized:
        return f"{normalized} / {name}"
    return normalized


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
    st.markdown("### 市場ニュースヘッドライン")
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
    st.markdown("### 投資ヒートマップ")
    st.caption(
        "投資カテゴリごとの値動き、取引量の活発さ、ニュース量を合わせた確認用の温度感です。"
        "市場指標がないカテゴリはニュース材料から代理シグナルを補完します。"
    )
    frame = news_dashboard_heatmap_frame(snapshot)
    if frame.empty:
        st.info("投資ヒートマップを集計できる材料はまだありません。")
        return
    base = alt.Chart(frame).encode(
        x=alt.X("分野:N", title=None),
        y=alt.Y(
            "投資カテゴリ:N",
            title=None,
            sort=alt.EncodingSortField(field="加熱度", order="descending"),
        ),
        tooltip=[
            alt.Tooltip("投資カテゴリ:N"),
            alt.Tooltip("分野:N"),
            alt.Tooltip("市場指標:N"),
            alt.Tooltip("加熱度:Q", format=".1f"),
            alt.Tooltip("値動き:Q", format="+.1f"),
            alt.Tooltip("取引量:Q", format=".2f"),
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
            "値動きスコア:Q",
            title="値動き/材料",
            scale=alt.Scale(
                domain=[-3, 0, 3],
                range=[
                    THEME_COLORS["signal_risk"],
                    THEME_COLORS["bg_card_hover"],
                    THEME_COLORS["signal_buy"],
                ],
            ),
        ),
        opacity=alt.Opacity(
            "取引量スコア:Q",
            title="取引量",
            scale=alt.Scale(domain=[1.0, 2.2], range=[0.65, 1.0]),
        ),
    )
    text = base.mark_text(
        color=THEME_COLORS["text_title"],
        fontWeight="bold",
        fontSize=13,
    ).encode(text=alt.Text("値動き表示:N"))
    chart = (rect + text).properties(height=max(260, 44 * frame["投資カテゴリ"].nunique()))
    st.altair_chart(style_altair_chart(chart), use_container_width=True)


def _render_category_lanes(
    snapshot: NewsDashboardSnapshot,
    *,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    st.markdown("### カテゴリ別ニュースレーン")
    lane_items = news_dashboard_lane_card_items(snapshot)
    if not lane_items:
        st.info("カテゴリ別に表示できるニュースはまだありません。")
        return
    for row_start in range(0, len(lane_items), 3):
        cols = st.columns(3)
        for col, (lane_index, card_index, category, card) in zip(
            cols,
            lane_items[row_start : row_start + 3],
            strict=False,
        ):
            with col:
                st.markdown(_lane_heading_html(category), unsafe_allow_html=True)
                st.markdown(news_headline_card_html(card, compact=True), unsafe_allow_html=True)
                _render_symbol_handoff_buttons(
                    card,
                    key_prefix=f"lane_{lane_index}_{card_index}",
                    open_symbol_callback=open_symbol_callback,
                    max_columns=1,
                )


def _render_symbol_handoff_buttons(
    card: NewsHeadlineCard,
    *,
    key_prefix: str,
    open_symbol_callback: OpenSymbolCallback,
    max_columns: int = 3,
) -> None:
    symbols = [symbol.strip().upper() for symbol in card.related_symbols if symbol.strip()]
    if not symbols:
        return
    st.caption("関連銘柄")
    cols = st.columns(min(max_columns, len(symbols)))
    for index, symbol in enumerate(symbols[:3]):
        label = news_symbol_handoff_label(symbol)
        with cols[index % len(cols)]:
            st.button(
                truncate_text(label, max_chars=34),
                key=f"investment_news_open_{key_prefix}_{symbol}",
                help=f"{label}を銘柄コックピットで確認します。",
                use_container_width=True,
                on_click=open_symbol_callback,
                args=(symbol,),
            )


def _lane_heading_html(category: str) -> str:
    return (
        '<div class="investment-news-lane-heading">'
        '<span class="investment-news-lane-dot"></span>'
        f"<span>{html.escape(category)}</span>"
        "</div>"
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


def _price_change_label(value: float | None, *, inferred: bool = False) -> str:
    if value is None:
        return "未取得"
    if inferred:
        return f"材料{value:+.1f}"
    return f"{value:+.1f}%"


def _volume_label(value: float | None, *, inferred: bool = False) -> str:
    if value is None:
        return "未取得"
    suffix = "相当" if inferred else ""
    if value >= 1.8:
        return f"高い{suffix}"
    if value >= 1.3:
        return f"やや高い{suffix}"
    return f"通常{suffix}"
