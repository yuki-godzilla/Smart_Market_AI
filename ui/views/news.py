from __future__ import annotations

import html
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from typing import cast
from urllib.parse import quote

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from backend.news import (
    NewsCategoryLane,
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    NewsUpdateStatus,
    build_demo_news_dashboard_snapshot,
    build_standard_news_dashboard_snapshot,
    load_cached_news_dashboard_snapshot,
    load_news_update_status,
    refresh_news_dashboard_cache,
)
from ui.components.mascot import render_page_title
from ui.styles import truncate_text
from ui.symbol_universe import symbol_name, symbol_universe_csv_rows, symbol_universe_name_map

OpenSymbolCallback = Callable[[str], None]

NEWS_DASHBOARD_REFRESH_STATE_KEY = "investment_news_dashboard_refresh_message"
NEWS_DASHBOARD_WATCHLIST_STATE_KEY = "investment_news_watchlist_symbols"
NEWS_COCKPIT_QUERY_PAGE_PARAM = "smai_page"
NEWS_COCKPIT_QUERY_SYMBOL_PARAM = "smai_symbol"
NEWS_COCKPIT_QUERY_COCKPIT_VALUE = "cockpit"
NEWS_DIRECT_SYMBOL_DISPLAY_LIMIT = 8
NEWS_INFERRED_SYMBOL_DISPLAY_LIMIT = 4
NEWS_SYMBOL_DISPLAY_TOTAL_LIMIT = 8
NEWS_DISPLAY_TIMEZONE = ZoneInfo("Asia/Tokyo")
NEWS_DISPLAY_TIMEZONE_LABEL = "JST"

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

_HEATMAP_MARKET_CAP_WEIGHTS = {
    "mega": 1.4,
    "large": 1.0,
    "mid": 0.52,
    "small": 0.22,
    "micro": 0.02,
}

_HEATMAP_MARKET_CAP_AREA_WEIGHTS = {
    "mega": 2.6,
    "large": 2.1,
    "mid": 1.45,
    "small": 0.85,
    "micro": 0.45,
}

_HEATMAP_MARKET_CAP_LABELS = {
    "mega": "超大型",
    "large": "大型",
    "mid": "中型",
    "small": "小型",
    "micro": "超小型",
}

_HEATMAP_CATEGORY_PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "半導体・AI": {
        "sectors": ("technology",),
        "themes": ("technology", "index"),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "adr", "etf"),
        "keywords": (
            "semiconductor",
            "セミコン",
            "半導体",
            "nvidia",
            "tsmc",
            "asml",
            "advanced micro",
            "ai",
            "robotics",
        ),
        "seed_symbols": ("NVDA", "6857.T", "8035.T", "TSM", "ASML", "AMD"),
    },
    "決算・業績修正": {
        "sectors": (
            "technology",
            "communication",
            "consumer",
            "industrial",
            "financial",
        ),
        "themes": ("technology", "communication", "consumer", "financial", "balanced"),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "adr"),
        "keywords": ("earnings", "growth", "決算", "業績", "profit", "sales"),
        "seed_symbols": ("6758.T", "9432.T", "9984.T", "7974.T", "6861.T"),
    },
    "配当・株主還元": {
        "sectors": ("financial", "industrial", "consumer", "communication", "energy"),
        "themes": ("financial", "consumer", "balanced", "energy"),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "adr", "etf"),
        "keywords": ("dividend", "shareholder", "配当", "自社株", "還元", "高配当"),
        "seed_symbols": ("7203.T", "8306.T", "8316.T", "9432.T", "8058.T"),
    },
    "為替・金利": {
        "sectors": ("financial", "index", "real_estate"),
        "themes": ("financial", "bond", "index", "reit"),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "etf", "reit"),
        "keywords": ("bond", "treasury", "bank", "reit", "為替", "金利", "米国債"),
        "seed_symbols": ("JPM", "QQQ", "1488.T", "SPY", "TLT", "8306.T"),
    },
    "金融": {
        "sectors": ("financial",),
        "themes": ("financial",),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "adr", "etf"),
        "keywords": ("bank", "financial", "insurance", "銀行", "証券", "保険"),
        "seed_symbols": ("8306.T", "8316.T", "JPM", "BAC", "GS", "MS"),
    },
    "エネルギー": {
        "sectors": ("energy", "utilities", "index"),
        "themes": ("energy", "commodity", "index"),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "adr", "etf"),
        "keywords": ("energy", "oil", "lng", "原油", "石油", "ガス", "電力"),
        "seed_symbols": ("1605.T", "XLE", "XOM", "CVX", "5020.T"),
    },
    "ETF": {
        "sectors": ("index",),
        "themes": ("index", "bond", "commodity", "reit"),
        "markets": ("jp", "us"),
        "asset_types": ("etf", "mutual_fund", "reit"),
        "keywords": ("etf", "index", "s&p", "topix", "nasdaq", "低コスト", "指数"),
        "seed_symbols": ("VOO", "2558.T", "QQQ", "SPY", "VTI", "1306.T"),
    },
    "地政学・マクロリスク": {
        "sectors": ("industrial", "energy", "materials", "index"),
        "themes": ("balanced", "energy", "commodity", "index"),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "adr", "etf"),
        "keywords": (
            "defense",
            "gold",
            "shipping",
            "commodity",
            "防衛",
            "海運",
            "資源",
            "金",
        ),
        "seed_symbols": ("7011.T", "9101.T", "GLD", "6208.T", "6301.T", "1605.T"),
    },
    "政策・規制": {
        "sectors": (
            "technology",
            "consumer",
            "financial",
            "industrial",
            "communication",
        ),
        "themes": ("technology", "consumer", "financial", "balanced", "communication"),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "adr", "etf"),
        "keywords": (
            "policy",
            "regulation",
            "tariff",
            "subsidy",
            "政策",
            "規制",
            "関税",
        ),
        "seed_symbols": ("7203.T", "NVDA", "6758.T", "9432.T", "9984.T", "8306.T"),
    },
    "日本株": {
        "sectors": (
            "technology",
            "consumer",
            "financial",
            "industrial",
            "communication",
            "index",
        ),
        "themes": (
            "technology",
            "consumer",
            "financial",
            "balanced",
            "index",
            "communication",
        ),
        "markets": ("jp",),
        "asset_types": ("stock", "etf", "reit"),
        "keywords": ("topix", "nikkei", "japan", "日本", "日経"),
        "seed_symbols": ("7203.T", "8306.T", "6758.T", "9984.T", "7974.T", "6861.T"),
    },
    "米国株": {
        "sectors": (
            "technology",
            "financial",
            "consumer",
            "communication",
            "healthcare",
            "index",
        ),
        "themes": (
            "technology",
            "financial",
            "consumer",
            "communication",
            "healthcare",
            "index",
        ),
        "markets": ("us",),
        "asset_types": ("stock", "adr", "etf"),
        "keywords": ("s&p", "nasdaq", "us", "米国", "growth"),
        "seed_symbols": ("NVDA", "JPM", "QQQ", "AAPL", "MSFT", "AMZN"),
    },
    "小売・消費": {
        "sectors": ("consumer", "communication"),
        "themes": ("consumer", "communication"),
        "markets": ("jp", "us"),
        "asset_types": ("stock", "adr", "etf"),
        "keywords": ("retail", "consumer", "小売", "消費", "ecommerce", "restaurant"),
        "seed_symbols": ("AMZN", "7203.T", "HD", "WMT", "COST", "9983.T"),
    },
}

_HEATMAP_DEFAULT_PROFILE: dict[str, tuple[str, ...]] = {
    "sectors": ("technology", "financial", "consumer", "industrial", "index"),
    "themes": ("technology", "financial", "consumer", "balanced", "index"),
    "markets": ("jp", "us"),
    "asset_types": ("stock", "adr", "etf"),
    "keywords": (),
    "seed_symbols": ("7203.T", "8306.T", "NVDA", "QQQ", "VOO"),
}

_HEATMAP_SYMBOL_SHORT_NAMES = {
    "NVDA": "NVIDIA",
    "TSM": "TSMC",
    "ASML": "ASML",
    "AMD": "AMD",
    "6857.T": "アドバンテスト",
    "8035.T": "東京エレクトロン",
    "7203.T": "トヨタ自動車",
    "8306.T": "三菱UFJ",
    "8316.T": "三井住友FG",
    "8058.T": "三菱商事",
    "6758.T": "ソニーG",
    "9432.T": "NTT",
    "9984.T": "ソフトバンクG",
    "7974.T": "任天堂",
    "6861.T": "キーエンス",
    "JPM": "JPMorgan",
    "BAC": "Bank of America",
    "GS": "Goldman Sachs",
    "MS": "Morgan Stanley",
    "QQQ": "QQQ",
    "SPY": "S&P500 ETF",
    "TLT": "米国債ETF",
    "1488.T": "日経高配当50",
    "1605.T": "INPEX",
    "XLE": "エネルギーETF",
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "5020.T": "ENEOS",
    "VOO": "S&P500 ETF",
    "2558.T": "MAXIS S&P500",
    "VTI": "全米株ETF",
    "1306.T": "TOPIX ETF",
    "7011.T": "三菱重工",
    "9101.T": "日本郵船",
    "6208.T": "石川製作所",
    "6301.T": "コマツ",
    "GLD": "ゴールドETF",
    "AMZN": "Amazon",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "HD": "Home Depot",
    "WMT": "Walmart",
    "COST": "Costco",
    "9983.T": "ファストリ",
}


def render_news_dashboard_page(
    *,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    """Render the Investment Radar dashboard MVP."""

    snapshot, status = _load_dashboard_snapshot()
    render_page_title(
        "投資レーダー",
        "市場ニュースの流れ、投資ヒートマップ、カテゴリ別材料を確認し、気になる銘柄を深掘りします。",
        "investment_radar",
        accessory_html=news_dashboard_freshness_badge_html(snapshot),
    )

    _render_refresh_controls()
    _render_status_message()
    _render_update_warning(status)
    symbol_name_map = _news_symbol_name_map()
    filtered_snapshot = _render_news_detail_filters(snapshot)
    _render_news_stream(
        filtered_snapshot,
        open_symbol_callback=open_symbol_callback,
        symbol_name_map=symbol_name_map,
    )
    _render_heatmap(filtered_snapshot)
    _render_category_lanes(
        filtered_snapshot,
        open_symbol_callback=open_symbol_callback,
        symbol_name_map=symbol_name_map,
    )


def news_dashboard_heatmap_frame(snapshot: NewsDashboardSnapshot) -> pd.DataFrame:
    """Return the heatmap frame used by the Investment News chart."""

    return pd.DataFrame([_heatmap_cell_row(cell) for cell in snapshot.heatmap_cells])


def news_dashboard_stock_heatmap_groups(
    snapshot: NewsDashboardSnapshot,
    *,
    max_groups: int = 12,
    max_tiles_per_group: int = 8,
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
        symbol_scores = _heatmap_group_symbol_scores(
            category,
            lane.headlines if lane else [],
            row,
            max_tiles_per_group,
        )
        symbol_sentiments = _heatmap_group_symbol_sentiments(lane.headlines if lane else [])
        if not symbol_scores:
            symbol_scores = [(category, 0.0)]
        tiles = [
            _stock_heatmap_tile(
                symbol,
                row,
                tile_index,
                symbol_score,
                symbol_sentiments.get(symbol, 0.0),
            )
            for tile_index, (symbol, symbol_score) in enumerate(symbol_scores)
        ]
        balance_label = _stock_heatmap_group_balance_label(tiles)
        groups.append(
            {
                "category": category,
                "region": str(row["分野"]),
                "metric_source": str(row["市場指標"]),
                "heat_score": row["加熱度"],
                "group_class": _stock_heatmap_group_class(group_index, float(row["加熱度"])),
                "summary_label": f'{row["値動き表示"]} / {balance_label}',
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
        "面積は値動き・時価総額目安・注目度、色は値動きで変わります。"
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
        direct_symbols, inferred_symbols = _card_handoff_symbol_groups(card)
        for symbol in [*direct_symbols, *inferred_symbols]:
            normalized = symbol.strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            symbols.append(normalized)
    return symbols


def _card_handoff_symbol_groups(card: NewsHeadlineCard) -> tuple[list[str], list[str]]:
    direct = _unique_normalized_symbols(card.related_symbols)
    inferred = _unique_normalized_symbols(
        getattr(card, "inferred_symbols", []),
        exclude=set(direct),
    )
    return direct, inferred


def news_card_symbol_handoff_groups(
    card: NewsHeadlineCard,
    *,
    direct_limit: int = NEWS_DIRECT_SYMBOL_DISPLAY_LIMIT,
    inferred_limit: int = NEWS_INFERRED_SYMBOL_DISPLAY_LIMIT,
    total_limit: int = NEWS_SYMBOL_DISPLAY_TOTAL_LIMIT,
) -> list[tuple[str, list[str]]]:
    """Return balanced direct/inferred symbol groups for one news card."""

    direct_symbols, inferred_symbols = _card_handoff_symbol_groups(card)
    normalized_direct_limit = max(0, direct_limit)
    normalized_inferred_limit = max(0, inferred_limit)
    normalized_total_limit = max(0, total_limit)
    displayed_direct = direct_symbols[: min(normalized_direct_limit, normalized_total_limit)]
    remaining_slots = max(0, normalized_total_limit - len(displayed_direct))
    displayed_inferred = inferred_symbols[: min(normalized_inferred_limit, remaining_slots)]
    groups: list[tuple[str, list[str]]] = []
    if displayed_direct:
        groups.append(("本文に出た銘柄", displayed_direct))
    if displayed_inferred:
        groups.append(("SMAI推測候補", displayed_inferred))
    return groups


def _unique_normalized_symbols(
    symbols: list[str],
    *,
    exclude: set[str] | None = None,
) -> list[str]:
    seen = set(exclude or set())
    normalized_symbols: list[str] = []
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_symbols.append(normalized)
    return normalized_symbols


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


def news_dashboard_filter_options(
    snapshot: NewsDashboardSnapshot,
) -> dict[str, list[str]]:
    """Return stable filter options for Investment Radar detail controls."""

    cards = _news_dashboard_all_cards(snapshot)
    categories = sorted({card.category for card in cards if card.category})
    freshness = [
        status
        for status in ("latest", "recent", "stale", "unknown")
        if any(card.freshness_status == status for card in cards)
    ]
    sources = sorted({card.source_name or _source_type_label(card.source_type) for card in cards})
    return {
        "categories": categories,
        "freshness": freshness,
        "sources": sources,
    }


def news_dashboard_filtered_snapshot(
    snapshot: NewsDashboardSnapshot,
    *,
    categories: Sequence[str] = (),
    freshness: Sequence[str] = (),
    relation_filter: str = "all",
    sources: Sequence[str] = (),
    watchlist_symbols: Sequence[str] = (),
    watchlist_only: bool = False,
    prioritize_watchlist: bool = True,
) -> NewsDashboardSnapshot:
    """Return a display-only snapshot filtered for the current UI controls."""

    category_set = {value for value in categories if value}
    freshness_set = {value for value in freshness if value}
    source_set = {value for value in sources if value}
    watchlist_set = {symbol.strip().upper() for symbol in watchlist_symbols if symbol.strip()}

    def include(card: NewsHeadlineCard) -> bool:
        if category_set and card.category not in category_set:
            return False
        if freshness_set and card.freshness_status not in freshness_set:
            return False
        source = card.source_name or _source_type_label(card.source_type)
        if source_set and source not in source_set:
            return False
        if relation_filter == "direct" and not card.related_symbols:
            return False
        if relation_filter == "inferred" and not getattr(card, "inferred_symbols", []):
            return False
        if relation_filter == "none" and (
            card.related_symbols or getattr(card, "inferred_symbols", [])
        ):
            return False
        if watchlist_only and not _card_watchlist_symbols(card, watchlist_set):
            return False
        return True

    stream_cards = [card for card in snapshot.stream_headlines if include(card)]
    lanes: list[NewsCategoryLane] = []
    for lane in snapshot.category_lanes:
        lane_cards = [card for card in lane.headlines if include(card)]
        if lane_cards:
            lanes.append(NewsCategoryLane(category=lane.category, headlines=lane_cards))

    if prioritize_watchlist and watchlist_set:
        stream_cards = _sort_cards_by_watchlist(stream_cards, watchlist_set)
        lanes = [
            NewsCategoryLane(
                category=lane.category,
                headlines=_sort_cards_by_watchlist(lane.headlines, watchlist_set),
            )
            for lane in lanes
        ]

    visible_categories = {card.category for card in stream_cards}
    for lane in lanes:
        visible_categories.add(lane.category)
    heatmap_cells = [
        cell
        for cell in snapshot.heatmap_cells
        if not visible_categories or cell.category in visible_categories
    ]

    return NewsDashboardSnapshot(
        schema_version=snapshot.schema_version,
        generated_at=snapshot.generated_at,
        fetched_at=snapshot.fetched_at,
        freshness_status=snapshot.freshness_status,
        stream_headlines=stream_cards,
        heatmap_cells=heatmap_cells,
        category_lanes=lanes,
    )


def _news_dashboard_all_cards(
    snapshot: NewsDashboardSnapshot,
) -> list[NewsHeadlineCard]:
    cards = list(snapshot.stream_headlines)
    for lane in snapshot.category_lanes:
        cards.extend(lane.headlines)
    return cards


def _sort_cards_by_watchlist(
    cards: Sequence[NewsHeadlineCard],
    watchlist_symbols: set[str],
) -> list[NewsHeadlineCard]:
    ranked_cards = sorted(
        enumerate(cards),
        key=lambda item: (
            0 if _card_watchlist_symbols(item[1], watchlist_symbols) else 1,
            -_card_material_rank(item[1]),
            item[0],
        ),
    )
    return [card for _, card in ranked_cards]


def _card_watchlist_symbols(card: NewsHeadlineCard, watchlist_symbols: set[str]) -> list[str]:
    if not watchlist_symbols:
        return []
    direct_symbols, inferred_symbols = _card_handoff_symbol_groups(card)
    return [
        symbol for symbol in [*direct_symbols, *inferred_symbols] if symbol in watchlist_symbols
    ]


def _card_material_rank(card: NewsHeadlineCard) -> int:
    return {
        "earnings": 5,
        "risk": 5,
        "policy": 4,
        "theme": 4,
        "shareholder_return": 3,
        "macro": 3,
        "fund_flow": 2,
    }.get(card.material_type, 1)


def parse_news_watchlist_symbols(value: str) -> list[str]:
    """Parse comma/space separated watchlist symbols for the News UI."""

    parts = re_split_news_watchlist(value)
    symbols: list[str] = []
    for part in parts:
        symbol = part.strip().upper()
        if not symbol or symbol in symbols:
            continue
        symbols.append(symbol)
    return symbols


def re_split_news_watchlist(value: str) -> list[str]:
    return [part for part in re.split(r"[\s,、;；]+", value.strip()) if part]


def news_dashboard_freshness_badge_html(
    snapshot: NewsDashboardSnapshot,
) -> str:
    """Return the small freshness badge shown in the Investment Radar title."""

    freshness = _freshness_label(snapshot.freshness_status)
    fetched_at = snapshot.fetched_at or snapshot.generated_at
    fetched_at_label = _datetime_label(fetched_at)
    return (
        '<div class="investment-news-freshness-badge" '
        f'aria-label="情報鮮度 {html.escape(freshness)} '
        f'取得時刻 {html.escape(fetched_at_label)}">'
        '<span class="investment-news-freshness-status">'
        '<span class="investment-news-freshness-label">情報鮮度</span>'
        f'<strong class="investment-news-freshness-value">{html.escape(freshness)}</strong>'
        "</span>"
        f'<span class="investment-news-freshness-time">取得 {html.escape(fetched_at_label)}</span>'
        "</div>"
    )


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


@lru_cache(maxsize=1)
def _heatmap_symbol_universe_rows() -> tuple[dict[str, str], ...]:
    try:
        return tuple(symbol_universe_csv_rows())
    except OSError:
        return ()


@lru_cache(maxsize=1)
def _heatmap_symbol_names() -> dict[str, str]:
    return {
        row.get("symbol", "").strip().upper(): row.get("name", "").strip()
        for row in _heatmap_symbol_universe_rows()
        if row.get("symbol", "").strip() and row.get("name", "").strip()
    }


@lru_cache(maxsize=1)
def _heatmap_symbol_universe_by_symbol() -> dict[str, dict[str, str]]:
    return {
        row.get("symbol", "").strip().upper(): row
        for row in _heatmap_symbol_universe_rows()
        if row.get("symbol", "").strip()
    }


def _heatmap_group_symbol_scores(
    category: str,
    cards: list[NewsHeadlineCard],
    row: dict[str, object],
    limit: int,
) -> list[tuple[str, float]]:
    if limit <= 0:
        return []
    profile = _HEATMAP_CATEGORY_PROFILES.get(category, _HEATMAP_DEFAULT_PROFILE)
    scores: dict[str, float] = {}
    market_signal = _heatmap_market_signal_boost(row)
    for card_index, card in enumerate(cards):
        card_score = _heatmap_news_card_score(card) + max(0.0, 0.35 - card_index * 0.08)
        direct_symbols, inferred_symbols = _card_handoff_symbol_groups(card)
        for symbol_index, symbol in enumerate(direct_symbols):
            _add_heatmap_symbol_score(
                scores,
                symbol,
                card_score + market_signal - symbol_index * 0.12,
            )
        for symbol_index, symbol in enumerate(inferred_symbols):
            _add_heatmap_symbol_score(
                scores,
                symbol,
                card_score + market_signal - 1.0 - symbol_index * 0.16,
            )
    for symbol, universe_score in _heatmap_universe_symbol_scores(category, profile):
        _add_heatmap_symbol_score(scores, symbol, universe_score + market_signal)
    for symbol_index, symbol in enumerate(profile.get("seed_symbols", ())):
        _add_heatmap_symbol_score(scores, symbol, 5.2 + market_signal - symbol_index * 0.08)
    ranked_symbols = sorted(
        scores.items(),
        key=lambda item: (
            item[1] + _stable_heatmap_symbol_offset(category, item[0]),
            item[0],
        ),
        reverse=True,
    )
    return ranked_symbols[:limit]


def _add_heatmap_symbol_score(
    scores: dict[str, float],
    symbol: str,
    score: float,
) -> None:
    normalized = symbol.strip().upper()
    if not normalized:
        return
    current = scores.get(normalized)
    if current is None:
        scores[normalized] = score
    else:
        scores[normalized] = max(current, score) + min(0.7, score * 0.06)


def _heatmap_news_card_score(card: NewsHeadlineCard) -> float:
    freshness_weight = {
        "latest": 1.1,
        "recent": 0.7,
        "stale": 0.25,
        "unknown": 0.0,
    }.get(card.freshness_status, 0.0)
    material_weight = {
        "risk": 1.15,
        "earnings": 1.0,
        "theme": 0.9,
        "shareholder_return": 0.85,
        "policy": 0.65,
        "macro": 0.6,
        "fund_flow": 0.5,
    }.get(card.material_type, 0.35)
    official_weight = 0.35 if card.is_official_source else 0.0
    return 3.7 + freshness_weight + material_weight + official_weight


def _heatmap_group_symbol_sentiments(cards: list[NewsHeadlineCard]) -> dict[str, float]:
    sentiments: dict[str, float] = {}
    for card_index, card in enumerate(cards):
        polarity = _heatmap_news_card_polarity(card)
        if polarity == 0.0:
            continue
        freshness = 1.0 if card.freshness_status == "latest" else 0.72
        weight = max(0.35, freshness - card_index * 0.08)
        direct_symbols, inferred_symbols = _card_handoff_symbol_groups(card)
        for symbol_index, symbol in enumerate([*direct_symbols, *inferred_symbols]):
            normalized = symbol.strip().upper()
            if not normalized:
                continue
            source_weight = 1.0 if symbol_index < len(direct_symbols) else 0.65
            current = sentiments.get(normalized, 0.0)
            sentiments[normalized] = (
                current + polarity * max(0.25, weight - symbol_index * 0.08) * source_weight
            )
    return {symbol: max(-1.0, min(1.0, value)) for symbol, value in sentiments.items()}


def _heatmap_news_card_polarity(card: NewsHeadlineCard) -> float:
    if card.material_type == "risk":
        return -1.0
    if card.material_type in {"earnings", "theme", "shareholder_return"}:
        return 0.8
    if card.material_type == "fund_flow":
        return 0.25
    if card.material_type in {"macro", "policy"}:
        return -0.25
    return 0.0


def _heatmap_market_signal_boost(row: dict[str, object]) -> float:
    heat_score = _coerce_float(row.get("加熱度"), 0.0)
    price_change = abs(_coerce_float(row.get("値動きスコア"), 0.0))
    volume_score = _coerce_float(row.get("取引量スコア"), 1.0)
    return round(
        min(
            1.8,
            heat_score * 0.08 + price_change * 0.16 + max(0.0, volume_score - 1.0) * 0.35,
        ),
        3,
    )


def _heatmap_universe_symbol_scores(
    category: str,
    profile: dict[str, tuple[str, ...]],
) -> list[tuple[str, float]]:
    profile_sectors = set(profile.get("sectors", ()))
    profile_themes = set(profile.get("themes", ()))
    profile_markets = set(profile.get("markets", ()))
    profile_asset_types = set(profile.get("asset_types", ()))
    profile_keywords = tuple(keyword.lower() for keyword in profile.get("keywords", ()))
    seed_symbols = {symbol.upper() for symbol in profile.get("seed_symbols", ())}

    candidates: list[tuple[str, float]] = []
    for universe_row in _heatmap_symbol_universe_rows():
        symbol = universe_row.get("symbol", "").strip().upper()
        if not symbol or universe_row.get("is_active", "").lower() == "false":
            continue
        is_seed = symbol in seed_symbols
        market = universe_row.get("market", "").strip()
        asset_type = universe_row.get("asset_type", "").strip()
        sector = universe_row.get("sector", "").strip()
        theme = universe_row.get("theme", "").strip()
        if not is_seed and profile_markets and market not in profile_markets:
            continue
        if not is_seed and profile_asset_types and asset_type not in profile_asset_types:
            continue

        score = 0.0
        if is_seed:
            score += 5.4
        if sector in profile_sectors:
            score += 2.7
        if theme in profile_themes:
            score += 2.0
        if market in profile_markets:
            score += 0.55
        if asset_type in profile_asset_types:
            score += 0.45
        score += _HEATMAP_MARKET_CAP_WEIGHTS.get(universe_row.get("market_cap_tier", ""), 0.0)
        score += _heatmap_keyword_match_score(universe_row, profile_keywords)
        score += _heatmap_universe_quality_score(universe_row)
        if score >= 3.05 or is_seed:
            candidates.append((symbol, round(score, 3)))

    candidates.sort(
        key=lambda item: (
            item[1] + _stable_heatmap_symbol_offset(category, item[0]),
            item[0],
        ),
        reverse=True,
    )
    return candidates[:96]


def _heatmap_keyword_match_score(
    universe_row: dict[str, str],
    profile_keywords: tuple[str, ...],
) -> float:
    if not profile_keywords:
        return 0.0
    search_text = " ".join(
        (
            universe_row.get("symbol", ""),
            universe_row.get("name", ""),
            universe_row.get("sector", ""),
            universe_row.get("theme", ""),
            universe_row.get("aliases", ""),
            universe_row.get("tags", ""),
            universe_row.get("index_family", ""),
        )
    ).lower()
    matches = sum(1 for keyword in profile_keywords if keyword and keyword in search_text)
    return min(2.2, matches * 0.55)


def _heatmap_universe_quality_score(universe_row: dict[str, str]) -> float:
    score = 0.0
    if universe_row.get("data_quality", "").upper() == "OK":
        score += 0.28
    if universe_row.get("tradability", "") == "tradable":
        score += 0.18
    if universe_row.get("is_sbi_supported", "").lower() == "true":
        score += 0.12
    if universe_row.get("risk_band", "").upper() == "HIGH":
        score -= 0.14
    return score


def _stable_heatmap_symbol_offset(category: str, symbol: str) -> float:
    seed = f"{category}:{symbol}"
    ordinal_sum = sum((index + 1) * ord(character) for index, character in enumerate(seed))
    return (ordinal_sum % 1000) / 10000.0


def _stable_heatmap_symbol_unit(category: str, symbol: str) -> float:
    seed = f"{category}:{symbol}"
    ordinal_sum = sum((index + 1) * ord(character) for index, character in enumerate(seed))
    return ((ordinal_sum % 2001) / 1000.0) - 1.0


def _stock_heatmap_tile(
    symbol: str,
    row: dict[str, object],
    tile_index: int,
    symbol_score: float,
    symbol_sentiment: float = 0.0,
) -> dict[str, object]:
    base_change = _coerce_float(row.get("値動きスコア"), 0.0)
    offset = _HEATMAP_TILE_OFFSETS[tile_index % len(_HEATMAP_TILE_OFFSETS)]
    direction = -1.0 if base_change < -0.25 else 1.0
    score_boost = min(0.55, max(0.0, symbol_score - 4.2) * 0.06)
    symbol_dispersion = _stable_heatmap_symbol_unit("tile-change", symbol) * 0.35
    sentiment_shift = max(-1.0, min(1.0, symbol_sentiment)) * 0.9
    change = round(
        max(
            -3.0,
            min(
                3.0,
                base_change * 0.72
                + offset * 0.45
                + sentiment_shift
                + symbol_dispersion
                + direction * score_boost,
            ),
        ),
        1,
    )
    inferred = str(row.get("市場指標")) != "市場データ"
    display_name, full_name = _stock_heatmap_tile_names(symbol)
    display_name = _stock_heatmap_tile_display_name(display_name, symbol, tile_index)
    market_cap_tier = _stock_heatmap_market_cap_tier(symbol)
    market_cap_label = _stock_heatmap_market_cap_label(market_cap_tier)
    area_score = _stock_heatmap_area_score(
        symbol_score=symbol_score,
        change=change,
        market_cap_tier=market_cap_tier,
    )
    span_cols, span_rows = _stock_heatmap_tile_spans(area_score, tile_index)
    size = _stock_heatmap_tile_size(span_cols, span_rows)
    factors_label = _stock_heatmap_tile_factors_label(
        change_label=_price_change_label(change, inferred=inferred),
        market_cap_label=market_cap_label,
        symbol_score=symbol_score,
    )
    label_parts = [symbol]
    if full_name:
        label_parts.append(full_name)
    label_parts.append(f"面積根拠: {factors_label}")
    label = " / ".join(label_parts)
    return {
        "symbol": symbol,
        "name": display_name,
        "full_name": full_name,
        "label": label,
        "href": news_dashboard_cockpit_href(symbol),
        "change": change,
        "change_label": _price_change_label(change, inferred=inferred),
        "score": round(symbol_score, 2),
        "factors_label": factors_label,
        "area_score": round(area_score, 2),
        "span_cols": span_cols,
        "span_rows": span_rows,
        "color_style": _stock_heatmap_tile_color_style(symbol, change),
        "tone": _stock_heatmap_tone(change),
        "size": size,
    }


def _stock_heatmap_tile_names(symbol: str) -> tuple[str, str]:
    normalized_symbol = symbol.strip().upper()
    short_name = _HEATMAP_SYMBOL_SHORT_NAMES.get(normalized_symbol)
    name = _heatmap_symbol_names().get(normalized_symbol)
    if name is None:
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


def _stock_heatmap_tile_display_name(display_name: str, symbol: str, tile_index: int) -> str:
    name = display_name or symbol
    if tile_index == 0:
        max_chars = 20
    elif tile_index <= 2:
        max_chars = 18
    elif tile_index <= 5:
        max_chars = 16
    else:
        max_chars = 12
    return truncate_text(name, max_chars=max_chars)


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


def _stock_heatmap_group_balance_label(tiles: list[dict[str, object]]) -> str:
    positive = 0
    negative = 0
    neutral = 0
    for tile in tiles:
        change = _coerce_float(tile.get("change"), 0.0)
        if change >= 0.35:
            positive += 1
        elif change <= -0.35:
            negative += 1
        else:
            neutral += 1
    if positive and negative:
        if positive > negative:
            return "上昇・銘柄差"
        if negative > positive:
            return "下降・銘柄差"
        return "まちまち"
    if positive:
        return "上昇・一方向"
    if negative:
        return "下降・一方向"
    if neutral:
        return "中立中心"
    return "方向感未確認"


def _stock_heatmap_market_cap_tier(symbol: str) -> str:
    row = _heatmap_symbol_universe_by_symbol().get(symbol.strip().upper(), {})
    tier = row.get("market_cap_tier", "").strip().lower()
    return tier if tier in _HEATMAP_MARKET_CAP_AREA_WEIGHTS else ""


def _stock_heatmap_market_cap_label(market_cap_tier: str) -> str:
    return _HEATMAP_MARKET_CAP_LABELS.get(market_cap_tier, "規模不明")


def _stock_heatmap_area_score(
    *,
    symbol_score: float,
    change: float,
    market_cap_tier: str,
) -> float:
    cap_weight = _HEATMAP_MARKET_CAP_AREA_WEIGHTS.get(market_cap_tier, 1.0)
    change_weight = min(3.0, abs(change)) * 0.75
    attention_weight = max(0.0, symbol_score) * 0.62
    return round(attention_weight + cap_weight + change_weight, 3)


def _stock_heatmap_tile_factors_label(
    *,
    change_label: str,
    market_cap_label: str,
    symbol_score: float,
) -> str:
    return f"{change_label} / {market_cap_label} / 注目{symbol_score:.1f}"


def _stock_heatmap_tile_spans(area_score: float, tile_index: int) -> tuple[int, int]:
    if area_score >= 14.0:
        spans = (3, 3)
    elif area_score >= 12.5:
        spans = (3, 2)
    elif area_score >= 10.5:
        spans = (2, 2)
    elif area_score >= 8.5:
        spans = (2, 1)
    else:
        spans = (1, 1)
    return _stock_heatmap_tile_span_cap(spans, tile_index)


def _stock_heatmap_tile_span_cap(spans: tuple[int, int], tile_index: int) -> tuple[int, int]:
    span_cols, span_rows = spans
    if tile_index == 0:
        return span_cols, span_rows
    if tile_index <= 3:
        return min(span_cols, 3), min(span_rows, 2)
    if tile_index <= 5:
        return min(span_cols, 2), min(span_rows, 2)
    if tile_index <= 7:
        return min(span_cols, 2), min(span_rows, 1)
    return 1, 1


def _stock_heatmap_tile_size(span_cols: int, span_rows: int) -> str:
    if span_cols >= 3 and span_rows >= 3:
        return "hero"
    if span_cols >= 3 or span_rows >= 2:
        return "major"
    if span_cols >= 2 and span_rows >= 2:
        return "medium"
    if span_cols >= 2:
        return "compact"
    return "minor"


def _stock_heatmap_tile_color_style(symbol: str, change: float) -> str:
    offset = _stable_heatmap_symbol_offset("tile-color", symbol)
    strength = min(3.0, abs(change)) / 3.0
    if change > 0.25:
        hue = 166 + int(offset * 36)
        saturation = 62 + int(strength * 18)
        lightness = 28 + int(strength * 12) + int(offset * 4)
        border_hue = 170
    elif change < -0.25:
        hue = 340 + int(offset * 28)
        saturation = 62 + int(strength * 16)
        lightness = 26 + int(strength * 10) + int(offset * 4)
        border_hue = 350
    else:
        hue = 214 + int(offset * 20)
        saturation = 34 + int(strength * 14)
        lightness = 24 + int(offset * 5)
        border_hue = 210
    dark_lightness = max(13, lightness - 18)
    return (
        f"--heatmap-tile-bg: linear-gradient(145deg, "
        f"hsl({hue} {saturation}% {lightness}%), "
        f"hsl({hue} {max(45, saturation - 10)}% {dark_lightness}%)); "
        f"--heatmap-tile-border: hsla({border_hue}, 88%, 78%, 0.58);"
    )


def _stock_heatmap_group_class(group_index: int, heat_score: float) -> str:
    if group_index < 2 or heat_score >= 4.5:
        return "mega"
    if group_index < 5 or heat_score >= 3.2:
        return "large"
    return "medium"


def _stock_heatmap_group_html(group: dict[str, object]) -> str:
    category = html.escape(str(group["category"]))
    metric_source = html.escape(str(group["metric_source"]))
    summary_label = html.escape(str(group["summary_label"]))
    group_class = html.escape(str(group["group_class"]))
    tiles_raw = group.get("tiles")
    tiles = cast(list[dict[str, object]], tiles_raw) if isinstance(tiles_raw, list) else []
    tile_html = "".join(_stock_heatmap_tile_html(tile) for tile in tiles)
    count_class = f"count-{min(len(tiles), 12)}"
    return (
        f'<article class="investment-stock-heatmap-group {group_class} {count_class}">'
        '<header class="investment-stock-heatmap-group-header">'
        f'<span class="investment-stock-heatmap-group-title">{category}</span>'
        f'<span class="investment-stock-heatmap-group-meta">{metric_source} / {summary_label}</span>'
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
    factors_label = html.escape(str(tile["factors_label"]))
    tone = html.escape(str(tile["tone"]))
    size = html.escape(str(tile["size"]))
    span_cols = _coerce_int(tile.get("span_cols"), 1)
    span_rows = _coerce_int(tile.get("span_rows"), 1)
    color_style = str(tile.get("color_style", ""))
    style = html.escape(
        f"grid-column: span {span_cols}; grid-row: span {span_rows}; {color_style}",
        quote=True,
    )
    primary_name = name or symbol
    symbol_html = f'<span class="investment-stock-heatmap-symbol">{symbol}</span>' if name else ""
    return (
        f'<a class="investment-stock-heatmap-tile {tone} {size}" '
        f'href="{href}" target="_self" title="{label}" aria-label="{label}" style="{style}">'
        '<span class="investment-stock-heatmap-identity">'
        f'<span class="investment-stock-heatmap-name">{primary_name}</span>'
        f"{symbol_html}"
        "</span>"
        f'<span class="investment-stock-heatmap-change">{change_label}</span>'
        f'<span class="investment-stock-heatmap-factors">{factors_label}</span>'
        "</a>"
    )


def _coerce_float(value: object, fallback: float) -> float:
    if not isinstance(value, (int, float, str)):
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_int(value: object, fallback: int) -> int:
    if not isinstance(value, (int, float, str)):
        return fallback
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def news_symbol_handoff_label(
    symbol: str,
    *,
    symbol_name_map: dict[str, str] | None = None,
) -> str:
    """Return a symbol handoff label with known company name."""

    normalized = symbol.strip().upper()
    if symbol_name_map is not None:
        name = symbol_name_map.get(normalized)
        if name and name.strip().upper() != normalized:
            return f"{normalized} / {name}"
        return normalized
    try:
        name = symbol_name(normalized)
    except OSError:
        name = None
    if name and name.strip().upper() != normalized:
        return f"{normalized} / {name}"
    return normalized


def _load_dashboard_snapshot() -> tuple[NewsDashboardSnapshot, NewsUpdateStatus]:
    status = load_news_update_status()
    snapshot = load_cached_news_dashboard_snapshot()
    if snapshot is not None:
        return snapshot, status
    return build_demo_news_dashboard_snapshot(), status


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


def _render_update_warning(status: NewsUpdateStatus) -> None:
    if status.last_error_type:
        st.warning(
            "ニュース更新で確認が必要な状態です。前回保存データまたはデモ表示を使っています。"
        )


def _render_news_detail_filters(
    snapshot: NewsDashboardSnapshot,
) -> NewsDashboardSnapshot:
    options = news_dashboard_filter_options(snapshot)
    relation_labels = {
        "all": "すべて",
        "direct": "本文に出た銘柄あり",
        "inferred": "SMAI推測候補あり",
        "none": "関連銘柄なし",
    }
    with st.expander("ニュース詳細フィルタ", expanded=False):
        col_category, col_freshness, col_relation, col_source = st.columns([1.2, 0.9, 1.0, 1.2])
        with col_category:
            categories = st.multiselect(
                "カテゴリ",
                options["categories"],
                default=[],
                key="investment_news_filter_categories",
            )
        with col_freshness:
            freshness = st.multiselect(
                "鮮度",
                options["freshness"],
                default=[],
                format_func=_freshness_label,
                key="investment_news_filter_freshness",
            )
        with col_relation:
            relation_filter = st.selectbox(
                "関連銘柄",
                list(relation_labels),
                format_func=lambda value: relation_labels.get(value, str(value)),
                key="investment_news_filter_relation",
            )
        with col_source:
            sources = st.multiselect(
                "source",
                options["sources"],
                default=[],
                key="investment_news_filter_sources",
            )

        watch_col, priority_col, only_col = st.columns([1.8, 0.8, 0.8])
        with watch_col:
            watchlist_value = st.text_input(
                "Watchlist",
                key=NEWS_DASHBOARD_WATCHLIST_STATE_KEY,
                placeholder="NVDA, 7203.T, GLD",
            )
        with priority_col:
            prioritize_watchlist = st.checkbox(
                "Watchlist一致を優先表示",
                value=True,
                key="investment_news_filter_watchlist_priority",
            )
        with only_col:
            watchlist_only = st.checkbox(
                "Watchlist一致だけ表示",
                value=False,
                key="investment_news_filter_watchlist_only",
            )

        watchlist_symbols = parse_news_watchlist_symbols(watchlist_value)
        filtered_snapshot = news_dashboard_filtered_snapshot(
            snapshot,
            categories=categories,
            freshness=freshness,
            relation_filter=relation_filter or "all",
            sources=sources,
            watchlist_symbols=watchlist_symbols,
            watchlist_only=watchlist_only,
            prioritize_watchlist=prioritize_watchlist,
        )
        original_count = news_dashboard_unique_headline_count(snapshot)
        filtered_count = news_dashboard_unique_headline_count(filtered_snapshot)
        watchlist_note = (
            f" / Watchlist: {', '.join(watchlist_symbols)}" if watchlist_symbols else ""
        )
        st.caption(f"表示中ニュース: {filtered_count}件 / 全体 {original_count}件{watchlist_note}")
        return filtered_snapshot


def _render_news_stream(
    snapshot: NewsDashboardSnapshot,
    *,
    open_symbol_callback: OpenSymbolCallback,
    symbol_name_map: dict[str, str],
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
                symbol_name_map=symbol_name_map,
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
    symbol_name_map: dict[str, str],
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
                    symbol_name_map=symbol_name_map,
                    max_columns=1,
                )


def _render_symbol_handoff_buttons(
    card: NewsHeadlineCard,
    *,
    key_prefix: str,
    open_symbol_callback: OpenSymbolCallback,
    symbol_name_map: dict[str, str],
    max_columns: int = 3,
) -> None:
    groups = news_card_symbol_handoff_groups(card)
    if not groups:
        return
    for group_index, (caption, symbols) in enumerate(groups):
        _render_symbol_button_group(
            symbols,
            caption=caption,
            key_prefix=f"{key_prefix}_group_{group_index}",
            open_symbol_callback=open_symbol_callback,
            symbol_name_map=symbol_name_map,
            max_columns=max_columns,
        )


def _render_symbol_button_group(
    symbols: list[str],
    *,
    caption: str,
    key_prefix: str,
    open_symbol_callback: OpenSymbolCallback,
    symbol_name_map: dict[str, str],
    max_columns: int,
) -> None:
    st.caption(caption)
    cols = st.columns(min(max_columns, len(symbols)))
    for index, symbol in enumerate(symbols):
        label = news_symbol_handoff_label(symbol, symbol_name_map=symbol_name_map)
        with cols[index % len(cols)]:
            st.button(
                truncate_text(label, max_chars=34),
                key=f"investment_news_open_{key_prefix}_{symbol}",
                help=f"{label}を投資コックピットで確認します。",
                use_container_width=True,
                on_click=open_symbol_callback,
                args=(symbol,),
            )


def _news_symbol_name_map() -> dict[str, str]:
    try:
        return symbol_universe_name_map()
    except OSError:
        return {}


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
    items = "".join(_news_ticker_item_html(card) for card in cards)
    repeated_items = "".join(_news_ticker_item_html(card, aria_hidden=True) for card in cards)
    return (
        '<section class="investment-news-ticker" aria-label="market news stream">'
        f'<div class="investment-news-ticker-track">{items}{repeated_items}</div>'
        "</section>"
    )


def _news_ticker_item_html(card: NewsHeadlineCard, *, aria_hidden: bool = False) -> str:
    hidden_attr = ' aria-hidden="true"' if aria_hidden else ""
    return (
        f'<span class="investment-news-ticker-item"{hidden_attr}>'
        f'<span class="investment-news-ticker-category">{html.escape(card.category)}</span>'
        f'<span class="investment-news-ticker-title">{html.escape(card.title)}</span>'
        "</span>"
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
    local_value = value.astimezone(NEWS_DISPLAY_TIMEZONE)
    return f"{local_value.strftime('%Y-%m-%d %H:%M')} {NEWS_DISPLAY_TIMEZONE_LABEL}"


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
