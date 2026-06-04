from __future__ import annotations

import html
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from urllib.parse import quote

import pandas as pd
import streamlit as st

from backend.news import (
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    NewsUpdateStatus,
    build_demo_news_dashboard_snapshot,
    build_standard_news_dashboard_snapshot,
    get_news_cache_file_size,
    load_cached_news_dashboard_snapshot,
    load_news_update_status,
    refresh_news_dashboard_cache,
)
from ui.components.mascot import render_page_title
from ui.styles import render_metric_card, truncate_text
from ui.symbol_universe import symbol_name

OpenSymbolCallback = Callable[[str], None]

NEWS_DASHBOARD_REFRESH_STATE_KEY = "investment_news_dashboard_refresh_message"
NEWS_COCKPIT_QUERY_PAGE_PARAM = "smai_page"
NEWS_COCKPIT_QUERY_SYMBOL_PARAM = "smai_symbol"
NEWS_COCKPIT_QUERY_COCKPIT_VALUE = "cockpit"

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

_HEATMAP_TILE_OFFSETS = (0.0, -0.35, 0.28, 0.62, -0.72, 0.18, -0.15, 0.45, -0.42, 0.08)

_HEATMAP_SYMBOL_SHORT_NAMES = {
    "NVDA": "NVIDIA",
    "6857.T": "アドバンテスト",
    "8035.T": "東京エレクトロン",
    "7203.T": "トヨタ自動車",
    "8306.T": "三菱UFJ",
    "8316.T": "三井住友FG",
    "6758.T": "ソニーG",
    "9432.T": "NTT",
    "JPM": "JPMorgan",
    "QQQ": "QQQ",
    "1488.T": "日経高配当50",
    "1605.T": "INPEX",
    "XLE": "エネルギーETF",
    "VOO": "S&P500 ETF",
    "2558.T": "MAXIS S&P500",
    "7011.T": "三菱重工",
    "9101.T": "日本郵船",
    "GLD": "ゴールドETF",
    "AMZN": "Amazon",
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
            "label": "表示中ニュース",
            "value": f"{news_dashboard_unique_headline_count(snapshot)}件",
            "caption": "サンプル見出し数" if using_demo else "重複を除いた見出し数",
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
            "label": "データ状態",
            "value": "サンプル表示" if using_demo else "保存データ",
            "caption": "手動更新前の例示データ" if using_demo else _cache_size_label(cache_size),
        },
    ]


def news_dashboard_heatmap_frame(snapshot: NewsDashboardSnapshot) -> pd.DataFrame:
    """Return the heatmap frame used by the Investment News chart."""

    return pd.DataFrame([_heatmap_cell_row(cell) for cell in snapshot.heatmap_cells])


def news_dashboard_stock_heatmap_groups(
    snapshot: NewsDashboardSnapshot,
    *,
    max_groups: int = 12,
    max_tiles_per_group: int = 12,
) -> list[dict[str, object]]:
    """Return sector-style groups for the stock heatmap view."""

    if max_groups <= 0 or max_tiles_per_group <= 0:
        return []
    frame = news_dashboard_heatmap_frame(snapshot)
    if frame.empty:
        return []
    lanes_by_category = {lane.category: lane for lane in snapshot.category_lanes}
    groups: list[dict[str, object]] = []
    sorted_frame = frame.sort_values("加熱度", ascending=False).head(max_groups)
    for group_index, row in enumerate(sorted_frame.to_dict("records")):
        category = str(row["投資カテゴリ"])
        lane = lanes_by_category.get(category)
        symbols = _heatmap_group_symbols(lane.headlines if lane else [], max_tiles_per_group)
        if not symbols:
            symbols = [category]
        tiles = [
            _stock_heatmap_tile(symbol, row, tile_index)
            for tile_index, symbol in enumerate(symbols[:max_tiles_per_group])
        ]
        groups.append(
            {
                "category": category,
                "region": str(row["分野"]),
                "metric_source": str(row["市場指標"]),
                "heat_score": row["加熱度"],
                "group_class": _stock_heatmap_group_class(group_index, float(row["加熱度"])),
                "summary_label": str(row["値動き表示"]),
                "tiles": tiles,
            }
        )
    return groups


def news_dashboard_stock_heatmap_html(snapshot: NewsDashboardSnapshot) -> str:
    """Return a sector-style stock heatmap HTML surface."""

    groups = news_dashboard_stock_heatmap_groups(snapshot)
    if not groups:
        return ""
    tile_count = sum(_stock_heatmap_group_tile_count(group) for group in groups)
    group_html = "".join(_stock_heatmap_group_html(group) for group in groups)
    return (
        '<section class="investment-stock-heatmap" aria-label="investment stock heatmap">'
        '<div class="investment-stock-heatmap-topline">'
        '<span class="investment-stock-heatmap-read">'
        f"表示: {len(groups)}セクター / {tile_count}銘柄タイル。"
        "銘柄名・シンボル・値動きを並べて確認できます。"
        "</span>"
        '<span class="investment-stock-heatmap-click">コックピット連携</span>'
        '<span class="investment-stock-heatmap-legend negative">注意材料</span>'
        '<span class="investment-stock-heatmap-legend neutral">中立</span>'
        '<span class="investment-stock-heatmap-legend positive">好材料</span>'
        "</div>"
        f'<div class="investment-stock-heatmap-board">{group_html}</div>'
        "</section>"
    )


def news_dashboard_cockpit_href(symbol: str) -> str:
    """Return the same-app URL used to open a heatmap symbol in the cockpit."""

    normalized = symbol.strip().upper()
    encoded_symbol = quote(normalized, safe="")
    return (
        f"?{NEWS_COCKPIT_QUERY_PAGE_PARAM}={NEWS_COCKPIT_QUERY_COCKPIT_VALUE}"
        f"&{NEWS_COCKPIT_QUERY_SYMBOL_PARAM}={encoded_symbol}"
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
    checkpoint_limit = 1 if compact else 3
    checkpoint_items = "".join(
        f"<li>{html.escape(checkpoint)}</li>"
        for checkpoint in card.investment_checkpoints[:checkpoint_limit]
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
    max_lanes: int = 9,
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


def _heatmap_group_symbols(
    cards: list[NewsHeadlineCard],
    limit: int,
) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for card in cards:
        for symbol in card.related_symbols:
            normalized = symbol.strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            symbols.append(normalized)
            if len(symbols) >= limit:
                return symbols
    return symbols


def _stock_heatmap_tile(
    symbol: str,
    row: dict[str, object],
    tile_index: int,
) -> dict[str, object]:
    base_change = _coerce_float(row.get("値動きスコア"), 0.0)
    change = round(
        max(
            -3.0,
            min(3.0, base_change + _HEATMAP_TILE_OFFSETS[tile_index % len(_HEATMAP_TILE_OFFSETS)]),
        ),
        1,
    )
    inferred = str(row.get("市場指標")) != "市場データ"
    display_name, full_name = _stock_heatmap_tile_names(symbol)
    label = f"{symbol} / {full_name}" if full_name else symbol
    return {
        "symbol": symbol,
        "name": display_name,
        "full_name": full_name,
        "label": label,
        "href": news_dashboard_cockpit_href(symbol),
        "change": change,
        "change_label": _price_change_label(change, inferred=inferred),
        "tone": _stock_heatmap_tone(change),
        "size": _stock_heatmap_tile_size(tile_index),
    }


def _stock_heatmap_tile_names(symbol: str) -> tuple[str, str]:
    normalized_symbol = symbol.strip().upper()
    short_name = _HEATMAP_SYMBOL_SHORT_NAMES.get(normalized_symbol)
    try:
        name = symbol_name(symbol)
    except OSError:
        name = None
    if short_name:
        return short_name, (name or short_name).strip()
    if not name or name.strip().upper() == symbol.strip().upper():
        return "", ""
    normalized = name.strip()
    return truncate_text(normalized, max_chars=30), normalized


def _stock_heatmap_tone(change: float) -> str:
    if change >= 1.4:
        return "strong-positive"
    if change >= 0.35:
        return "positive"
    if change <= -1.4:
        return "strong-negative"
    if change <= -0.35:
        return "negative"
    return "neutral"


def _stock_heatmap_tile_size(tile_index: int) -> str:
    if tile_index == 0:
        return "hero"
    if tile_index in {1, 2}:
        return "major"
    if tile_index in {3, 4, 5}:
        return "medium"
    return "minor"


def _stock_heatmap_group_class(group_index: int, heat_score: float) -> str:
    if group_index < 2 or heat_score >= 4.5:
        return "mega"
    if group_index < 5 or heat_score >= 3.2:
        return "large"
    return "medium"


def _stock_heatmap_group_html(group: dict[str, object]) -> str:
    category = html.escape(str(group["category"]))
    region = html.escape(str(group["region"]))
    metric_source = html.escape(str(group["metric_source"]))
    summary_label = html.escape(str(group["summary_label"]))
    group_class = html.escape(str(group["group_class"]))
    tiles_raw = group.get("tiles")
    tiles = cast(list[dict[str, object]], tiles_raw) if isinstance(tiles_raw, list) else []
    tile_html = "".join(_stock_heatmap_tile_html(tile) for tile in tiles)
    count_class = f"count-{min(len(tiles), 6)}"
    return (
        f'<article class="investment-stock-heatmap-group {group_class} {count_class}">'
        '<header class="investment-stock-heatmap-group-header">'
        f'<span class="investment-stock-heatmap-group-title">{category}</span>'
        f'<span class="investment-stock-heatmap-group-meta">{region} / {metric_source} / {summary_label}</span>'
        "</header>"
        f'<div class="investment-stock-heatmap-tiles">{tile_html}</div>'
        "</article>"
    )


def _stock_heatmap_group_tile_count(group: dict[str, object]) -> int:
    tiles = group.get("tiles")
    return len(tiles) if isinstance(tiles, list) else 0


def _stock_heatmap_tile_html(tile: dict[str, object]) -> str:
    symbol = html.escape(str(tile["symbol"]))
    name = html.escape(str(tile["name"]))
    label = html.escape(str(tile["label"]), quote=True)
    href = html.escape(str(tile["href"]), quote=True)
    change_label = html.escape(str(tile["change_label"]))
    tone = html.escape(str(tile["tone"]))
    size = html.escape(str(tile["size"]))
    primary_name = name or symbol
    symbol_html = f'<span class="investment-stock-heatmap-symbol">{symbol}</span>' if name else ""
    return (
        f'<a class="investment-stock-heatmap-tile {tone} {size}" '
        f'href="{href}" title="{label}" aria-label="{label}">'
        '<span class="investment-stock-heatmap-identity">'
        f'<span class="investment-stock-heatmap-name">{primary_name}</span>'
        f"{symbol_html}"
        "</span>"
        f'<span class="investment-stock-heatmap-change">{change_label}</span>'
        "</a>"
    )


def _coerce_float(value: object, fallback: float) -> float:
    if not isinstance(value, (int, float, str)):
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


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
            now = datetime.now(UTC)
            result = refresh_news_dashboard_cache(
                lambda: build_standard_news_dashboard_snapshot(
                    allow_network=True,
                    now=now,
                    fallback_to_demo=False,
                ),
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
            "手動更新では外部ニュースRSSを広めに取得し、重複を除いて最大100件の確認材料に整理します。"
            "スコアやランキング順位は変更しません。"
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
                tone="forecast" if item["label"] in {"鮮度", "データ状態"} else "info",
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
        "カテゴリごとの市場温度感を、セクター枠と関連銘柄タイルで確認します。"
        "市場指標がないカテゴリはニュース材料から代理シグナルを補完します。"
    )
    heatmap_html = news_dashboard_stock_heatmap_html(snapshot)
    if not heatmap_html:
        st.info("投資ヒートマップを集計できる材料はまだありません。")
        return
    st.markdown(heatmap_html, unsafe_allow_html=True)


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
