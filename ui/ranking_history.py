from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

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
from ui.ranking_state import restore_ranking_filters

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
    _render_history_section("📌 ピン留め済み", pinned)
    _render_history_section("通常履歴", normal)


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
    with st.expander("検索条件", expanded=True):
        st.write(snapshot.condition_summary)
    st.warning(HISTORY_NOTICE)
    symbols = [row.symbol for row in snapshot.result_rows]
    if symbols and open_current_symbol is not None:
        symbol = st.selectbox(
            "現在情報を確認する銘柄",
            symbols,
            key=f"ranking_history_current_symbol_{snapshot.run_id}",
        )
        st.button(
            "現在の銘柄を確認",
            key=f"ranking_history_open_current_{snapshot.run_id}",
            on_click=open_current_symbol,
            args=(symbol,),
        )
    render_result_table(snapshot_display_rows(snapshot), snapshot.run_id, snapshot.weight_preset)


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


def snapshot_display_rows(snapshot: RankingHistorySnapshot) -> list[dict[str, str]]:
    return [dict(row.display) for row in snapshot.result_rows]


def render_ranking_history_empty_state() -> None:
    st.info("保存済みのランキング履歴はありません。ランキングを作成するとここに保存されます。")


def render_ranking_history_default_user_notice() -> None:
    st.info(
        "ランキング履歴を保存・表示するには、ローカルプロフィールを選択または作成してください。"
    )


def render_ranking_history_error_notice(message: str) -> None:
    st.warning(f"ランキング履歴を読み込めませんでした。{message}")


def _render_history_section(title: str, items: list[RankingHistoryIndexItem]) -> None:
    st.subheader(title)
    if not items:
        st.caption("該当する履歴はありません。")
        return
    for item in items:
        with st.container(border=True):
            st.markdown(
                f"**{item.created_at:%Y/%m/%d %H:%M}｜"
                f"{item.target_label}｜{item.ranking_type}**"
            )
            st.caption(
                f"データ取得日 {item.data_as_of} / 候補 {item.candidate_count}件 / "
                f"上位: {', '.join(item.top_symbols) or '未取得'}"
            )
            st.write(item.condition_summary)
            if item.snapshot_status != "available":
                st.warning("詳細データを読み込めません。")
            if st.button(
                "詳細を見る",
                key=f"ranking_history_open_{item.run_id}",
                disabled=item.snapshot_status != "available",
            ):
                st.session_state[RANKING_HISTORY_SELECTED_KEY] = item.run_id
                st.session_state[RANKING_HISTORY_VIEW_KEY] = "history_detail"
                st.rerun()


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
