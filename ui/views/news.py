from __future__ import annotations

import html
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import cast
from urllib.parse import quote

import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

import backend.news.sources as news_sources
from backend.news import (
    NewsCategoryLane,
    NewsDashboardSnapshot,
    NewsHeadlineCard,
    NewsUpdateStatus,
    RadarCandidate,
    RadarCandidateDataStatus,
    RadarCandidateMap,
    RadarEvidenceBundle,
    RadarInterpretationResult,
    build_demo_news_dashboard_snapshot,
    build_radar_candidate_map,
    build_radar_evidence_bundle,
    build_radar_interpretation_from_settings,
    build_radar_research_context,
    build_standard_news_dashboard_snapshot,
    filter_radar_candidates,
    load_cached_news_dashboard_snapshot,
    load_news_update_status,
    refresh_news_dashboard_cache,
)
from backend.news.radar_market import RadarMarketSnapshot, RadarMarketTile
from ui.components.mascot import (
    render_page_title,
    workflow_loading_headlines_from_cache,
    workflow_loading_html,
)
from ui.favorites import (
    evaluate_favorite_refresh_status,
    is_favorite,
    load_favorites,
    render_favorite_button,
)
from ui.notification_center import START_PROFILE_QUERY_KEY
from ui.styles import truncate_text
from ui.symbol_universe import symbol_name, symbol_universe_csv_rows, symbol_universe_name_map
from ui.user_data import current_user_id

OpenSymbolCallback = Callable[[str], None]
MarketSnapshotCallback = Callable[[Sequence[RadarCandidate], int], RadarMarketSnapshot]

NEWS_DASHBOARD_REFRESH_STATE_KEY = "investment_news_dashboard_refresh_message"
NEWS_DASHBOARD_WATCHLIST_STATE_KEY = "investment_news_watchlist_symbols"
NEWS_COCKPIT_QUERY_PAGE_PARAM = "smai_page"
NEWS_COCKPIT_QUERY_SYMBOL_PARAM = "smai_symbol"
NEWS_COCKPIT_QUERY_COCKPIT_VALUE = "cockpit"
NEWS_DIRECT_SYMBOL_DISPLAY_LIMIT = 8
NEWS_INFERRED_SYMBOL_DISPLAY_LIMIT = 3
NEWS_MARKET_PROXY_SYMBOL_DISPLAY_LIMIT = 5
NEWS_SYMBOL_DISPLAY_TOTAL_LIMIT = 8
NEWS_DISPLAY_TIMEZONE = ZoneInfo("Asia/Tokyo")
NEWS_DISPLAY_TIMEZONE_LABEL = "JST"
NEWS_FEATURED_HEADLINE_LIMIT = 3
NEWS_RADAR_CANDIDATE_STATE_KEY = "investment_radar_selected_candidate_id"
NEWS_RADAR_CANDIDATE_DIALOG_REQUEST_STATE_KEY = "investment_radar_candidate_detail_request_id"
NEWS_RADAR_EVIDENCE_BUNDLES_STATE_KEY = "investment_radar_evidence_bundles"
NEWS_RADAR_INTERPRETATIONS_STATE_KEY = "investment_radar_interpretations"
NEWS_RADAR_SESSION_OWNER_STATE_KEY = "investment_radar_session_owner_user_id"
NEWS_RADAR_CANDIDATE_INITIAL_LANE_LIMIT = 4
NEWS_RADAR_CANDIDATE_QUICK_DIRECT_ONLY_KEY = "investment_radar_candidate_quick_direct_only"
NEWS_RADAR_CANDIDATE_QUICK_WATCHLIST_ONLY_KEY = "investment_radar_candidate_quick_watchlist_only"
NEWS_RADAR_CANDIDATE_QUICK_UNCHECKED_ONLY_KEY = "investment_radar_candidate_quick_unchecked_only"
NEWS_RADAR_TRIAGE_PROVENANCE_STATE_KEY = "investment_radar_candidate_triage_provenance"
NEWS_RADAR_TRIAGE_PRIORITY_STATE_KEY = "investment_radar_candidate_triage_priority"
NEWS_RADAR_MARKET_SNAPSHOT_STATE_KEY = "investment_radar_market_snapshot"
NEWS_RADAR_MARKET_PERIOD_STATE_KEY = "investment_radar_market_period"

_FRESHNESS_LABELS = {
    "latest": "最新",
    "recent": "近日",
    "stale": "古め",
    "unknown": "未確認",
}

_RADAR_PROVENANCE_LABELS = {
    "direct_mention": "本文に出た銘柄",
    "inferred_candidate": "SMAI推測候補",
    "macro_proxy": "市場背景の確認",
}
_RADAR_PROVENANCE_GUIDANCE = {
    "direct_mention": "記事本文または見出しに明示された銘柄です。まず根拠記事を確認します。",
    "inferred_candidate": "ニュースのテーマからの関連候補です。記事に銘柄名が出たとは限りません。",
    "macro_proxy": "個別銘柄候補ではなく、市場全体の背景を確認するための指標です。",
}
_RADAR_MATERIAL_TONE_LABELS = {
    "positive": "好材料を含む",
    "caution": "注意材料を含む",
    "mixed": "材料が混在",
    "unknown": "材料の方向は未確認",
}
_RADAR_DATA_STATUS_LABELS = {
    "available": "確認可能",
    "partial": "一部確認",
    "unavailable": "未取得",
    "not_checked": "未確認",
}
_RADAR_TRIAGE_PRIORITY_LABELS = {
    "first": "先に確認",
    "next": "次に確認",
    "as_needed": "必要に応じて",
}

# Keep this display-only compatibility data alongside the Radar copy.  A
# Streamlit page reload can pick up this module while retaining an already
# imported RadarCandidate class from the previous process revision.
_RADAR_PRIORITY_FRESHNESS_POINTS = {
    "latest": 40,
    "recent": 28,
    "stale": 12,
    "unknown": 6,
}
_RADAR_PRIORITY_MATERIAL_POINTS = {
    "risk": 12,
    "earnings": 10,
    "policy": 8,
    "macro": 7,
    "shareholder_return": 6,
    "theme": 6,
    "fund_flow": 4,
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
    # Material taxonomy is not a validated positive/negative reading of the
    # headline. Keep the news surface neutral or attention-oriented until a
    # separate evidence-grounded direction contract exists.
    "earnings": "news",
    "fund_flow": "news",
    "macro": "news",
    "policy": "news",
    "risk": "news",
    "shareholder_return": "news",
    "theme": "news",
}

_HEATMAP_GROUP_KIND_LABELS = {
    "market": "市場",
    "asset_class": "資産クラス",
    "theme": "テーマ",
    "macro": "マクロ",
    "event": "イベント",
}

_HEATMAP_CATEGORY_GROUP_KINDS = {
    "日本株": "market",
    "米国株": "market",
    "アジア株": "market",
    "ETF": "asset_class",
    "ETF・投信": "asset_class",
    "REIT": "asset_class",
    "為替・金利": "macro",
    "地政学・マクロリスク": "macro",
    "指数・市場心理": "macro",
    "地政学・資源価格": "macro",
    "決算・業績修正": "event",
    "資金フロー": "event",
    "大型ニュース反応": "event",
}

_NEWS_MARKET_PROXY_LABELS = {
    "1306.T": "TOPIX ETF",
    "1488.T": "東証REIT ETF",
    "GLD": "金ETF",
    "QQQ": "NASDAQ100 ETF",
    "SPY": "S&P500 ETF",
    "TLT": "米国債ETF",
    "USDJPY": "ドル円",
    "US10Y": "米10年金利",
    "VTI": "全米株ETF",
    "XLE": "エネルギーETF",
}

_HEATMAP_MARKET_CAP_WEIGHTS = {
    "mega": 1.4,
    "large": 1.0,
    "mid": 0.52,
    "small": 0.22,
    "micro": 0.02,
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


def _clear_news_radar_user_transient_state() -> None:
    """Clear page-local transient state when the active local user changes."""

    removable_keys = (
        NEWS_DASHBOARD_REFRESH_STATE_KEY,
        NEWS_DASHBOARD_WATCHLIST_STATE_KEY,
        "investment_news_watchlist_source",
    )
    for key in tuple(st.session_state):
        name = str(key)
        if (
            name.startswith("investment_radar_")
            or name.startswith("investment_news_filter_")
            or name in removable_keys
        ):
            st.session_state.pop(key, None)


def _ensure_news_radar_user_scope() -> None:
    """Prevent one local profile's transient Radar state from appearing in another."""

    active_user_id = current_user_id() or "default"
    if st.session_state.get(NEWS_RADAR_SESSION_OWNER_STATE_KEY) == active_user_id:
        return
    _clear_news_radar_user_transient_state()
    st.session_state[NEWS_RADAR_SESSION_OWNER_STATE_KEY] = active_user_id


def render_news_dashboard_page(
    *,
    open_symbol_callback: OpenSymbolCallback,
    market_snapshot_callback: MarketSnapshotCallback,
) -> None:
    """Render the Investment Radar dashboard MVP."""

    _ensure_news_radar_user_scope()
    snapshot, status = _load_dashboard_snapshot()
    render_page_title(
        "投資レーダー",
        "市場ニュースとテーマから、根拠を確認する候補を整理します。",
        "investment_radar",
        accessory_html=news_dashboard_freshness_badge_html(snapshot),
    )

    _render_refresh_controls()
    _render_status_message()
    _render_update_warning(status)
    symbol_name_map = _news_symbol_name_map()
    today_candidate_map = _radar_candidate_map_for_snapshot(snapshot)
    today_tab, market_tab, evidence_tab, news_tab = st.tabs(
        ["今日のレーダー", "市場ヒートマップ", "ニュース・根拠", "ニュース一覧"]
    )
    with today_tab:
        _render_radar_today_summary(today_candidate_map)
        _render_heatmap(snapshot)
    with market_tab:
        _render_market_heatmap(
            today_candidate_map,
            market_snapshot_callback=market_snapshot_callback,
        )
    with evidence_tab:
        filtered_snapshot = _render_news_detail_filters(snapshot)
        candidate_map = _radar_candidate_map_for_snapshot(filtered_snapshot)
        _render_radar_candidate_map(candidate_map)
        _render_requested_radar_candidate_detail(
            candidate_map.candidates,
            as_of=filtered_snapshot.generated_at.date(),
            open_symbol_callback=open_symbol_callback,
        )
    with news_tab:
        st.caption("「ニュース・根拠」タブの探索条件を共有して表示します。")
        _render_news_stream(filtered_snapshot)
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
    """Return classified category groups for the stock heatmap view."""

    if max_groups <= 0 or max_tiles_per_group <= 0:
        return []
    frame = news_dashboard_heatmap_frame(snapshot)
    if frame.empty:
        return []
    lanes_by_category = {lane.category: lane for lane in snapshot.category_lanes}
    groups: list[dict[str, object]] = []
    sorted_frame = frame.sort_values("加熱度", ascending=False)
    for group_index, row in enumerate(sorted_frame.to_dict("records")):
        category = str(row["投資カテゴリ"])
        lane = lanes_by_category.get(category)
        symbol_scores = _heatmap_group_symbol_scores(
            category,
            lane.headlines if lane else [],
            row,
            max_tiles_per_group,
        )
        if not symbol_scores:
            # A macro-only category remains available in the separate market
            # background lane. Do not invent a cockpit-linked tile without a
            # direct or inferred symbol in the displayed evidence.
            continue
        evidence_details = _heatmap_group_symbol_evidence_details(lane.headlines if lane else [])
        symbol_scores = sorted(
            symbol_scores,
            key=lambda item: (
                _coerce_int(evidence_details.get(item[0], {}).get("evidence_count"), 0),
                _coerce_int(evidence_details.get(item[0], {}).get("source_count"), 0),
                item[1],
                item[0],
            ),
            reverse=True,
        )
        tiles = [
            _stock_heatmap_tile(
                symbol,
                row,
                tile_index,
                symbol_score,
                evidence_details.get(symbol, {}),
            )
            for tile_index, (symbol, symbol_score) in enumerate(symbol_scores)
        ]
        _apply_stock_heatmap_tile_layout(tiles)
        balance_label = _stock_heatmap_group_balance_label(
            tiles,
            market_measured=str(row["市場指標"]) == "市場データ",
        )
        groups.append(
            {
                "category": category,
                "group_kind": news_dashboard_heatmap_group_kind(category),
                "group_kind_label": news_dashboard_heatmap_group_kind_label(category),
                "region": str(row["分野"]),
                "metric_source": str(row["市場指標"]),
                "heat_score": row["加熱度"],
                "group_class": _stock_heatmap_group_class(group_index, float(row["加熱度"])),
                "summary_label": f'{row["値動き表示"]} / {balance_label}',
                "tiles": tiles,
            }
        )
        if len(groups) >= max_groups:
            break
    return groups


def news_dashboard_heatmap_group_kind(category: str) -> str:
    """Return the display classification for an Investment Radar category."""

    return _HEATMAP_CATEGORY_GROUP_KINDS.get(category.strip(), "theme")


def news_dashboard_heatmap_group_kind_label(category: str) -> str:
    """Return the beginner-friendly classification badge text."""

    return _HEATMAP_GROUP_KIND_LABELS[news_dashboard_heatmap_group_kind(category)]


def news_dashboard_stock_heatmap_html(
    snapshot: NewsDashboardSnapshot,
    *,
    max_groups: int = 12,
    max_tiles_per_group: int = 8,
    include_topline: bool = True,
    start_group: int = 0,
) -> str:
    """Return a classified stock heatmap HTML surface."""

    all_groups = news_dashboard_stock_heatmap_groups(
        snapshot,
        max_groups=999,
        max_tiles_per_group=max_tiles_per_group,
    )
    bounded_start = max(0, start_group)
    groups = all_groups[bounded_start : bounded_start + max_groups]
    if not groups:
        return ""
    tile_count = sum(_stock_heatmap_group_tile_count(group) for group in groups)
    hidden_group_count = max(0, len(all_groups) - bounded_start - len(groups))
    has_category_market_data = any(str(group["metric_source"]) == "市場データ" for group in groups)
    group_html = "".join(_stock_heatmap_group_html(group) for group in groups)
    more_themes = (
        f'<span class="investment-stock-heatmap-more">ほか {hidden_group_count}テーマ</span>'
        if hidden_group_count
        else ""
    )
    category_market_note = (
        '<span class="investment-stock-heatmap-legend market-metric">'
        "カテゴリ市場データは見出しのみ"
        "</span>"
        if has_category_market_data
        else ""
    )
    topline = (
        '<div class="investment-stock-heatmap-topline">'
        '<span class="investment-stock-heatmap-read">'
        f"表示: {len(groups)}カテゴリ / {tile_count}銘柄タイル。"
        "面積は重複を除いた根拠記事数、色は鮮度の目安です。"
        "</span>"
        f"{more_themes}"
        '<span class="investment-stock-heatmap-click">コックピット連携</span>'
        '<span class="investment-stock-heatmap-legend evidence">面積: 根拠記事数</span>'
        '<span class="investment-stock-heatmap-legend freshness">色: 古い→最新</span>'
        '<span class="investment-stock-heatmap-legend direct">本文に出た</span>'
        '<span class="investment-stock-heatmap-legend inferred">テーマ関連</span>'
        '<span class="investment-stock-heatmap-legend neutral">タイルの価格方向: 未確認</span>'
        f"{category_market_note}"
        "</div>"
        if include_topline
        else ""
    )
    return (
        '<section class="investment-stock-heatmap" aria-label="investment theme map">'
        f"{topline}"
        f'<div class="investment-stock-heatmap-board">{group_html}</div>'
        "</section>"
    )


def news_dashboard_cockpit_href(symbol: str) -> str:
    """Return the same-app URL used to open a heatmap symbol in the cockpit."""

    normalized = symbol.strip().upper()
    encoded_symbol = quote(normalized, safe="")
    query_parts: list[tuple[str, str]] = []
    current_user_id = str(st.session_state.get("smai_current_user_id") or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", current_user_id):
        query_parts.append((START_PROFILE_QUERY_KEY, quote(current_user_id, safe="")))
    query_parts.extend(
        (
            (NEWS_COCKPIT_QUERY_PAGE_PARAM, NEWS_COCKPIT_QUERY_COCKPIT_VALUE),
            (NEWS_COCKPIT_QUERY_SYMBOL_PARAM, encoded_symbol),
        )
    )
    return "?" + "&".join(f"{key}={value}" for key, value in query_parts)


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


def news_card_market_proxy_symbols(
    card: NewsHeadlineCard,
    *,
    limit: int = NEWS_MARKET_PROXY_SYMBOL_DISPLAY_LIMIT,
) -> list[str]:
    """Return market proxy indicators separately from cockpit handoff symbols."""

    direct_symbols, inferred_symbols = _card_handoff_symbol_groups(card)
    return _unique_normalized_symbols(
        getattr(card, "macro_proxy_symbols", []),
        exclude={*direct_symbols, *inferred_symbols},
    )[: max(0, limit)]


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
    exclude_top_headlines: int = 3,
) -> list[tuple[int, int, str, NewsHeadlineCard]]:
    """Return bounded category lane cards for the responsive lane grid."""

    items: list[tuple[int, int, str, NewsHeadlineCard]] = []
    excluded = {
        _news_headline_identity(card)
        for card in snapshot.stream_headlines[: max(0, exclude_top_headlines)]
    }
    for lane_index, lane in enumerate(snapshot.category_lanes[:max_lanes]):
        displayed_count = 0
        for card_index, card in enumerate(lane.headlines):
            if _news_headline_identity(card) in excluded:
                continue
            items.append((lane_index, card_index, lane.category, card))
            displayed_count += 1
            if displayed_count >= max_cards_per_lane:
                break
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


def _news_headline_identity(card: NewsHeadlineCard) -> str:
    url = (card.url or "").strip().lower()
    if url:
        return re.sub(r"[?#].*$", "", url)
    title = re.sub(r"\s+", " ", card.title.strip().lower())
    return f"{card.category.strip().lower()}|{title}"


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


def combine_news_watchlist_symbols(
    manual_symbols: Sequence[str],
    favorite_symbols: Sequence[str],
    *,
    source: str,
) -> list[str]:
    """Return watchlist symbols for Investment Radar without changing stored favorites."""

    if source == "manual_watchlist":
        candidates = manual_symbols
    elif source == "favorites_watchlist":
        candidates = favorite_symbols
    else:
        candidates = [*favorite_symbols, *manual_symbols]
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in candidates:
        cleaned = symbol.strip().upper()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


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
    market_measured = (
        getattr(cell, "market_metric_source", "news_proxy") == "market_measured"
        and actual_price_change_pct is not None
        and actual_volume_activity_score is not None
    )
    price_change_pct = actual_price_change_pct if market_measured else None
    volume_activity_score = actual_volume_activity_score if market_measured else None
    metric_source = "市場データ" if market_measured else "ニュース代理"
    region = getattr(cell, "region", None) or "全体"
    return {
        "カテゴリ": getattr(cell, "category"),
        "投資カテゴリ": getattr(cell, "category"),
        "地域": region,
        "分野": region,
        "加熱度": getattr(cell, "heat_score"),
        "市場指標": metric_source,
        "値動き": price_change_pct,
        "値動きスコア": price_change_pct if price_change_pct is not None else 0.0,
        "値動き表示": _price_change_label(
            price_change_pct,
            inferred=not market_measured,
        ),
        "取引量": volume_activity_score,
        "取引量スコア": volume_activity_score if volume_activity_score is not None else 1.0,
        "取引量目安": _volume_label(
            volume_activity_score,
            inferred=not market_measured,
        ),
        "ニュース件数": getattr(cell, "news_count"),
        "リスク材料": getattr(cell, "risk_count"),
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


def _float_attr(value: object, name: str) -> float:
    raw_value = getattr(value, name, 0.0)
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.0


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
    # Do not add category seed or symbol-universe entries here. A theme-map
    # tile must be traceable to the currently displayed news evidence; generic
    # related-symbol suggestions belong in a future, explicitly labelled view.
    ranked_symbols = sorted(
        scores.items(),
        key=lambda item: (
            item[1] + _stable_heatmap_symbol_offset(category, item[0]),
            item[0],
        ),
        reverse=True,
    )
    return ranked_symbols[:limit]


def _heatmap_group_symbol_evidence_details(
    cards: list[NewsHeadlineCard],
) -> dict[str, dict[str, object]]:
    """Collect display-only evidence facts for the visible theme-map tiles.

    A map tile may be large or visually prominent only because multiple
    displayed news cards support it.  Company size, category market metrics,
    and material taxonomy stay out of this presentation contract.
    """

    details: dict[str, dict[str, object]] = {}
    freshness_rank = {"unknown": 0, "stale": 1, "recent": 2, "latest": 3}
    for card in cards:
        card_key = _news_headline_dedupe_key(card)
        source_key = (card.source_name or card.source_type or "未確認").strip().lower()
        direct_symbols, inferred_symbols = _card_handoff_symbol_groups(card)
        for relation, symbols in (
            ("direct", direct_symbols),
            ("inferred", inferred_symbols),
        ):
            for symbol in symbols:
                normalized_symbol = symbol.strip().upper()
                if not normalized_symbol:
                    continue
                detail = details.setdefault(
                    normalized_symbol,
                    {
                        "evidence_keys": set(),
                        "source_keys": set(),
                        "freshness_rank": 0,
                        "has_direct_mention": False,
                    },
                )
                evidence_keys = cast(set[str], detail["evidence_keys"])
                source_keys = cast(set[str], detail["source_keys"])
                is_new_evidence = card_key not in evidence_keys
                evidence_keys.add(card_key)
                if is_new_evidence:
                    source_keys.add(source_key)
                detail["freshness_rank"] = max(
                    _coerce_int(detail["freshness_rank"], 0),
                    freshness_rank.get(card.freshness_status, 0),
                )
                if relation == "direct":
                    detail["has_direct_mention"] = True

    normalized_details: dict[str, dict[str, object]] = {}
    for symbol, detail in details.items():
        evidence_keys = cast(set[str], detail["evidence_keys"])
        source_keys = cast(set[str], detail["source_keys"])
        normalized_details[symbol] = {
            "evidence_count": len(evidence_keys),
            "source_count": len(source_keys),
            "freshness_rank": _coerce_int(detail["freshness_rank"], 0),
            "relationship": "direct" if bool(detail["has_direct_mention"]) else "inferred",
        }
    return normalized_details


def _news_headline_dedupe_key(card: NewsHeadlineCard) -> str:
    """Resolve the headline key across Streamlit partial module reloads.

    Streamlit can reload this UI module while retaining a previously imported
    ``backend.news.sources`` module. The helper was publicized from
    ``_headline_dedupe_key`` to ``news_headline_dedupe_key`` during the Radar
    update, so accept the immediately preceding private name until the server
    process has been fully restarted.
    """

    for helper_name in ("news_headline_dedupe_key", "_headline_dedupe_key"):
        helper = getattr(news_sources, helper_name, None)
        if callable(helper):
            return str(helper(card))
    if card.url:
        return re.sub(r"[?#].*$", "", card.url.strip()).casefold()
    normalized_title = re.sub(r"\s+", " ", card.title.strip()).casefold()
    return f"{card.category}|{normalized_title}"


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


def _stock_heatmap_tile(
    symbol: str,
    row: dict[str, object],
    tile_index: int,
    symbol_score: float,
    evidence_detail: Mapping[str, object] | None = None,
) -> dict[str, object]:
    # A heatmap cell has at most a category-level market metric. It must not
    # become a fabricated individual-symbol move or red/green tile. Individual
    # tile direction remains unknown until a per-symbol market-data contract is
    # supplied.
    change = 0.0
    inferred = True
    detail = evidence_detail or {}
    evidence_count = max(1, _coerce_int(detail.get("evidence_count"), 1))
    source_count = max(1, _coerce_int(detail.get("source_count"), 1))
    freshness_rank = min(3, max(0, _coerce_int(detail.get("freshness_rank"), 0)))
    relationship = (
        "direct" if str(detail.get("relationship", "inferred")) == "direct" else "inferred"
    )
    display_name, full_name = _stock_heatmap_tile_names(symbol)
    display_name = _stock_heatmap_tile_display_name(display_name, symbol, tile_index)
    area_score = _stock_heatmap_area_score(
        evidence_count=evidence_count,
        source_count=source_count,
    )
    span_cols, span_rows = _stock_heatmap_tile_spans(area_score, tile_index)
    size = _stock_heatmap_tile_size(span_cols, span_rows)
    factors_label = _stock_heatmap_tile_factors_label(
        evidence_count=evidence_count,
        source_count=source_count,
    )
    label_parts = [symbol]
    if full_name:
        label_parts.append(full_name)
    label_parts.append("本文に出た銘柄" if relationship == "direct" else "テーマ関連候補")
    label_parts.append(f"面積根拠: {factors_label}")
    label_parts.append("価格方向: 未確認")
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
        "evidence_count": evidence_count,
        "source_count": source_count,
        "freshness_rank": freshness_rank,
        "relationship": relationship,
        "relationship_label": "本文に出た" if relationship == "direct" else "テーマ関連",
        "area_score": round(area_score, 2),
        "span_cols": span_cols,
        "span_rows": span_rows,
        "color_style": _stock_heatmap_tile_color_style(
            symbol,
            change,
            non_directional=True,
            freshness_ratio=freshness_rank / 3.0,
        ),
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


def _stock_heatmap_group_balance_label(
    tiles: list[dict[str, object]],
    *,
    market_measured: bool,
) -> str:
    if not market_measured:
        return "ニュース上の注目度"
    # The category metric belongs to the header, not the individual tiles.
    del tiles
    return "カテゴリの市場指標"


def _stock_heatmap_area_score(
    *,
    evidence_count: int,
    source_count: int,
) -> float:
    """Return a display area derived only from the deduplicated evidence count."""

    # Source breadth is disclosed as supporting context on the tile, but must
    # not quietly change its area.  The map legend can therefore state the
    # precise visual contract: area equals deduplicated evidence count.
    del source_count
    return float(max(1, evidence_count))


def _stock_heatmap_tile_factors_label(
    *,
    evidence_count: int,
    source_count: int,
) -> str:
    if source_count > 1:
        return f"根拠{evidence_count}件・独立出典{source_count}件"
    return f"根拠{evidence_count}件"


def _stock_heatmap_tile_spans(area_score: float, tile_index: int) -> tuple[int, int]:
    if area_score >= 4.0:
        spans = (3, 3)
    elif area_score >= 3.0:
        spans = (3, 2)
    elif area_score >= 2.0:
        spans = (2, 2)
    elif area_score >= 1.5:
        spans = (2, 1)
    else:
        spans = (1, 1)
    return _stock_heatmap_tile_span_cap(spans, tile_index)


def _apply_stock_heatmap_tile_layout(tiles: list[dict[str, object]]) -> None:
    """Fill the compact board without inventing visual importance.

    The initial Radar surface intentionally shows at most three symbols per
    theme.  Equal evidence should therefore use equal area instead of leaving
    a mostly empty treemap.  A clearly larger evidence set keeps the familiar
    lead-tile hierarchy from the earlier map while its area remains traceable.
    """

    layout_spans: tuple[tuple[int, int], ...]
    if len(tiles) == 1:
        layout_spans = ((6, 5),)
    elif len(tiles) == 2:
        layout_spans = ((3, 5), (3, 5))
    elif len(tiles) == 3:
        area_scores = [_coerce_float(tile.get("area_score"), 1.0) for tile in tiles]
        lead_is_distinct = max(area_scores) >= min(area_scores) + 1.0
        layout_spans = ((3, 5), (3, 3), (3, 2)) if lead_is_distinct else ((2, 5), (2, 5), (2, 5))
    else:
        return

    for tile, (span_cols, span_rows) in zip(tiles, layout_spans):
        tile["span_cols"] = span_cols
        tile["span_rows"] = span_rows
        tile["size"] = _stock_heatmap_tile_size(span_cols, span_rows)


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
    if span_cols >= 3:
        return "major"
    if span_cols >= 2 and span_rows >= 2:
        return "medium"
    if span_cols >= 2:
        return "compact"
    return "minor"


def _stock_heatmap_tile_color_style(
    symbol: str,
    change: float,
    *,
    non_directional: bool = False,
    freshness_ratio: float = 0.0,
) -> str:
    if non_directional:
        # Freshness is exposed through a labelled CSS class so the visual
        # scale remains consistent across all tiles instead of drifting by
        # symbol-specific pseudo-random offsets.
        del symbol, change, freshness_ratio
        return ""
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
    group_kind = html.escape(str(group["group_kind"]))
    group_kind_label = html.escape(str(group["group_kind_label"]))
    meta = _stock_heatmap_group_meta_parts(
        str(group["metric_source"]),
        str(group["summary_label"]),
    )
    score = html.escape(meta["score"])
    badge = html.escape(meta["badge"])
    trend = html.escape(meta["trend"])
    tone = html.escape(meta["tone"])
    group_class = html.escape(str(group["group_class"]))
    tiles_raw = group.get("tiles")
    tiles = cast(list[dict[str, object]], tiles_raw) if isinstance(tiles_raw, list) else []
    tile_html = "".join(_stock_heatmap_tile_html(tile) for tile in tiles)
    count_class = f"count-{min(len(tiles), 12)}"
    trend_html = (
        f'<span class="investment-stock-heatmap-group-trend {tone}">{trend}</span>' if trend else ""
    )
    return (
        f'<article class="investment-stock-heatmap-group {group_class} {group_kind} {count_class}">'
        '<header class="investment-stock-heatmap-group-header">'
        '<div class="investment-stock-heatmap-group-main">'
        f'<span class="investment-stock-heatmap-group-title">{category}</span>'
        f'<span class="investment-stock-heatmap-group-score {tone}">{score}</span>'
        "</div>"
        '<div class="investment-stock-heatmap-group-sub">'
        f'<span class="investment-stock-heatmap-group-kind {group_kind}">'
        f"{group_kind_label}</span>"
        f'<span class="investment-stock-heatmap-group-badge">{badge}</span>'
        f"{trend_html}"
        "</div>"
        "</header>"
        f'<div class="investment-stock-heatmap-tiles">{tile_html}</div>'
        "</article>"
    )


def _stock_heatmap_group_meta_parts(
    metric_source: str,
    summary_label: str,
) -> dict[str, str]:
    if metric_source.strip() != "市場データ":
        return {
            "score": "方向未確認",
            "badge": "ニュース根拠",
            "trend": "",
            "tone": "neutral",
        }
    parts = [part.strip() for part in summary_label.split("/") if part.strip()]
    score = parts[0] if parts else "変化なし"
    trend = "個別タイルは方向未確認"
    tone = (
        "negative"
        if score.startswith("-")
        else ("positive" if score.startswith("+") else "neutral")
    )
    return {
        "score": score,
        "badge": "カテゴリ市場データ",
        "trend": trend,
        "tone": tone,
    }


def _stock_heatmap_group_tile_count(group: dict[str, object]) -> int:
    tiles = group.get("tiles")
    return len(tiles) if isinstance(tiles, list) else 0


def _stock_heatmap_tile_html(tile: dict[str, object]) -> str:
    symbol = html.escape(str(tile["symbol"]))
    name = html.escape(str(tile["name"]))
    label = html.escape(str(tile["label"]), quote=True)
    href = html.escape(str(tile["href"]), quote=True)
    factors_label = html.escape(str(tile["factors_label"]))
    relationship = html.escape(str(tile.get("relationship", "inferred")))
    relationship_label = html.escape(str(tile.get("relationship_label", "テーマ関連")))
    freshness_rank = min(3, max(0, _coerce_int(tile.get("freshness_rank"), 0)))
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
        f'<a class="investment-stock-heatmap-tile text-safe {tone} {relationship} '
        f'freshness-{freshness_rank} {size}" '
        f'href="{href}" target="_self" title="{label}" aria-label="{label}" style="{style}">'
        '<span class="investment-stock-heatmap-identity">'
        f'<span class="investment-stock-heatmap-name">{primary_name}</span>'
        f"{symbol_html}"
        "</span>"
        '<span class="investment-stock-heatmap-evidence-meta">'
        f'<span class="investment-stock-heatmap-evidence {relationship}">{relationship_label}</span>'
        f'<span class="investment-stock-heatmap-factors">{factors_label}</span>'
        "</span>"
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
    symbol_name_map: Mapping[str, str] | None = None,
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
    col_action, col_note = st.columns([1.05, 1.95])
    with col_action:
        st.markdown(
            '<div class="smai-news-refresh-action-anchor"></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "ニュース表示を更新",
            key="investment_news_refresh",
            type="primary",
            use_container_width=True,
        ):
            now = datetime.now(UTC)
            loading_slot = st.empty()
            loading_headlines, loading_headline_note = workflow_loading_headlines_from_cache()
            loading_slot.markdown(
                workflow_loading_html(
                    title="最新ニュースを更新中",
                    message="外部ニュースを取得し、重複を除いて確認材料に整理しています。",
                    current_step="外部ニュースRSSへ接続しています。",
                    progress=0.12,
                    mode="blocking",
                    headlines=loading_headlines,
                    headline_note=loading_headline_note,
                ),
                unsafe_allow_html=True,
            )
            try:
                result = refresh_news_dashboard_cache(
                    lambda: build_standard_news_dashboard_snapshot(
                        allow_network=True,
                        now=now,
                        fallback_to_demo=False,
                    ),
                    force=True,
                )
                loading_slot.markdown(
                    workflow_loading_html(
                        title="最新ニュースを更新中",
                        message="外部ニュースを取得し、重複を除いて確認材料に整理しています。",
                        current_step="ニュースを分類して表示を更新しています。",
                        progress=0.9,
                        mode="blocking",
                        headlines=loading_headlines,
                        headline_note=loading_headline_note,
                    ),
                    unsafe_allow_html=True,
                )
            finally:
                loading_slot.empty()
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

        watch_col, source_col, priority_col, only_col = st.columns([1.5, 1.0, 0.8, 0.8])
        with watch_col:
            watchlist_value = st.text_input(
                "Watchlist",
                key=NEWS_DASHBOARD_WATCHLIST_STATE_KEY,
                placeholder="NVDA, 7203.T, GLD",
            )
        favorite_watchlist = load_favorites()
        favorite_watchlist_symbols = [favorite.symbol for favorite in favorite_watchlist]
        with source_col:
            watchlist_source = st.selectbox(
                "Watchlist source",
                ["favorites_watchlist", "combined_watchlist", "manual_watchlist"],
                format_func=lambda value: {
                    "favorites_watchlist": "Myウォッチリスト",
                    "combined_watchlist": "My + 手入力",
                    "manual_watchlist": "手入力のみ",
                }.get(value, value),
                key="investment_news_watchlist_source",
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

        manual_watchlist_symbols = parse_news_watchlist_symbols(watchlist_value)
        watchlist_symbols = combine_news_watchlist_symbols(
            manual_watchlist_symbols,
            favorite_watchlist_symbols,
            source=watchlist_source,
        )
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
        if favorite_watchlist_symbols:
            refresh_states = [
                evaluate_favorite_refresh_status(favorite) for favorite in favorite_watchlist
            ]
            refresh_attention_count = sum(1 for state in refresh_states if state.status != "fresh")
            st.caption(
                "☆ Myウォッチリスト対象: "
                f"{len(favorite_watchlist_symbols)}銘柄 / "
                f"更新推奨 {refresh_attention_count}件 / "
                f"{', '.join(favorite_watchlist_symbols[:8])}"
            )
        st.caption(f"表示中ニュース: {filtered_count}件 / 全体 {original_count}件{watchlist_note}")
        return filtered_snapshot


def _render_news_stream(
    snapshot: NewsDashboardSnapshot,
) -> None:
    st.markdown("### 重要ニュース")
    featured = snapshot.stream_headlines[:NEWS_FEATURED_HEADLINE_LIMIT]
    if not featured:
        st.info("表示できるニュースはまだありません。")
        return
    st.markdown(_news_ticker_html(featured), unsafe_allow_html=True)


def radar_market_treemap_rectangles(
    tiles: Sequence[RadarMarketTile],
    *,
    width: float = 100.0,
    height: float = 56.0,
) -> list[tuple[RadarMarketTile, float, float, float, float]]:
    """Lay out proportional price-movement tiles with a squarified treemap."""

    if not tiles or width <= 0 or height <= 0:
        return []
    ordered = sorted(tiles, key=lambda item: (-item.magnitude_pct, item.symbol))
    raw_weights = [max(item.magnitude_pct, 0.25) for item in ordered]
    scale = (width * height) / sum(raw_weights)
    sizes = [value * scale for value in raw_weights]
    rectangles: list[tuple[RadarMarketTile, float, float, float, float]] = []

    def worst(row: list[float], side: float) -> float:
        if not row or side <= 0:
            return float("inf")
        total = sum(row)
        return max(
            (side * side * max(row)) / (total * total),
            (total * total) / (side * side * min(row)),
        )

    def place(
        row_tiles: list[RadarMarketTile],
        row_sizes: list[float],
        x: float,
        y: float,
        dx: float,
        dy: float,
    ) -> tuple[float, float, float, float]:
        total = sum(row_sizes)
        if dx >= dy:
            row_height = total / dx
            cursor = x
            for tile, size in zip(row_tiles, row_sizes, strict=True):
                tile_width = size / row_height
                rectangles.append((tile, cursor, y, tile_width, row_height))
                cursor += tile_width
            return x, y + row_height, dx, max(0.0, dy - row_height)
        row_width = total / dy
        cursor = y
        for tile, size in zip(row_tiles, row_sizes, strict=True):
            tile_height = size / row_width
            rectangles.append((tile, x, cursor, row_width, tile_height))
            cursor += tile_height
        return x + row_width, y, max(0.0, dx - row_width), dy

    x = y = 0.0
    dx, dy = width, height
    row_tiles: list[RadarMarketTile] = []
    row_sizes: list[float] = []
    remaining = list(zip(ordered, sizes, strict=True))
    while remaining:
        tile, size = remaining[0]
        side = min(dx, dy)
        if not row_sizes or worst([*row_sizes, size], side) <= worst(row_sizes, side):
            row_tiles.append(tile)
            row_sizes.append(size)
            remaining.pop(0)
            continue
        x, y, dx, dy = place(row_tiles, row_sizes, x, y, dx, dy)
        row_tiles, row_sizes = [], []
    if row_sizes:
        place(row_tiles, row_sizes, x, y, dx, dy)
    return rectangles


def radar_market_heatmap_html(snapshot: RadarMarketSnapshot) -> str:
    """Return the verified price-movement map; missing values are never colored."""

    if not snapshot.tiles:
        return ""
    rectangles = radar_market_treemap_rectangles(snapshot.tiles)
    max_magnitude = max(tile.magnitude_pct for tile in snapshot.tiles) or 1.0
    tile_html: list[str] = []
    for tile, x, y, width, height in rectangles:
        intensity = min(1.0, tile.magnitude_pct / max(max_magnitude, 1.0))
        if tile.change_pct > 0.02:
            direction_class, direction, arrow = "positive", "上昇", "▲"
            background = f"rgba(12, 142, 99, {0.30 + intensity * 0.58:.3f})"
        elif tile.change_pct < -0.02:
            direction_class, direction, arrow = "negative", "下落", "▼"
            background = f"rgba(184, 63, 86, {0.30 + intensity * 0.58:.3f})"
        else:
            direction_class, direction, arrow = "flat", "横ばい", "―"
            background = "rgba(95, 112, 134, 0.52)"
        change_label = f"{tile.change_pct:+.2f}%"
        tile_html.append(
            '<div class="investment-market-heatmap-tile '
            f'{direction_class}" style="left:{x:.4f}%;top:{y / 56 * 100:.4f}%;'
            f'width:{width:.4f}%;height:{height / 56 * 100:.4f}%;background:{background}" '
            f'aria-label="{html.escape(tile.display_name)} {direction} {change_label}">'
            f'<span class="investment-market-heatmap-name">{html.escape(tile.display_name)}</span>'
            f'<span class="investment-market-heatmap-symbol">{html.escape(tile.symbol)}</span>'
            f"<strong>{arrow} {change_label}</strong>"
            f"<small>{html.escape(tile.category)} · 根拠{tile.evidence_count}件</small>"
            "</div>"
        )
    period_label = f"直近{snapshot.lookback_sessions}営業日"
    as_of = max(tile.as_of for tile in snapshot.tiles).astimezone(NEWS_DISPLAY_TIMEZONE)
    unavailable = (
        f"<span>価格不足 {len(snapshot.unavailable_symbols)}銘柄</span>"
        if snapshot.unavailable_symbols
        else ""
    )
    return (
        '<section class="investment-market-heatmap">'
        '<div class="investment-market-heatmap-meta">'
        f"<strong>{period_label}の値動き</strong>"
        "<span>面積: 変動の大きさ（最低表示面積あり）</span>"
        "<span>色: 騰落方向</span>"
        f"<span>取得元: {html.escape(snapshot.provider)}</span>"
        f"<span>価格基準: {as_of:%Y-%m-%d %H:%M} {NEWS_DISPLAY_TIMEZONE_LABEL}</span>"
        f"{unavailable}"
        "</div>"
        '<div class="investment-market-heatmap-canvas">' + "".join(tile_html) + "</div>"
        '<div class="investment-market-heatmap-scale" aria-label="色の凡例">'
        '<span class="negative">▼ 下落</span><span class="flat">― 横ばい</span>'
        '<span class="positive">▲ 上昇</span></div>'
        "</section>"
    )


def _market_snapshot_from_state() -> RadarMarketSnapshot | None:
    raw_snapshot = st.session_state.get(NEWS_RADAR_MARKET_SNAPSHOT_STATE_KEY)
    if isinstance(raw_snapshot, RadarMarketSnapshot):
        return raw_snapshot
    if isinstance(raw_snapshot, Mapping):
        try:
            return RadarMarketSnapshot.model_validate(raw_snapshot)
        except ValueError:
            return None
    return None


def _render_market_heatmap(
    candidate_map: RadarCandidateMap,
    *,
    market_snapshot_callback: MarketSnapshotCallback,
) -> None:
    st.markdown("### 値動き注目マップ")
    st.caption(
        "ニュースで見つかった銘柄の実価格を比較し、動きが大きい対象を見つけます。"
        "投資魅力度や将来予測ではありません。"
    )
    period = int(
        st.radio(
            "比較期間",
            options=[1, 5, 20],
            format_func=lambda value: f"{value}営業日",
            horizontal=True,
            key=NEWS_RADAR_MARKET_PERIOD_STATE_KEY,
        )
    )
    if st.button(
        "価格マップを更新",
        key="investment_radar_market_refresh",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner("候補銘柄の価格を確認しています…"):
            st.session_state[NEWS_RADAR_MARKET_SNAPSHOT_STATE_KEY] = market_snapshot_callback(
                candidate_map.candidates, period
            )
    market_snapshot = _market_snapshot_from_state()
    if market_snapshot is None:
        st.info(
            "価格はまだ取得していません。「価格マップを更新」を押すと、"
            "ニュース候補を最大24銘柄まで明示的に取得します。"
        )
        return
    if market_snapshot.lookback_sessions != period:
        st.info(
            f"表示中は{market_snapshot.lookback_sessions}営業日の結果です。"
            f"{period}営業日に切り替えるには価格マップを更新してください。"
        )
    heatmap_html = radar_market_heatmap_html(market_snapshot)
    if not heatmap_html:
        st.warning(
            "比較に必要な価格履歴を取得できませんでした。Provider設定や銘柄コードを確認し、"
            "時間をおいて再実行してください。"
        )
        return
    st.markdown(heatmap_html, unsafe_allow_html=True)
    st.caption(
        "面積と色は概略比較のための表示です。正確な騰落率は各タイルの数値を確認してください。"
    )


def _render_heatmap(snapshot: NewsDashboardSnapshot) -> None:
    st.markdown("### ニューステーマ")
    st.caption("ニュース根拠が集まるテーマを確認します。価格方向は市場ヒートマップで確認します。")
    heatmap_html = news_dashboard_stock_heatmap_html(
        snapshot,
        max_groups=3,
        max_tiles_per_group=3,
    )
    if not heatmap_html:
        st.info("投資ヒートマップを集計できる材料はまだありません。")
        return
    st.markdown(heatmap_html, unsafe_allow_html=True)
    all_groups = news_dashboard_stock_heatmap_groups(
        snapshot,
        max_groups=999,
        max_tiles_per_group=3,
    )
    hidden_group_count = max(0, len(all_groups) - 3)
    if hidden_group_count:
        with st.expander(f"ほか {hidden_group_count}テーマを見る", expanded=False):
            st.caption(
                "初期表示には直近の3テーマだけを置いています。"
                "以下は同じ根拠量・鮮度の見方で確認できます。"
            )
            expanded_html = news_dashboard_stock_heatmap_html(
                snapshot,
                max_groups=999,
                max_tiles_per_group=3,
                include_topline=False,
                start_group=3,
            )
            st.markdown(expanded_html, unsafe_allow_html=True)


def news_radar_candidate_map_frame(candidates: Sequence[RadarCandidate]) -> pd.DataFrame:
    """Return a display-only frame for candidate diagnostics and regression tests."""

    return pd.DataFrame(
        [
            {
                "candidate_id": candidate.candidate_id,
                "symbol": candidate.symbol,
                "name": candidate.display_name or candidate.symbol,
                "provenance": _RADAR_PROVENANCE_LABELS[candidate.provenance],
                "directness": candidate.directness,
                "confirmation_priority": candidate.confirmation_priority,
                "source_breadth": max(1, candidate.independent_source_count),
                "material_tone": _RADAR_MATERIAL_TONE_LABELS[candidate.material_tone],
                "material_type": _radar_candidate_material_type_label(candidate),
                "data_status": _RADAR_DATA_STATUS_LABELS[candidate.symbol_data_status],
                "freshness": _freshness_label(candidate.freshness_status),
                "watchlist": "Myウォッチリスト一致" if candidate.watchlist_match else "",
            }
            for candidate in candidates
        ]
    )


def _radar_candidate_map_for_snapshot(snapshot: NewsDashboardSnapshot) -> RadarCandidateMap:
    """Build the display-only Radar map once so summary and queue stay aligned."""

    return _candidate_map_with_rag_state(
        build_radar_candidate_map(
            snapshot,
            watchlist_symbols=_radar_watchlist_symbols(),
            symbol_metadata_by_symbol=_heatmap_symbol_universe_by_symbol(),
        )
    )


def _render_radar_candidate_map(candidate_map: RadarCandidateMap) -> None:
    st.markdown("### ニュースからの確認候補")
    st.caption(
        "ニュース根拠を、本文に出た銘柄・SMAI推測候補・市場背景に分けて整理します。"
        "投資魅力度・期待収益・ランキング順位ではありません。"
    )
    _render_radar_candidate_guide(candidate_map)
    _render_radar_candidate_triage(candidate_map.candidates)
    candidates = _render_radar_candidate_filters(candidate_map)
    if not candidates:
        st.info("選択中の条件で、根拠へ戻れる追加候補はありません。")
        return

    selected_candidate = _selected_radar_candidate(candidate_map.candidates)
    st.caption(
        f"条件一致: {len(candidates)}件。初期表示は各レーン最大"
        f"{NEWS_RADAR_CANDIDATE_INITIAL_LANE_LIMIT}件です。候補を選ぶだけでは、"
        "価格取得・根拠資料確認・保存は開始しません。"
    )
    _render_radar_candidate_lanes(
        candidates,
        selected_candidate_id=selected_candidate.candidate_id,
    )


def _render_radar_candidate_guide(candidate_map: RadarCandidateMap) -> None:
    del candidate_map
    st.markdown(
        "**見方：** ① 本文に出た銘柄は記事で明示された対象、"
        "② SMAI推測候補はテーマとの関連を確認する対象、"
        "③ 市場背景の確認は個別銘柄ではなく市場の背景です。"
    )
    st.caption(
        "「確認の順番」はニュースの鮮度・追跡できる根拠・材料種別・"
        "Myウォッチリスト一致を整理した目安であり、投資判断ではありません。"
    )
    st.caption(
        "初期表示は「本文に出た銘柄」と「SMAI推測候補」です。"
        "市場背景の確認は「詳しい探索条件」から追加できます。"
    )


def _selected_radar_candidate(candidates: Sequence[RadarCandidate]) -> RadarCandidate:
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    selected_candidate_id = st.session_state.get(NEWS_RADAR_CANDIDATE_STATE_KEY)
    if selected_candidate_id not in candidate_by_id:
        selected_candidate_id = candidates[0].candidate_id
        st.session_state[NEWS_RADAR_CANDIDATE_STATE_KEY] = selected_candidate_id
    return candidate_by_id[selected_candidate_id]


def _select_radar_candidate(candidate_id: str) -> None:
    st.session_state[NEWS_RADAR_CANDIDATE_STATE_KEY] = candidate_id


def _request_radar_candidate_detail(candidate_id: str) -> None:
    _select_radar_candidate(candidate_id)
    st.session_state[NEWS_RADAR_CANDIDATE_DIALOG_REQUEST_STATE_KEY] = candidate_id


def _rerun_with_radar_candidate_detail(candidate_id: str) -> None:
    """Preserve the explicit detail surface after an explicit detail action reruns."""

    _request_radar_candidate_detail(candidate_id)
    st.rerun()


def _radar_candidate_material_type_label(candidate: RadarCandidate) -> str:
    """Return an evidence taxonomy label without implying a price direction."""

    material_types = _unique_text(
        [str(getattr(evidence, "material_type", "")).strip() for evidence in candidate.evidence]
    )
    if not material_types:
        return "材料種別: 未確認"
    labels = [
        _MATERIAL_LABELS.get(material_type, material_type) for material_type in material_types
    ]
    displayed = labels[:2]
    suffix = f"ほか{len(labels) - len(displayed)}種" if len(labels) > len(displayed) else ""
    return "材料種別: " + " / ".join([*displayed, *([suffix] if suffix else [])])


def _radar_candidate_display_name(candidate: RadarCandidate) -> str:
    display_name = (candidate.display_name or "").strip()
    if display_name and display_name.upper() != candidate.symbol.strip().upper():
        return display_name
    return candidate.symbol


def _radar_candidate_priority_bucket(candidate: RadarCandidate) -> str:
    if candidate.confirmation_priority >= 70:
        return "first"
    if candidate.confirmation_priority >= 55:
        return "next"
    return "as_needed"


def news_radar_confirmation_triage_frame(candidates: Sequence[RadarCandidate]) -> pd.DataFrame:
    """Return a compact, display-only by-lane confirmation overview."""

    rows: list[dict[str, object]] = []
    for priority_bucket, priority_label in _RADAR_TRIAGE_PRIORITY_LABELS.items():
        for provenance, provenance_label in _RADAR_PROVENANCE_LABELS.items():
            matched = [
                candidate
                for candidate in candidates
                if candidate.provenance == provenance
                and _radar_candidate_priority_bucket(candidate) == priority_bucket
            ]
            rows.append(
                {
                    "確認の順番": priority_label,
                    "候補由来": provenance_label,
                    "件数": len(matched),
                    "候補": " / ".join(
                        _radar_candidate_display_name(candidate) for candidate in matched[:2]
                    ),
                }
            )
    return pd.DataFrame(rows)


def _apply_radar_triage_filter(provenance: str, priority_bucket: str) -> None:
    _clear_radar_candidate_filters()
    st.session_state[NEWS_RADAR_TRIAGE_PROVENANCE_STATE_KEY] = provenance
    st.session_state[NEWS_RADAR_TRIAGE_PRIORITY_STATE_KEY] = priority_bucket
    st.session_state["investment_radar_candidate_provenance"] = [provenance]


def _clear_radar_candidate_filters() -> None:
    for key in (
        NEWS_RADAR_CANDIDATE_QUICK_DIRECT_ONLY_KEY,
        NEWS_RADAR_CANDIDATE_QUICK_WATCHLIST_ONLY_KEY,
        NEWS_RADAR_CANDIDATE_QUICK_UNCHECKED_ONLY_KEY,
        NEWS_RADAR_TRIAGE_PROVENANCE_STATE_KEY,
        NEWS_RADAR_TRIAGE_PRIORITY_STATE_KEY,
        "investment_radar_candidate_markets",
        "investment_radar_candidate_asset_types",
        "investment_radar_candidate_provenance",
        "investment_radar_candidate_rag_status",
    ):
        st.session_state.pop(key, None)


def _render_radar_candidate_triage(candidates: Sequence[RadarCandidate]) -> None:
    active_provenance = st.session_state.get(NEWS_RADAR_TRIAGE_PROVENANCE_STATE_KEY)
    active_priority = st.session_state.get(NEWS_RADAR_TRIAGE_PRIORITY_STATE_KEY)
    active_provenance_label = (
        _RADAR_PROVENANCE_LABELS.get(active_provenance)
        if isinstance(active_provenance, str)
        else None
    )
    active_priority_label = (
        _RADAR_TRIAGE_PRIORITY_LABELS.get(active_priority)
        if isinstance(active_priority, str)
        else None
    )
    triage_active = active_provenance_label is not None and active_priority_label is not None
    with st.expander("確認トリアージ（候補を絞る）", expanded=triage_active):
        st.caption(
            "候補由来とニュース確認の順番を組み合わせた見取り図です。"
            "投資魅力度・予想収益・ランキングではありません。"
        )
        if active_provenance_label is not None and active_priority_label is not None:
            st.caption(f"適用中: {active_provenance_label} / {active_priority_label}")
            st.button(
                "条件を解除",
                key="investment_radar_triage_clear",
                on_click=_clear_radar_candidate_filters,
            )
        for priority_bucket, priority_label in _RADAR_TRIAGE_PRIORITY_LABELS.items():
            st.markdown(f"**{priority_label}**")
            columns = st.columns(3)
            for column, provenance in zip(columns, _RADAR_PROVENANCE_LABELS, strict=False):
                matched = [
                    candidate
                    for candidate in candidates
                    if candidate.provenance == provenance
                    and _radar_candidate_priority_bucket(candidate) == priority_bucket
                ]
                with column:
                    st.caption(_RADAR_PROVENANCE_LABELS[provenance])
                    st.markdown(f"**{len(matched)}件**")
                    if matched:
                        st.caption(
                            " / ".join(
                                _radar_candidate_display_name(candidate)
                                for candidate in matched[:2]
                            )
                        )
                    else:
                        st.caption("該当なし")
                    st.button(
                        "この条件で絞り込む",
                        key=f"investment_radar_triage_{provenance}_{priority_bucket}",
                        on_click=_apply_radar_triage_filter,
                        args=(provenance, priority_bucket),
                        disabled=not matched,
                        use_container_width=True,
                    )


def _render_radar_today_summary(candidate_map: RadarCandidateMap) -> None:
    """Render the selected confirmation path before the compact theme map."""

    candidates = candidate_map.candidates
    if not candidates:
        return
    selected_candidate = max(
        candidates,
        key=lambda candidate: (
            candidate.confirmation_priority,
            candidate.provenance == "direct_mention",
            candidate.directness,
            candidate.candidate_id,
        ),
    )
    counts = {
        provenance: sum(candidate.provenance == provenance for candidate in candidates)
        for provenance in _RADAR_PROVENANCE_LABELS
    }
    st.markdown("### 今日の確認ポイント")
    st.caption(
        "ニュースから確認を始める候補と、市場背景として見る対象を分けて表示します。"
        "投資魅力度・期待収益・ランキング順位ではありません。"
    )
    direct_col, inferred_col, macro_col = st.columns(3)
    for column, provenance in zip(
        (direct_col, inferred_col, macro_col),
        _RADAR_PROVENANCE_LABELS,
        strict=False,
    ):
        with column:
            column.metric(_RADAR_PROVENANCE_LABELS[provenance], f"{counts[provenance]}件")
    with st.container(border=True):
        st.markdown("**まず確認する候補**")
        st.markdown(f"**{html.escape(_radar_candidate_display_name(selected_candidate))}**")
        if _radar_candidate_display_name(selected_candidate) != selected_candidate.symbol:
            st.caption(f"銘柄コード: {selected_candidate.symbol}")
        status_parts = [
            _RADAR_PROVENANCE_LABELS[selected_candidate.provenance],
            _radar_candidate_material_type_label(selected_candidate),
            f"ニュース: {_freshness_label(selected_candidate.freshness_status)}",
            f"確認の順番: {_radar_candidate_priority_label(selected_candidate)}",
        ]
        if selected_candidate.watchlist_match:
            status_parts.append("Myウォッチリスト一致")
        st.caption(" / ".join(status_parts))
        st.button(
            "根拠と次の操作を開く",
            key=f"investment_radar_today_candidate_detail_{selected_candidate.candidate_id}",
            on_click=_request_radar_candidate_detail,
            args=(selected_candidate.candidate_id,),
            type="primary",
            use_container_width=True,
        )


def _render_radar_candidate_lanes(
    candidates: Sequence[RadarCandidate],
    *,
    selected_candidate_id: str,
) -> None:
    candidates_by_provenance = {
        provenance: [candidate for candidate in candidates if candidate.provenance == provenance]
        for provenance in _RADAR_PROVENANCE_LABELS
    }
    for provenance in ("direct_mention", "inferred_candidate"):
        _render_radar_candidate_lane(
            provenance,
            candidates_by_provenance[provenance],
            selected_candidate_id=selected_candidate_id,
        )
    macro_candidates = candidates_by_provenance["macro_proxy"]
    if macro_candidates:
        macro_selected = selected_candidate_id in {
            candidate.candidate_id for candidate in macro_candidates
        }
        with st.expander("市場背景の確認", expanded=macro_selected):
            _render_radar_candidate_lane(
                "macro_proxy",
                macro_candidates,
                selected_candidate_id=selected_candidate_id,
            )


def radar_candidate_lane_visible_items(
    candidates: Sequence[RadarCandidate],
    *,
    expanded: bool,
    limit: int = NEWS_RADAR_CANDIDATE_INITIAL_LANE_LIMIT,
) -> tuple[list[RadarCandidate], int]:
    """Bound a candidate lane while retaining the backend's deterministic order."""

    bounded_limit = max(1, limit)
    visible = list(candidates) if expanded else list(candidates[:bounded_limit])
    return visible, max(0, len(candidates) - len(visible))


def _radar_candidate_lane_expanded_key(provenance: str) -> str:
    return f"investment_radar_candidate_lane_expanded_{provenance}"


def _toggle_radar_candidate_lane(provenance: str) -> None:
    key = _radar_candidate_lane_expanded_key(provenance)
    st.session_state[key] = not bool(st.session_state.get(key, False))


def _render_radar_candidate_lane(
    provenance: str,
    candidates: Sequence[RadarCandidate],
    *,
    selected_candidate_id: str,
) -> None:
    st.markdown(f"#### {_RADAR_PROVENANCE_LABELS[provenance]}（{len(candidates)}件）")
    st.caption(_RADAR_PROVENANCE_GUIDANCE[provenance])
    if not candidates:
        st.caption("表示中の候補はありません。")
        return
    expanded = bool(st.session_state.get(_radar_candidate_lane_expanded_key(provenance), False))
    visible_candidates, hidden_count = radar_candidate_lane_visible_items(
        candidates, expanded=expanded
    )
    for candidate in visible_candidates:
        _render_radar_candidate_card(
            candidate,
            selected=candidate.candidate_id == selected_candidate_id,
        )
    if hidden_count or expanded:
        label = f"あと {hidden_count}件を見る" if hidden_count else "表示をたたむ"
        st.button(
            label,
            key=f"investment_radar_candidate_lane_toggle_{provenance}",
            on_click=_toggle_radar_candidate_lane,
            args=(provenance,),
            use_container_width=True,
        )


def _render_radar_candidate_card(
    candidate: RadarCandidate,
    *,
    selected: bool,
) -> None:
    with st.container(border=True):
        selected_label = "　（選択中）" if selected else ""
        st.markdown(f"**{html.escape(_radar_candidate_display_name(candidate))}{selected_label}**")
        if _radar_candidate_display_name(candidate) != candidate.symbol:
            st.caption(f"銘柄コード: {candidate.symbol}")
        status_parts = [
            _radar_candidate_material_type_label(candidate),
            f"ニュース: {_freshness_label(candidate.freshness_status)}",
            f"独立根拠: {candidate.independent_source_count}件",
            f"確認の順番: {_radar_candidate_priority_label(candidate)}",
        ]
        if candidate.watchlist_match:
            status_parts.append("Myウォッチリスト一致")
        st.caption(" / ".join(status_parts))
        st.button(
            "詳細を開く",
            key=f"investment_radar_candidate_open_detail_{candidate.candidate_id}",
            on_click=_request_radar_candidate_detail,
            args=(candidate.candidate_id,),
            use_container_width=True,
        )


def _render_requested_radar_candidate_detail(
    candidates: Sequence[RadarCandidate],
    *,
    as_of: date,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    """Consume exactly one explicit detail request without reopening after close."""

    requested_candidate_id = st.session_state.pop(
        NEWS_RADAR_CANDIDATE_DIALOG_REQUEST_STATE_KEY, None
    )
    if not isinstance(requested_candidate_id, str):
        return
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    candidate = candidate_by_id.get(requested_candidate_id)
    if candidate is None:
        return
    _show_radar_candidate_detail_dialog(
        candidate,
        as_of=as_of,
        open_symbol_callback=open_symbol_callback,
    )


def _render_radar_candidate_filters(candidate_map: RadarCandidateMap) -> list[RadarCandidate]:
    candidates = candidate_map.candidates
    markets = sorted({candidate.market for candidate in candidates if candidate.market})
    asset_types = sorted({candidate.asset_type for candidate in candidates if candidate.asset_type})
    rag_statuses = sorted({candidate.rag_data_status for candidate in candidates})
    provenance_options = ["direct_mention", "inferred_candidate", "macro_proxy"]
    st.markdown("#### 探索条件")
    quick_direct_only = st.checkbox(
        "本文に出た銘柄",
        key=NEWS_RADAR_CANDIDATE_QUICK_DIRECT_ONLY_KEY,
    )
    quick_watchlist_only = st.checkbox(
        "Myウォッチリスト",
        key=NEWS_RADAR_CANDIDATE_QUICK_WATCHLIST_ONLY_KEY,
    )
    quick_unchecked_only = st.checkbox(
        "資料未確認",
        key=NEWS_RADAR_CANDIDATE_QUICK_UNCHECKED_ONLY_KEY,
    )
    with st.expander("詳しい探索条件", expanded=False):
        market_col, asset_col, provenance_col = st.columns(3)
        with market_col:
            selected_markets = st.multiselect(
                "市場",
                markets,
                key="investment_radar_candidate_markets",
            )
        with asset_col:
            selected_asset_types = st.multiselect(
                "資産種別",
                asset_types,
                key="investment_radar_candidate_asset_types",
            )
        with provenance_col:
            selected_provenance_values = st.multiselect(
                "候補由来",
                provenance_options,
                default=["direct_mention", "inferred_candidate"],
                format_func=lambda value: _RADAR_PROVENANCE_LABELS[value],
                key="investment_radar_candidate_provenance",
            )
        selected_rag_statuses = st.multiselect(
            "根拠資料の状態",
            rag_statuses,
            format_func=lambda value: _RADAR_DATA_STATUS_LABELS[value],
            key="investment_radar_candidate_rag_status",
        )
    st.button(
        "条件を解除",
        key="investment_radar_candidate_filters_clear",
        on_click=_clear_radar_candidate_filters,
    )
    selected_provenances = cast(list[object], selected_provenance_values)
    filtered = filter_radar_candidates(
        candidate_map,
        markets=selected_markets,
        asset_types=selected_asset_types,
        provenances=cast(list, selected_provenances),
        rag_statuses=cast(list[RadarCandidateDataStatus], selected_rag_statuses),
        watchlist_only=quick_watchlist_only,
    )
    if quick_direct_only:
        filtered = [candidate for candidate in filtered if candidate.provenance == "direct_mention"]
    if quick_unchecked_only:
        filtered = [
            candidate for candidate in filtered if candidate.rag_data_status == "not_checked"
        ]
    triage_provenance = st.session_state.get(NEWS_RADAR_TRIAGE_PROVENANCE_STATE_KEY)
    triage_priority = st.session_state.get(NEWS_RADAR_TRIAGE_PRIORITY_STATE_KEY)
    if triage_provenance in _RADAR_PROVENANCE_LABELS:
        filtered = [
            candidate for candidate in filtered if candidate.provenance == triage_provenance
        ]
    if triage_priority in _RADAR_TRIAGE_PRIORITY_LABELS:
        filtered = [
            candidate
            for candidate in filtered
            if _radar_candidate_priority_bucket(candidate) == triage_priority
        ]
    active_conditions: list[str] = []
    if quick_direct_only:
        active_conditions.append("本文に出た銘柄")
    if quick_watchlist_only:
        active_conditions.append("Myウォッチリスト")
    if quick_unchecked_only:
        active_conditions.append("資料未確認")
    if (
        triage_provenance in _RADAR_PROVENANCE_LABELS
        and triage_priority in _RADAR_TRIAGE_PRIORITY_LABELS
    ):
        active_conditions.append(
            f"{_RADAR_PROVENANCE_LABELS[triage_provenance]} / "
            f"{_RADAR_TRIAGE_PRIORITY_LABELS[triage_priority]}"
        )
    if active_conditions:
        st.caption("絞り込み中: " + " / ".join(active_conditions))
    return filtered


def _render_radar_candidate_detail(
    candidate: RadarCandidate,
    *,
    as_of: date,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    with st.container(border=True):
        st.markdown(f"#### 選択中の候補：{html.escape(_radar_candidate_label(candidate))}")
        st.caption(
            f"{_RADAR_PROVENANCE_LABELS[candidate.provenance]} / "
            f"{_radar_candidate_material_type_label(candidate)} / "
            f"ニュース鮮度: {_freshness_label(candidate.freshness_status)}"
        )
        st.markdown("**なぜこの候補か**")
        categories = " / ".join(candidate.categories) or "未分類"
        st.write(
            f"候補由来: {_RADAR_PROVENANCE_LABELS[candidate.provenance]}。"
            f"カテゴリ: {categories}。"
            f"独立した根拠: {candidate.independent_source_count}件。"
        )
        st.markdown(_radar_evidence_path_html(candidate), unsafe_allow_html=True)
        if candidate.watchlist_match:
            st.caption("Myウォッチリストと一致しています。")
        st.markdown("**データの状態**")
        st.caption("銘柄DB: " f"{_RADAR_DATA_STATUS_LABELS[candidate.symbol_data_status]}")
        st.caption(f"価格: {_radar_price_data_status_label(candidate)}")
        st.caption(f"根拠資料: {_radar_rag_data_status_label(candidate)}")
        st.markdown("**確認の順番**")
        st.write(_radar_candidate_priority_label(candidate))
        for kind, detail, points in _radar_candidate_priority_reason_rows(candidate):
            reason_text = _radar_candidate_priority_reason_text(
                candidate,
                kind,
                detail,
                points,
            )
            st.caption(f"・{reason_text}")
        st.caption(
            "確認優先度はニュース確認の順番です。投資魅力度・期待収益・ランキング順位を示しません。"
        )
        evidence_bundle = _render_radar_evidence_bundle(candidate)
        _render_radar_interpretation(candidate)
        st.markdown("**根拠記事**")
        for evidence in candidate.evidence:
            source = evidence.source_name or _source_type_label(evidence.source_type)
            label = f"{evidence.headline_title} — {source}"
            if evidence.source_url:
                st.markdown(
                    f'<a href="{html.escape(evidence.source_url, quote=True)}" '
                    f'target="_blank" rel="noopener noreferrer">{html.escape(label)} ↗</a>',
                    unsafe_allow_html=True,
                )
            else:
                st.write(label)
        st.markdown("**次の確認**")
        for gap in candidate.confirmation_gaps:
            st.caption(f"・{gap}")
        if candidate.is_investigation_candidate:
            if st.button(
                "根拠資料を確認",
                key=f"investment_radar_candidate_research_{candidate.candidate_id}",
            ):
                _store_radar_evidence_bundle(candidate, as_of=as_of)
                _rerun_with_radar_candidate_detail(candidate.candidate_id)
            if evidence_bundle is not None and st.button(
                "AIで根拠を整理（明示実行）",
                key=f"investment_radar_candidate_interpret_{candidate.candidate_id}",
            ):
                _store_radar_interpretation(candidate, evidence_bundle)
                _rerun_with_radar_candidate_detail(candidate.candidate_id)
            st.button(
                "銘柄コックピットで確認",
                key=f"investment_radar_candidate_open_{candidate.candidate_id}",
                on_click=open_symbol_callback,
                args=(candidate.symbol,),
                type="primary",
            )
            st.caption(
                "この画面での選択・遷移では、価格取得、RAG検索、外部資料取得、保存は開始しません。"
            )
        else:
            st.info("市場背景の確認は、個別銘柄候補としてではなく市場の状況確認に使います。")


def _radar_evidence_path_html(candidate: RadarCandidate) -> str:
    extraction_label = (
        "本文言及"
        if candidate.provenance == "direct_mention"
        else "テーマ推測" if candidate.provenance == "inferred_candidate" else "市場背景"
    )
    rag_class = "ready" if candidate.rag_data_status in {"available", "partial"} else "pending"
    rag_label = "RAG確認済み" if rag_class == "ready" else "RAG未確認"
    return (
        '<div class="investment-radar-evidence-path" aria-label="根拠の確認経路">'
        '<span class="ready">ニュース根拠</span><b>→</b>'
        f'<span class="ready">{html.escape(extraction_label)}</span><b>→</b>'
        f'<span class="{rag_class}">{rag_label}</span><b>→</b>'
        '<span class="next">銘柄コックピット</span>'
        "</div>"
    )


def _show_radar_candidate_detail_dialog(
    candidate: RadarCandidate,
    *,
    as_of: date,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    """Open candidate detail only for the explicit click that requested it."""

    def render_body() -> None:
        st.markdown(
            '<span class="investment-radar-candidate-detail-dialog-marker"></span>',
            unsafe_allow_html=True,
        )
        _render_radar_candidate_detail(
            candidate,
            as_of=as_of,
            open_symbol_callback=open_symbol_callback,
        )

    dialog = getattr(st, "dialog", None)
    if callable(dialog):

        @dialog("確認候補の詳細", width="large")
        def _dialog() -> None:
            render_body()

        _dialog()
        return
    with st.container(border=True):
        st.subheader("確認候補の詳細")
        render_body()


def _radar_candidate_priority_label(candidate: RadarCandidate) -> str:
    return _RADAR_TRIAGE_PRIORITY_LABELS[_radar_candidate_priority_bucket(candidate)]


def _radar_candidate_priority_reason_rows(
    candidate: RadarCandidate,
) -> list[tuple[str, str, int]]:
    """Return priority rows, including candidates built before the reason field existed.

    Streamlit reloads the page script independently of imported domain modules.
    During a rolling local update, a just-reloaded page can therefore receive a
    ``RadarCandidate`` created by the previous in-memory contract.  The fallback
    mirrors that previous deterministic priority formula strictly for display;
    it does not alter the score or persist any data.
    """

    current_reasons = getattr(candidate, "confirmation_priority_reasons", None)
    if current_reasons is not None:
        rows = [
            (
                str(getattr(reason, "kind", "unknown")),
                str(getattr(reason, "detail", "unknown")),
                int(getattr(reason, "points", 0)),
            )
            for reason in current_reasons
        ]
        if sum(points for _, _, points in rows) == candidate.confirmation_priority:
            return rows

    evidence = list(getattr(candidate, "evidence", ()) or ())
    freshness_status = max(
        (str(getattr(item, "freshness_status", "unknown")) for item in evidence),
        key=lambda value: (_RADAR_PRIORITY_FRESHNESS_POINTS.get(value, 0), value),
        default="unknown",
    )
    freshness_points = _RADAR_PRIORITY_FRESHNESS_POINTS.get(freshness_status, 0)
    material_type = max(
        (str(getattr(item, "material_type", "unknown")) for item in evidence),
        key=lambda value: (_RADAR_PRIORITY_MATERIAL_POINTS.get(value, 3), value),
        default="unknown",
    )
    material_points = _RADAR_PRIORITY_MATERIAL_POINTS.get(material_type, 3) if evidence else 0
    rows = [
        ("freshness", freshness_status, freshness_points),
        ("evidence_breadth", str(min(3, len(evidence))), min(3, len(evidence)) * 8),
        ("material_type", material_type, material_points),
    ]
    if candidate.watchlist_match:
        rows.append(("watchlist_match", "watchlist_match", 14))
    return rows if sum(points for _, _, points in rows) == candidate.confirmation_priority else []


def _radar_candidate_priority_reason_text(
    candidate: RadarCandidate,
    kind: str,
    detail: str,
    points: int,
) -> str:
    del points
    if kind == "freshness":
        return f"ニュース鮮度: {_freshness_label(candidate.freshness_status)}"
    if kind == "evidence_breadth":
        return f"追跡できる根拠記事: {detail}件"
    if kind == "material_type":
        material_label = _MATERIAL_LABELS.get(detail, detail)
        return f"材料の種類: {material_label}"
    if kind == "watchlist_match":
        return "Myウォッチリスト一致"
    return "確認材料"


def _radar_price_data_status_label(candidate: RadarCandidate) -> str:
    if candidate.price_data_status == "not_checked":
        return "未実行（銘柄コックピットで確認）"
    return _RADAR_DATA_STATUS_LABELS[candidate.price_data_status]


def _radar_rag_data_status_label(candidate: RadarCandidate) -> str:
    if candidate.rag_data_status == "not_checked":
        return "未実行（「根拠資料を確認」で開始）"
    return _RADAR_DATA_STATUS_LABELS[candidate.rag_data_status]


def _candidate_map_with_rag_state(candidate_map: RadarCandidateMap) -> RadarCandidateMap:
    stored = st.session_state.get(NEWS_RADAR_EVIDENCE_BUNDLES_STATE_KEY, {})
    if not isinstance(stored, dict):
        return candidate_map
    candidates: list[RadarCandidate] = []
    for candidate in candidate_map.candidates:
        bundle = _radar_evidence_bundle_from_state(stored.get(candidate.candidate_id))
        if bundle is None:
            candidates.append(candidate)
            continue
        rag_status: RadarCandidateDataStatus = (
            "available" if bundle.status == "available" else "partial"
        )
        candidates.append(
            candidate.model_copy(
                update={
                    "rag_data_status": rag_status,
                    "confirmation_gaps": _unique_text(
                        [
                            *candidate.confirmation_gaps,
                            *bundle.confirmation_gaps,
                        ]
                    ),
                }
            )
        )
    return candidate_map.model_copy(update={"candidates": candidates})


def _render_radar_evidence_bundle(candidate: RadarCandidate) -> RadarEvidenceBundle | None:
    bundle = _radar_evidence_bundle_for_candidate(candidate)
    if bundle is None:
        return None
    st.markdown("**根拠資料の確認**")
    if bundle.citations:
        for citation in bundle.citations:
            st.markdown(
                f"**{citation.title}** · {citation.source_type} · "
                f"{_freshness_label(citation.freshness_status)}"
            )
            st.caption(citation.excerpt)
    else:
        st.info("ローカルRAG根拠は確認できませんでした。確認不足として扱います。")
    for gap in bundle.confirmation_gaps:
        st.caption(f"・{gap}")
    if bundle.retrieval_quality is not None:
        with st.expander("検索の状態（ローカルRAG）", expanded=False):
            st.caption(
                f"方式: {bundle.retrieval_quality.backend} / "
                f"候補: {bundle.retrieval_quality.candidate_count}件 / "
                f"根拠: {bundle.retrieval_quality.evidence_count}件"
            )
    return bundle


def _store_radar_evidence_bundle(candidate: RadarCandidate, *, as_of: date) -> None:
    """Run local RAG only after the user explicitly asks to confirm evidence."""

    from backend.research import (
        HybridResearchRetrievalService,
        ResearchRetrievalService,
        ResearchSearchError,
    )
    from ui.research_state import (
        autoload_local_research_documents,
        research_store,
        research_vector_store,
    )

    context = build_radar_research_context(candidate, as_of=as_of)
    try:
        autoload_local_research_documents()
        retriever = HybridResearchRetrievalService(
            ResearchRetrievalService(research_store()),
            vector_store=research_vector_store(),
        )
        bundle = build_radar_evidence_bundle(
            candidate,
            context=context,
            retriever=retriever,
        )
    except (OSError, ResearchSearchError, ValueError):
        bundle = RadarEvidenceBundle(
            candidate_id=candidate.candidate_id,
            context=context,
            status="unavailable",
            confirmation_gaps=["ローカルRAG根拠を確認できませんでした。後で再試行してください。"],
            generated_at=datetime.now(UTC),
        )
    existing = st.session_state.get(NEWS_RADAR_EVIDENCE_BUNDLES_STATE_KEY, {})
    bundles = dict(existing) if isinstance(existing, dict) else {}
    bundles[candidate.candidate_id] = bundle
    st.session_state[NEWS_RADAR_EVIDENCE_BUNDLES_STATE_KEY] = bundles


def _render_radar_interpretation(candidate: RadarCandidate) -> None:
    stored = st.session_state.get(NEWS_RADAR_INTERPRETATIONS_STATE_KEY, {})
    result = _radar_interpretation_from_state(
        stored.get(candidate.candidate_id) if isinstance(stored, dict) else None
    )
    if result is None:
        return
    st.markdown("**AIによる根拠整理**")
    st.caption(
        "参照IDに結び付いた説明です。投資判断・順位・スコア・予測値を変更するものではありません。"
    )
    st.write(result.overall_reading)
    _render_radar_interpretation_points("材料", result.material_points)
    _render_radar_interpretation_points("注意点", result.caution_points)
    _render_radar_interpretation_points("不明点", result.unknowns)
    _render_radar_interpretation_points("次の確認", result.next_checks)
    if result.fallback_reason is not None:
        st.caption(f"表示状態: {_radar_interpretation_status_label(result)}")
    if result.warnings:
        for warning in result.warnings:
            st.caption(f"・{warning}")


def _render_radar_interpretation_points(label: str, points: Sequence[object]) -> None:
    if not points:
        return
    st.markdown(f"*{label}*")
    for point in points:
        summary = str(getattr(point, "summary", "")).strip()
        evidence_ids = getattr(point, "evidence_ids", [])
        if not summary:
            continue
        reference = "、".join(str(value) for value in evidence_ids[:3])
        st.write(f"・{summary}")
        if reference:
            st.caption(f"根拠ID: {reference}")


def _store_radar_interpretation(
    candidate: RadarCandidate,
    evidence_bundle: RadarEvidenceBundle,
) -> None:
    try:
        result = build_radar_interpretation_from_settings(candidate, evidence_bundle)
    except ValueError:
        return
    existing = st.session_state.get(NEWS_RADAR_INTERPRETATIONS_STATE_KEY, {})
    interpretations = dict(existing) if isinstance(existing, dict) else {}
    interpretations[candidate.candidate_id] = result
    st.session_state[NEWS_RADAR_INTERPRETATIONS_STATE_KEY] = interpretations


def _radar_evidence_bundle_for_candidate(candidate: RadarCandidate) -> RadarEvidenceBundle | None:
    stored = st.session_state.get(NEWS_RADAR_EVIDENCE_BUNDLES_STATE_KEY, {})
    return _radar_evidence_bundle_from_state(
        stored.get(candidate.candidate_id) if isinstance(stored, dict) else None
    )


def _radar_interpretation_from_state(value: object) -> RadarInterpretationResult | None:
    if isinstance(value, RadarInterpretationResult):
        return value
    if isinstance(value, Mapping):
        try:
            return RadarInterpretationResult.model_validate(value)
        except ValueError:
            return None
    return None


def _radar_interpretation_status_label(result: RadarInterpretationResult) -> str:
    labels = {
        "disabled": "AI根拠整理は設定で無効です。確認不足として扱います。",
        "fallback": "AI根拠整理を取得できませんでした。確認不足として扱います。",
        "validation_error": "AI応答を根拠制約に照らして採用しませんでした。",
    }
    return labels.get(result.status, "根拠IDに結び付けたAI整理を表示しています。")


def _radar_evidence_bundle_from_state(value: object) -> RadarEvidenceBundle | None:
    if isinstance(value, RadarEvidenceBundle):
        return value
    if isinstance(value, Mapping):
        try:
            return RadarEvidenceBundle.model_validate(value)
        except ValueError:
            return None
    return None


def _unique_text(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _radar_watchlist_symbols() -> list[str]:
    manual_symbols = parse_news_watchlist_symbols(
        str(st.session_state.get(NEWS_DASHBOARD_WATCHLIST_STATE_KEY) or "")
    )
    favorite_symbols = [favorite.symbol for favorite in load_favorites()]
    source = str(st.session_state.get("investment_news_watchlist_source", "favorites_watchlist"))
    return combine_news_watchlist_symbols(manual_symbols, favorite_symbols, source=source)


def _radar_candidate_label(candidate: RadarCandidate) -> str:
    name = _radar_candidate_display_name(candidate)
    identity = name if name == candidate.symbol else f"{name}（{candidate.symbol}）"
    return f"{identity} — {_RADAR_PROVENANCE_LABELS[candidate.provenance]}"


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
    _render_market_proxy_symbols(card, symbol_name_map=symbol_name_map)
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


def _render_market_proxy_symbols(
    card: NewsHeadlineCard,
    *,
    symbol_name_map: dict[str, str],
) -> None:
    symbols = news_card_market_proxy_symbols(card)
    if not symbols:
        return
    labels = [
        truncate_text(_market_proxy_label(symbol, symbol_name_map=symbol_name_map), max_chars=28)
        for symbol in symbols
    ]
    st.caption(f"市場確認指標: {' / '.join(labels)}")


def _market_proxy_label(symbol: str, *, symbol_name_map: dict[str, str]) -> str:
    normalized = symbol.strip().upper()
    display_name = _NEWS_MARKET_PROXY_LABELS.get(normalized) or symbol_name_map.get(normalized)
    return f"{normalized} / {display_name}" if display_name else normalized


def _render_symbol_button_group(
    symbols: list[str],
    *,
    caption: str,
    key_prefix: str,
    open_symbol_callback: OpenSymbolCallback,
    symbol_name_map: dict[str, str],
    max_columns: int,
) -> None:
    _ = max_columns
    st.caption(caption)
    for index, symbol in enumerate(symbols):
        normalized = symbol.strip().upper()
        if not normalized:
            continue
        label = news_symbol_handoff_label(symbol, symbol_name_map=symbol_name_map)
        with st.container(border=True):
            symbol_col, favorite_col = st.columns([1.7, 1])
            with symbol_col:
                st.markdown(
                    '<span class="investment-news-symbol-chip-open-anchor"></span>',
                    unsafe_allow_html=True,
                )
                st.button(
                    truncate_text(label, max_chars=42),
                    key=f"investment_news_open_{key_prefix}_{normalized}_{index}",
                    help=f"{label}を投資コックピットで確認します。",
                    use_container_width=True,
                    on_click=open_symbol_callback,
                    args=(normalized,),
                )
            with favorite_col:
                render_favorite_button(
                    normalized,
                    name=symbol_name_map.get(normalized),
                    source_screen="news",
                    key=f"investment_news_favorite_{key_prefix}_{normalized}_{index}",
                )


def _news_symbol_chip_preview_rows(
    symbols: Sequence[str],
    *,
    symbol_name_map: Mapping[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized:
            continue
        rows.append(
            {
                "symbol": normalized,
                "label": news_symbol_handoff_label(normalized, symbol_name_map=symbol_name_map),
                "favorite_label": "★ お気に入り中" if is_favorite(normalized) else "☆ お気に入り",
            }
        )
    return rows


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
    unique_cards = _unique_news_ticker_cards(cards)
    pages = [unique_cards[index : index + 4] for index in range(0, len(unique_cards), 4)]
    page_count = len(pages)
    duration_seconds = max(6, page_count * 6)
    visible_percent = round(100 / page_count, 4) if page_count > 1 else 100
    animation_css = (
        ""
        if page_count == 1
        else (
            "<style>"
            f"@keyframes investment-news-board-cycle{{0%,{visible_percent - 1}%{{opacity:1;transform:translateY(0);pointer-events:auto}}"
            f"{visible_percent}%,100%{{opacity:0;transform:translateY(10px);pointer-events:none}}}}"
            + "".join(
                (
                    f".investment-news-board-page--{index}{{animation-delay:{index * 6}s}}"
                    f"#investment-news-board-page-{index}:checked~.investment-news-board-viewport .investment-news-board-page{{animation:none;opacity:0;transform:none;pointer-events:none}}"
                    f"#investment-news-board-page-{index}:checked~.investment-news-board-viewport .investment-news-board-page--{index}{{opacity:1;pointer-events:auto}}"
                    f"#investment-news-board-page-{index}:checked~.investment-news-board-nav label[for=investment-news-board-page-{index}]{{background:#67e8f9;transform:scale(1.18)}}"
                )
                for index in range(page_count)
            )
            + "</style>"
        )
    )
    controls = "".join(
        f'<input class="investment-news-board-radio" type="radio" name="investment-news-board-page" id="investment-news-board-page-{index}" />'
        for index in range(page_count)
    )
    page_html = "".join(
        (
            f'<div class="investment-news-board-page investment-news-board-page--{page_index}" '
            f'style="--investment-news-board-duration:{duration_seconds}s">'
            + "".join(_news_ticker_item_html(card) for card in page)
            + "</div>"
        )
        for page_index, page in enumerate(pages)
    )
    navigation = (
        '<div class="investment-news-board-nav" aria-label="ヘッドラインページ">'
        + "".join(
            f'<label for="investment-news-board-page-{index}" title="{index + 1}ページ目"><span>{index + 1}</span></label>'
            for index in range(page_count)
        )
        + '<span class="investment-news-board-nav-note">ホバーで一時停止</span></div>'
        if page_count > 1
        else ""
    )
    return (
        animation_css
        + '<section class="investment-news-ticker investment-news-board" aria-label="市場ニュースヘッドライン">'
        + controls
        + f'<div class="investment-news-board-viewport">{page_html}</div>'
        + navigation
        + "</section>"
    )


def _unique_news_ticker_cards(cards: list[NewsHeadlineCard]) -> list[NewsHeadlineCard]:
    unique: list[NewsHeadlineCard] = []
    seen_titles: set[str] = set()
    for card in cards:
        normalized_title = " ".join(card.title.casefold().split())
        if not normalized_title or normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)
        unique.append(card)
    return unique


def _news_ticker_item_html(card: NewsHeadlineCard) -> str:
    tag = "a" if card.url else "article"
    link_attributes = (
        f' href="{html.escape(card.url or "", quote=True)}" target="_blank" rel="noopener noreferrer"'
        if card.url
        else ""
    )
    source = card.source_name or _source_type_label(card.source_type)
    return (
        f'<{tag} class="investment-news-ticker-item"{link_attributes}>'
        f'<span class="investment-news-ticker-category">{html.escape(card.category)}</span>'
        f'<span class="investment-news-ticker-title">{html.escape(card.title)}</span>'
        f"<small>{html.escape(source)}</small>"
        f"</{tag}>"
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
    if inferred:
        return "方向未確認"
    if value is None:
        return "未取得"
    return f"{value:+.1f}%"


def _volume_label(value: float | None, *, inferred: bool = False) -> str:
    if inferred:
        return "ニュース集計"
    if value is None:
        return "未取得"
    suffix = ""
    if value >= 1.8:
        return f"高い{suffix}"
    if value >= 1.3:
        return f"やや高い{suffix}"
    return f"通常{suffix}"
