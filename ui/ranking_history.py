from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

import altair as alt
import pandas as pd
import streamlit as st

from backend.ranking_history.models import (
    RankingHistoryIndexItem,
    RankingHistoryPeriod,
    RankingHistoryResultRow,
    RankingHistorySaveRequest,
    RankingHistorySaveResult,
    RankingHistorySnapshot,
    RankingHistoryTarget,
)
from backend.ranking_history.service import RankingHistoryService
from ui.ranking import (
    ranking_policy_description,
    ranking_policy_label,
    ranking_purpose_weight_summary,
)
from ui.ranking_state import restore_ranking_filters
from ui.styles import CHART_COLORS, THEME_COLORS, style_altair_chart

RANKING_HISTORY_VIEW_KEY = "ranking_view_mode"
RANKING_HISTORY_SELECTED_KEY = "selected_ranking_history_id"
RANKING_HISTORY_USER_KEY = "ranking_history_view_user_id"
RANKING_HISTORY_NOTICE_KEY = "ranking_history_restore_notice"
HISTORY_NOTICE = (
    "このランキングは保存時点の結果です。現在の株価・スコアとは異なる場合があります。"
    "現在の情報は銘柄コックピットで確認してください。"
)

DISPLAY_TO_FIELD = {
    "順位": "rank",
    "銘柄": "symbol",
    "銘柄名": "name",
    "現在値": "price",
    "現在株価（円）": "price_jpy",
    "総合スコア": "total_score",
    "Screening": "screening_score",
    "基礎評価": "screening_score",
    "Risk": "risk_score",
    "リスク": "risk_score",
    "データ品質": "data_quality_score",
    "データ信頼度": "data_quality_score",
    "条件適合度": "condition_fit_score",
    "上昇気配": "upside_signal_score",
    "下降警戒": "downside_signal_score",
    "予測変化率": "forecast_change_pct",
    "予測確度": "forecast_confidence",
    "予測日数": "forecast_days",
    "モデル方向": "model_direction",
    "配当利回り": "dividend_yield_pct",
    "PER": "per",
    "PBR": "pbr",
    "ROE": "roe_pct",
    "時価総額": "market_cap",
    "出来高": "volume",
    "ボラティリティ": "volatility",
    "自己資本比率": "equity_ratio",
    "営業利益率": "operating_margin",
    "売上成長率": "revenue_growth_pct",
    "経費率": "expense_ratio",
    "NISA": "nisa_eligibility",
    "投資スタイル": "investment_style",
    "連動指数": "benchmark_index",
    "複雑性": "complexity",
    "並べ替え理由": "ranking_reason",
    "確認ポイント": "confirmation_point",
    "SMAIメモ": "smai_memo",
    "注意点": "warning",
}


@dataclass(frozen=True)
class RankingHistorySortOption:
    key: str
    label: str
    field: str
    descending: bool


@dataclass(frozen=True)
class RankingHistoryCardView:
    run_id: str
    style_class: str
    created_at: str
    target_label: str
    ranking_label: str
    metadata_chips: tuple[str, ...]
    condition_chips: tuple[str, ...]
    top_symbol_tags: tuple[str, ...]
    is_pinned: bool
    snapshot_available: bool


HISTORY_SORT_DEFINITIONS = (
    RankingHistorySortOption("multi_factor", "AI総合", "total_score", True),
    RankingHistorySortOption("upside_signal", "上昇気配", "upside_signal_score", True),
    RankingHistorySortOption(
        "downside_low",
        "下振れ警戒が低い順",
        "downside_signal_score",
        False,
    ),
    RankingHistorySortOption("dividend", "配当利回り", "dividend_yield_pct", True),
    RankingHistorySortOption("per_low", "PERが低い順", "per", False),
    RankingHistorySortOption("pbr_low", "PBRが低い順", "pbr", False),
    RankingHistorySortOption("roe", "ROEが高い順", "roe_pct", True),
    RankingHistorySortOption(
        "data_confidence",
        "データ信頼度",
        "data_quality_score",
        True,
    ),
)


def build_ranking_history_save_request(
    *,
    rows: list[dict[str, str]],
    filters: Mapping[str, Any],
    provider: str,
    data_as_of: date,
    start: date,
    end: date,
    ranking_type: str,
    weight_preset: str,
    product_type: str,
    target_label: str,
    condition_summary: str,
    candidate_count: int,
    ranking_logic_version: str,
) -> RankingHistorySaveRequest:
    result_rows = [_history_row(row, rank=index) for index, row in enumerate(rows, start=1)]
    return RankingHistorySaveRequest(
        data_as_of=data_as_of,
        provider=provider,
        period=RankingHistoryPeriod(start=start, end=end),
        ranking_type=ranking_type,
        weight_preset=weight_preset,
        target=RankingHistoryTarget(
            region=str(filters.get("market_data_ranking_region", "all")),
            product_type=product_type,
            market=str(filters.get("market_data_ranking_market", "all")),
        ),
        target_label=target_label,
        filters=dict(filters),
        condition_summary=condition_summary,
        candidate_count=candidate_count,
        result_rows=result_rows,
        ranking_logic_version=ranking_logic_version,
    )


def save_ranking_history_for_current_user(
    user_id: str, request: RankingHistorySaveRequest
) -> RankingHistorySaveResult:
    return RankingHistoryService().save_ranking_history(user_id, request)


def synchronize_ranking_history_user(user_id: str) -> None:
    previous = st.session_state.get(RANKING_HISTORY_USER_KEY)
    if previous != user_id:
        st.session_state[RANKING_HISTORY_USER_KEY] = user_id
        st.session_state.pop(RANKING_HISTORY_SELECTED_KEY, None)
        st.session_state[RANKING_HISTORY_VIEW_KEY] = "live"


def render_ranking_history_list(user_id: str) -> None:
    st.title("ランキング履歴")
    if st.button("← ランキングへ戻る", use_container_width=False):
        st.session_state[RANKING_HISTORY_VIEW_KEY] = "live"
        st.rerun()
    if user_id == "default":
        render_ranking_history_default_user_notice()
        return
    result = RankingHistoryService().list_ranking_history(user_id)
    if result.error:
        render_ranking_history_error_notice(result.error)
        return
    if not result.items:
        render_ranking_history_empty_state()
        return
    pinned, normal = ranking_history_sections(result.items)
    st.caption(
        f"保存履歴 {len(result.items)}件 / ピン留め {len(pinned)}件 / 通常 {len(normal)} / 30件"
    )
    query = st.text_input("検索", key="ranking_history_search")
    selected_filter = st.selectbox(
        "表示",
        ["すべて", "ピン留め", "株式", "ETF", "AI総合"],
        key="ranking_history_filter",
    )
    pinned = filter_ranking_history_items(pinned, query, selected_filter)
    normal = filter_ranking_history_items(normal, query, selected_filter)
    service = RankingHistoryService()
    _render_history_section(
        "📌 ピン留め済み",
        pinned,
        service=service,
        user_id=user_id,
        empty_message="該当するピン留め履歴はありません。",
    )
    _render_history_section(
        "通常履歴",
        normal,
        service=service,
        user_id=user_id,
        empty_message=(
            "まだランキング履歴がありません。ランキングを作成すると、ここに保存されます。"
        ),
    )


def render_ranking_history_detail(
    user_id: str,
    *,
    render_result_table: Callable[[list[dict[str, str]], str, str], None],
    open_current_symbol: Callable[[str], None] | None = None,
) -> None:
    run_id = str(st.session_state.get(RANKING_HISTORY_SELECTED_KEY, ""))
    result = RankingHistoryService().get_ranking_history(user_id, run_id)
    if result.snapshot is None:
        st.session_state[RANKING_HISTORY_VIEW_KEY] = "history_list"
        render_ranking_history_error_notice(result.error or "履歴が見つかりません。")
        if st.button("履歴一覧へ戻る"):
            st.rerun()
        return
    snapshot = result.snapshot
    st.title("ランキング履歴詳細")
    back_col, live_col = st.columns(2)
    if back_col.button("← 履歴一覧へ戻る", use_container_width=True):
        st.session_state[RANKING_HISTORY_VIEW_KEY] = "history_list"
        st.rerun()
    if live_col.button("ランキング画面へ戻る", use_container_width=True):
        st.session_state[RANKING_HISTORY_VIEW_KEY] = "live"
        st.rerun()
    st.subheader(
        f"{'📌 ピン留め中' if snapshot.is_pinned else '未ピン留め'}｜{snapshot.target_label}"
    )
    st.caption(
        f"種別: {snapshot.ranking_type} / 作成日時: {snapshot.created_at:%Y/%m/%d %H:%M} / "
        f"データ取得日: {snapshot.data_as_of} / provider: {snapshot.provider}"
    )
    st.caption(
        f"取得期間: {snapshot.period.start} 〜 {snapshot.period.end} / "
        f"候補: {snapshot.candidate_count}件 / 保存: {snapshot.saved_row_count}件"
    )
    restore_col, pin_col, delete_col = st.columns(3)
    if restore_col.button("この条件で再ランキング", use_container_width=True):
        restore_ranking_filters(snapshot.filters)
        st.session_state[RANKING_HISTORY_NOTICE_KEY] = (
            "過去の検索条件をランキング画面に復元しました。"
            "条件を確認して「ランキング作成」を押してください。"
        )
        st.session_state[RANKING_HISTORY_VIEW_KEY] = "live"
        st.rerun()
    pin_label = "📌 ピン留め解除" if snapshot.is_pinned else "📌 ピン留めする"
    if pin_col.button(pin_label, use_container_width=True):
        mutation = RankingHistoryService().set_pinned(
            user_id, snapshot.run_id, not snapshot.is_pinned
        )
        if mutation.success:
            st.rerun()
        st.error(mutation.error or "更新に失敗しました。")
    if delete_col.button("削除", use_container_width=True):
        st.session_state[f"ranking_history_delete_{snapshot.run_id}"] = True
    if st.session_state.get(f"ranking_history_delete_{snapshot.run_id}"):
        warning = (
            "ピン留め済みの履歴を削除します。元に戻せません。"
            if snapshot.is_pinned
            else "この履歴を削除します。元に戻せません。"
        )
        st.warning(warning)
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button("削除を確定", type="primary", use_container_width=True):
            mutation = RankingHistoryService().delete_ranking_history(
                user_id,
                snapshot.run_id,
            )
            if mutation.success:
                st.session_state[RANKING_HISTORY_VIEW_KEY] = "history_list"
                st.session_state.pop(RANKING_HISTORY_SELECTED_KEY, None)
                st.rerun()
            st.error(mutation.error or "削除に失敗しました。")
        if cancel_col.button("キャンセル", use_container_width=True):
            st.session_state.pop(f"ranking_history_delete_{snapshot.run_id}", None)
            st.rerun()

    _render_history_detail_summary(snapshot)
    st.warning(HISTORY_NOTICE)

    sort_options = history_sort_options(snapshot)
    initial_sort_key = history_initial_sort_key(snapshot, sort_options)
    sort_state_key = f"ranking_history_sort_{snapshot.run_id}"
    if st.session_state.get(sort_state_key) not in {option.key for option in sort_options}:
        st.session_state[sort_state_key] = initial_sort_key
    selected_sort_key = st.selectbox(
        "表示中の並べ替え",
        [option.key for option in sort_options],
        key=sort_state_key,
        format_func=lambda key: next(option.label for option in sort_options if option.key == key),
    )
    selected_sort = next(option for option in sort_options if option.key == selected_sort_key)
    saved_label = ranking_policy_label(snapshot.ranking_type)
    if selected_sort.key == initial_sort_key:
        st.caption(f"保存時の基準: {saved_label} / 保存時の基準で表示中です")
    else:
        st.caption(f"保存時の基準: {saved_label} / 現在の表示並び: {selected_sort.label}")
    sorted_rows = sort_history_rows(snapshot.result_rows, selected_sort)

    _render_history_candidate_cards(sorted_rows)
    _render_history_bar_chart(sorted_rows, selected_sort)
    _render_history_signal_map(sorted_rows)

    st.markdown("#### ランキング結果を深掘り")
    st.caption(
        "気になる銘柄を1つ選び、銘柄コックピットで現在の価格・予測・スコア理由を確認します。"
    )
    symbols = [row.symbol for row in sorted_rows]
    if symbols and open_current_symbol is not None:
        row_by_symbol = {row.symbol: row for row in sorted_rows}
        symbol = st.selectbox(
            "深掘りする銘柄",
            symbols,
            key=f"ranking_history_current_symbol_{snapshot.run_id}",
            format_func=lambda value: _history_symbol_option_label(
                row_by_symbol[value],
                sorted_rows.index(row_by_symbol[value]) + 1,
            ),
        )
        st.button(
            "コックピットで現在情報を確認",
            key=f"ranking_history_open_current_{snapshot.run_id}",
            on_click=open_current_symbol,
            args=(symbol,),
            use_container_width=True,
        )
    st.markdown("#### 詳細テーブル")
    st.caption("以下は保存時点の結果です。テーブル内の操作では現在データを再取得しません。")
    render_result_table(
        history_display_rows(sorted_rows),
        snapshot.run_id,
        snapshot.weight_preset,
    )


def ranking_history_sections(
    items: list[RankingHistoryIndexItem],
) -> tuple[list[RankingHistoryIndexItem], list[RankingHistoryIndexItem]]:
    ordered = sorted(items, key=lambda item: item.created_at, reverse=True)
    return (
        [item for item in ordered if item.is_pinned],
        [item for item in ordered if not item.is_pinned],
    )


def filter_ranking_history_items(
    items: list[RankingHistoryIndexItem], query: str, selected_filter: str = "すべて"
) -> list[RankingHistoryIndexItem]:
    needle = query.strip().lower()
    filtered: list[RankingHistoryIndexItem] = []
    for item in items:
        haystack = " ".join(
            [
                item.title or "",
                item.memo or "",
                item.condition_summary,
                " ".join(item.top_symbols),
                item.target_label,
                item.ranking_type,
            ]
        ).lower()
        if needle and needle not in haystack:
            continue
        if selected_filter == "ピン留め" and not item.is_pinned:
            continue
        if selected_filter == "株式" and item.target.product_type != "stock":
            continue
        if selected_filter == "ETF" and item.target.product_type != "etf":
            continue
        if selected_filter == "AI総合" and item.ranking_type != "multi_factor":
            continue
        filtered.append(item)
    return filtered


def ranking_history_card_view(
    item: RankingHistoryIndexItem,
    *,
    snapshot: RankingHistorySnapshot | None,
    index: int,
) -> RankingHistoryCardView:
    metadata = [
        f"データ取得日 {item.data_as_of}",
        f"候補 {item.candidate_count}件",
        f"保存 {item.saved_row_count}件",
        item.target_label,
        _product_type_label(item.target.product_type),
    ]
    if snapshot is not None:
        metadata.append(_provider_label(snapshot.provider))
    style = (
        "smai-ranking-history-card--pinned"
        if item.is_pinned
        else ("smai-ranking-history-card--alt" if index % 2 else "")
    )
    return RankingHistoryCardView(
        run_id=item.run_id,
        style_class=style,
        created_at=item.created_at.strftime("%Y/%m/%d %H:%M"),
        target_label=item.target_label,
        ranking_label=ranking_policy_label(item.ranking_type),
        metadata_chips=tuple(metadata),
        condition_chips=tuple(
            ranking_history_condition_chips(
                snapshot.filters if snapshot is not None else {},
                item.condition_summary,
                ranking_type=item.ranking_type,
                product_type=item.target.product_type,
            )
        ),
        top_symbol_tags=tuple(
            f"#{rank} {symbol}" for rank, symbol in enumerate(item.top_symbols[:3], start=1)
        ),
        is_pinned=item.is_pinned,
        snapshot_available=item.snapshot_status == "available",
    )


def ranking_history_condition_chips(
    filters: Mapping[str, Any],
    condition_summary: str,
    *,
    ranking_type: str,
    product_type: str,
    limit: int = 7,
) -> list[str]:
    chips = [
        ranking_policy_label(ranking_type),
        _product_type_label(product_type),
    ]
    for key, prefix in (
        ("market_data_ranking_market", "国・市場"),
        ("market_data_ranking_official_sector", "セクター"),
        ("market_data_ranking_theme", "テーマ"),
    ):
        value = str(filters.get(key, "")).strip()
        if value and value != "all":
            chips.append(f"{prefix}: {value}")
    if str(filters.get("market_data_ranking_dividend_enabled", "")).lower() == "true":
        minimum = filters.get("market_data_ranking_min_dividend", "0")
        chips.append(f"配当利回り {minimum}%以上")
    summary_parts = [
        part.removeprefix("条件:").strip() for part in condition_summary.split("/") if part.strip()
    ]
    for part in summary_parts:
        if part and part not in chips and not any(part in chip for chip in chips):
            chips.append(part)
    detail_active = any(
        str(value).strip().lower() not in {"", "all", "false", "0", "0.0", "standard"}
        for key, value in filters.items()
        if key
        not in {
            "market_data_ranking_region",
            "market_data_ranking_product_type",
            "market_data_ranking_policy",
            "market_data_ranking_period",
            "market_data_ranking_fetch_limit",
        }
    )
    chips.append("詳細条件あり" if detail_active else "詳細条件なし")
    deduped = list(dict.fromkeys(chips))
    if len(deduped) <= limit:
        return deduped
    return [*deduped[: limit - 1], f"+{len(deduped) - limit + 1}条件"]


def history_sort_options(snapshot: RankingHistorySnapshot) -> list[RankingHistorySortOption]:
    options = [
        option
        for option in HISTORY_SORT_DEFINITIONS
        if any(getattr(row, option.field) is not None for row in snapshot.result_rows)
    ]
    return options or [RankingHistorySortOption("saved_order", "保存時の並び", "rank", False)]


def history_initial_sort_key(
    snapshot: RankingHistorySnapshot,
    options: list[RankingHistorySortOption],
) -> str:
    aliases = {
        "multi_factor": "multi_factor",
        "upside_signal": "upside_signal",
        "sustainable_income": "dividend",
        "quality_value": "per_low",
        "data_confidence": "data_confidence",
    }
    preferred = aliases.get(snapshot.ranking_type, snapshot.ranking_type)
    return preferred if any(option.key == preferred for option in options) else options[0].key


def sort_history_rows(
    rows: list[RankingHistoryResultRow],
    option: RankingHistorySortOption,
) -> list[RankingHistoryResultRow]:
    present = [row for row in rows if getattr(row, option.field) is not None]
    missing = [row for row in rows if getattr(row, option.field) is None]
    present.sort(
        key=lambda row: (
            float(getattr(row, option.field)),
            row.symbol,
        ),
        reverse=option.descending,
    )
    return [*present, *missing]


def history_bar_chart_rows(
    rows: list[RankingHistoryResultRow],
    option: RankingHistorySortOption,
) -> list[dict[str, Any]]:
    return [
        {
            "rank": index,
            "symbol": row.symbol,
            "name": row.name or "",
            "value": getattr(row, option.field),
            "label": f"{row.symbol} {row.name or ''}".strip(),
        }
        for index, row in enumerate(rows[:10], start=1)
        if getattr(row, option.field) is not None
    ]


def history_signal_map_rows(
    rows: list[RankingHistoryResultRow],
) -> list[dict[str, Any]]:
    return [
        {
            "symbol": row.symbol,
            "name": row.name or "",
            "upside": row.upside_signal_score,
            "downside": row.downside_signal_score,
            "risk": row.risk_score,
        }
        for row in rows
        if row.upside_signal_score is not None and row.downside_signal_score is not None
    ]


def snapshot_display_rows(snapshot: RankingHistorySnapshot) -> list[dict[str, str]]:
    return [dict(row.display) for row in snapshot.result_rows]


def history_display_rows(rows: list[RankingHistoryResultRow]) -> list[dict[str, str]]:
    display_rows: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        display = dict(row.display)
        display["順位"] = str(index)
        display_rows.append(display)
    return display_rows


def render_ranking_history_empty_state() -> None:
    st.info("保存済みのランキング履歴はありません。ランキングを作成するとここに保存されます。")


def render_ranking_history_default_user_notice() -> None:
    st.info(
        "ランキング履歴を保存・表示するには、ローカルプロフィールを選択または作成してください。"
    )


def render_ranking_history_error_notice(message: str) -> None:
    st.warning(f"ランキング履歴を読み込めませんでした。{message}")


def _render_history_section(
    title: str,
    items: list[RankingHistoryIndexItem],
    *,
    service: RankingHistoryService,
    user_id: str,
    empty_message: str,
) -> None:
    st.subheader(title)
    if not items:
        st.caption(empty_message)
        return
    columns = st.columns(2)
    for index, item in enumerate(items):
        snapshot = service.get_ranking_history(user_id, item.run_id).snapshot
        card = ranking_history_card_view(item, snapshot=snapshot, index=index)
        with columns[index % 2]:
            st.markdown(_ranking_history_card_html(card), unsafe_allow_html=True)
            if st.button(
                "詳細を見る",
                key=f"ranking_history_open_{item.run_id}",
                disabled=not card.snapshot_available,
                use_container_width=True,
            ):
                st.session_state[RANKING_HISTORY_SELECTED_KEY] = item.run_id
                st.session_state[RANKING_HISTORY_VIEW_KEY] = "history_detail"
                st.rerun()


def _ranking_history_card_html(card: RankingHistoryCardView) -> str:
    metadata = "".join(
        f'<span class="smai-ranking-history-chip">{html.escape(chip)}</span>'
        for chip in card.metadata_chips
    )
    conditions = "".join(
        f'<span class="smai-ranking-history-chip smai-ranking-history-chip--condition">'
        f"{html.escape(chip)}</span>"
        for chip in card.condition_chips
    )
    symbols = "".join(
        f'<span class="smai-ranking-history-symbol-tag">{html.escape(tag)}</span>'
        for tag in card.top_symbol_tags
    )
    pin = (
        '<span class="smai-ranking-history-badge smai-ranking-history-badge--pinned">'
        "📌 ピン留め済み</span>"
        if card.is_pinned
        else ""
    )
    classes = f"smai-ranking-history-card {card.style_class}".strip()
    return (
        f'<article class="{classes}">'
        '<div class="smai-ranking-history-card-header">'
        f"<time>{html.escape(card.created_at)}</time>{pin}"
        "</div>"
        '<div class="smai-ranking-history-card-title">'
        f"<strong>{html.escape(card.target_label)}</strong>"
        f'<span class="smai-ranking-history-badge">{html.escape(card.ranking_label)}</span>'
        "</div>"
        f'<div class="smai-ranking-history-chip-row">{metadata}</div>'
        '<div class="smai-ranking-history-card-label">保存時の条件</div>'
        f'<div class="smai-ranking-history-chip-row">{conditions}</div>'
        '<div class="smai-ranking-history-card-label">上位銘柄</div>'
        f'<div class="smai-ranking-history-symbol-row">{symbols or "未取得"}</div>'
        "</article>"
    )


def _render_history_detail_summary(snapshot: RankingHistorySnapshot) -> None:
    chips = ranking_history_condition_chips(
        snapshot.filters,
        snapshot.condition_summary,
        ranking_type=snapshot.ranking_type,
        product_type=snapshot.target.product_type,
    )
    chip_html = "".join(
        f'<span class="smai-ranking-history-chip smai-ranking-history-chip--condition">'
        f"{html.escape(chip)}</span>"
        for chip in chips
    )
    weights = ranking_purpose_weight_summary(snapshot.ranking_type, limit=5)
    weight_html = "".join(
        f'<span class="smai-ranking-history-chip">{html.escape(weight)}</span>'
        for weight in weights
    )
    policy = ranking_policy_label(snapshot.ranking_type)
    description = ranking_policy_description(snapshot.ranking_type)["short_summary"]
    st.markdown(
        '<section class="smai-ranking-history-detail-summary">'
        '<article class="smai-ranking-history-summary-card">'
        '<div class="smai-ranking-history-card-label">保存時のランキング候補</div>'
        f"<strong>候補 {snapshot.candidate_count}件 / 保存 {snapshot.saved_row_count}件</strong>"
        "<p>ここで絞った候補だけを、保存時のランキング基準で並べています。</p>"
        f'<div class="smai-ranking-history-chip-row">{chip_html}</div>'
        "</article>"
        '<article class="smai-ranking-history-summary-card">'
        '<div class="smai-ranking-history-card-label">保存時のランキング基準</div>'
        f"<strong>{html.escape(policy)}</strong>"
        f"<p>{html.escape(description)}</p>"
        f'<div class="smai-ranking-history-chip-row">{weight_html}</div>'
        "</article>"
        "</section>",
        unsafe_allow_html=True,
    )


def _render_history_candidate_cards(rows: list[RankingHistoryResultRow]) -> None:
    st.markdown("#### 注目候補")
    if not rows:
        st.info("表示できる保存候補がありません。")
        return
    columns = st.columns(min(5, len(rows[:5])))
    for index, row in enumerate(rows[:5], start=1):
        with columns[index - 1]:
            memo = row.smai_memo or row.ranking_reason or row.confirmation_point or ""
            metrics = [
                ("総合", row.total_score),
                ("上昇気配", row.upside_signal_score),
                ("下振れ警戒", row.downside_signal_score),
            ]
            metric_html = "".join(
                f"<span>{html.escape(label)} <strong>{value:.1f}</strong></span>"
                for label, value in metrics
                if value is not None
            )
            st.markdown(
                '<article class="smai-ranking-history-metric-card">'
                f'<span class="smai-ranking-history-rank">#{index}</span>'
                f"<strong>{html.escape(row.symbol)}</strong>"
                f"<small>{html.escape(row.name or '銘柄名未取得')}</small>"
                f'<div class="smai-ranking-history-metrics">{metric_html}</div>'
                f"<p>{html.escape(memo)}</p>"
                "</article>",
                unsafe_allow_html=True,
            )


def _render_history_bar_chart(
    rows: list[RankingHistoryResultRow],
    option: RankingHistorySortOption,
) -> None:
    st.markdown(f"#### 上位10件: {option.label}")
    chart_rows = history_bar_chart_rows(rows, option)
    if not chart_rows:
        st.info(f"{option.label}をグラフ化できる保存データがありません。")
        return
    frame = pd.DataFrame(chart_rows)
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            x=alt.X("value:Q", title=option.label),
            y=alt.Y("label:N", sort=alt.SortField("rank", order="ascending"), title=None),
            tooltip=[
                alt.Tooltip("rank:Q", title="表示順位"),
                alt.Tooltip("symbol:N", title="銘柄コード"),
                alt.Tooltip("name:N", title="銘柄名"),
                alt.Tooltip("value:Q", title=option.label, format=".1f"),
            ],
            color=alt.value(CHART_COLORS["ai"]),
        )
        .properties(height=max(260, min(420, 34 * len(frame))))
    )
    st.altair_chart(style_altair_chart(chart), use_container_width=True)


def _render_history_signal_map(rows: list[RankingHistoryResultRow]) -> None:
    st.markdown("#### 上昇気配 × 下振れ警戒マップ")
    chart_rows = history_signal_map_rows(rows)
    if not chart_rows:
        st.info("保存データに上昇気配・下振れ警戒の情報がないため、マップを表示できません。")
        return
    frame = pd.DataFrame(chart_rows)
    chart = (
        alt.Chart(frame)
        .mark_circle(size=100, opacity=0.82)
        .encode(
            x=alt.X("upside:Q", title="上昇気配"),
            y=alt.Y("downside:Q", title="下振れ警戒"),
            color=alt.Color(
                "downside:Q",
                title="下振れ警戒",
                scale=alt.Scale(
                    domain=[0, 100],
                    range=[THEME_COLORS["signal_buy"], THEME_COLORS["signal_sell"]],
                ),
            ),
            tooltip=[
                alt.Tooltip("symbol:N", title="銘柄コード"),
                alt.Tooltip("name:N", title="銘柄名"),
                alt.Tooltip("upside:Q", title="上昇気配", format=".1f"),
                alt.Tooltip("downside:Q", title="下振れ警戒", format=".1f"),
            ],
        )
        .properties(height=360)
    )
    labels = chart.mark_text(align="left", dx=7, dy=-7, color=THEME_COLORS["text_primary"]).encode(
        text="symbol:N"
    )
    st.altair_chart(style_altair_chart(chart + labels), use_container_width=True)


def _history_symbol_option_label(row: RankingHistoryResultRow, rank: int) -> str:
    return f"{rank}位｜{row.symbol} - {row.name or '銘柄名未取得'}"


def _product_type_label(value: str) -> str:
    return {
        "stock": "株式",
        "etf": "ETF",
        "mutual_fund": "投資信託",
        "all": "全商品",
    }.get(value, value or "商品未取得")


def _provider_label(value: str) -> str:
    return {"yahoo": "Yahoo", "mock": "Mock", "csv": "CSV"}.get(value, value)


def _history_row(row: Mapping[str, Any], *, rank: int) -> RankingHistoryResultRow:
    values: dict[str, Any] = {
        "rank": _integer(row.get("順位")) or rank,
        "symbol": str(row.get("銘柄") or row.get("symbol") or "").strip().upper(),
        "name": _text(row.get("銘柄名") or row.get("name")),
        "market": _text(row.get("市場") or row.get("market")),
        "country": _text(row.get("国") or row.get("country")),
        "asset_type": _text(row.get("商品") or row.get("asset_type")),
        "currency": _text(row.get("通貨") or row.get("currency")),
        "favorite_status_at_save": str(row.get("お気に入り", "")).startswith("★"),
        "display": {str(key): str(value) for key, value in row.items()},
    }
    for label, field in DISPLAY_TO_FIELD.items():
        if label not in row or field in values:
            continue
        if field in {
            "model_direction",
            "nisa_eligibility",
            "investment_style",
            "benchmark_index",
            "complexity",
            "ranking_reason",
            "confirmation_point",
            "smai_memo",
            "warning",
        }:
            values[field] = _text(row.get(label))
        elif field in {"rank", "forecast_days"}:
            values[field] = _integer(row.get(label))
        else:
            values[field] = _number(row.get(label))
    if not values["symbol"]:
        raise ValueError("Ranking history row requires a symbol.")
    return RankingHistoryResultRow(**values)


def _number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("%", "").strip()
    if not text or text in {"N/A", "-", "未取得", "未計算"}:
        return None
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
