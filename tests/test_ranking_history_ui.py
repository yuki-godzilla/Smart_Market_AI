from datetime import UTC, date, datetime

from backend.ranking_history.models import (
    RankingHistoryIndexItem,
    RankingHistoryPeriod,
    RankingHistoryResultRow,
    RankingHistorySnapshot,
    RankingHistoryTarget,
)
from ui.ranking_history import (
    filter_ranking_history_items,
    history_bar_chart_rows,
    history_initial_sort_key,
    history_signal_map_rows,
    history_sort_options,
    prepare_ranking_history_view_for_page,
    ranking_history_card_view,
    ranking_history_condition_chips,
    ranking_history_sections,
    sort_history_rows,
)
from ui.ranking_state import restore_ranking_filters


def _item(run_id: str, minute: int, *, pinned: bool = False, condition: str = "AI総合"):
    return RankingHistoryIndexItem(
        run_id=run_id,
        user_id="u_abcdefgh",
        created_at=datetime(2026, 7, 3, 0, minute, tzinfo=UTC),
        data_as_of=date(2026, 7, 2),
        ranking_type="multi_factor",
        target=RankingHistoryTarget(product_type="stock"),
        target_label="米国株",
        condition_summary=condition,
        candidate_count=2,
        saved_row_count=2,
        top_symbols=["AAPL", "MSFT"],
        is_pinned=pinned,
        snapshot_file=f"{run_id}.json.gz",
        signature=f"sha256:{run_id}",
    )


def _snapshot() -> RankingHistorySnapshot:
    return RankingHistorySnapshot(
        run_id="rh_20260703T000000Z_aaaaaaaa",
        user_id="u_abcdefgh",
        created_at=datetime(2026, 7, 3, tzinfo=UTC),
        data_as_of=date(2026, 7, 2),
        provider="yahoo",
        period=RankingHistoryPeriod(start=date(2026, 1, 1), end=date(2026, 7, 2)),
        ranking_type="multi_factor",
        weight_preset="multi_factor",
        target=RankingHistoryTarget(product_type="stock", market="us"),
        target_label="米国株",
        filters={
            "market_data_ranking_product_type": "stock",
            "market_data_ranking_market": "us",
            "market_data_ranking_dividend_enabled": "False",
        },
        condition_summary="条件: 全体 / 株式 / 評価方針: AI総合 / 米国",
        candidate_count=3,
        saved_row_count=3,
        top_symbols=["AAA", "BBB", "CCC"],
        result_rows=[
            RankingHistoryResultRow(
                rank=1,
                symbol="AAA",
                total_score=70,
                upside_signal_score=60,
                downside_signal_score=30,
                per=20,
                display={"順位": "1", "銘柄": "AAA", "総合スコア": "70"},
            ),
            RankingHistoryResultRow(
                rank=2,
                symbol="BBB",
                total_score=90,
                upside_signal_score=50,
                downside_signal_score=20,
                per=10,
                display={"順位": "2", "銘柄": "BBB", "総合スコア": "90"},
            ),
            RankingHistoryResultRow(
                rank=3,
                symbol="CCC",
                total_score=80,
                upside_signal_score=None,
                downside_signal_score=None,
                per=None,
                display={"順位": "3", "銘柄": "CCC", "総合スコア": "80"},
            ),
        ],
        ranking_logic_version="test",
        signature="sha256:test",
    )


def test_sections_put_pinned_first_and_sort_each_newest_first():
    pinned, normal = ranking_history_sections(
        [
            _item("rh_20260703T000000Z_aaaaaaaa", 0),
            _item("rh_20260703T000200Z_bbbbbbbb", 2, pinned=True),
            _item("rh_20260703T000100Z_cccccccc", 1),
        ]
    )
    assert [item.created_at.minute for item in pinned] == [2]
    assert [item.created_at.minute for item in normal] == [1, 0]


def test_search_matches_condition_and_top_symbols():
    items = [_item("rh_20260703T000000Z_aaaaaaaa", 0, condition="高配当")]
    assert filter_ranking_history_items(items, "高配当") == items
    assert filter_ranking_history_items(items, "msft") == items
    assert filter_ranking_history_items(items, "該当なし") == []


def test_card_view_applies_alternating_and_pinned_styles_with_tags():
    snapshot = _snapshot()
    alternate = ranking_history_card_view(
        _item(snapshot.run_id, 0),
        snapshot=snapshot,
        index=1,
    )
    pinned = ranking_history_card_view(
        _item(snapshot.run_id, 0, pinned=True),
        snapshot=snapshot,
        index=0,
    )
    assert alternate.style_class == "smai-ranking-history-card--alt"
    assert pinned.style_class == "smai-ranking-history-card--pinned"
    assert alternate.top_symbol_tags == ("#1 AAPL", "#2 MSFT")
    assert "Yahoo" in alternate.metadata_chips


def test_condition_chips_prioritize_policy_product_and_market():
    snapshot = _snapshot()
    chips = ranking_history_condition_chips(
        snapshot.filters,
        snapshot.condition_summary,
        ranking_type=snapshot.ranking_type,
        product_type=snapshot.target.product_type,
    )
    assert chips[0:2] == ["AI総合", "株式"]
    assert "国・市場: us" in chips


def test_sort_options_use_saved_policy_and_sort_without_mutating_snapshot():
    snapshot = _snapshot()
    original_symbols = [row.symbol for row in snapshot.result_rows]
    options = history_sort_options(snapshot)
    assert history_initial_sort_key(snapshot, options) == "multi_factor"
    total = next(option for option in options if option.key == "multi_factor")
    per = next(option for option in options if option.key == "per_low")
    assert [row.symbol for row in sort_history_rows(snapshot.result_rows, total)] == [
        "BBB",
        "CCC",
        "AAA",
    ]
    assert [row.symbol for row in sort_history_rows(snapshot.result_rows, per)] == [
        "BBB",
        "AAA",
        "CCC",
    ]
    assert [row.symbol for row in snapshot.result_rows] == original_symbols


def test_chart_rows_use_top_ten_and_signal_map_skips_missing_values():
    snapshot = _snapshot()
    option = next(
        option for option in history_sort_options(snapshot) if option.key == "multi_factor"
    )
    sorted_rows = sort_history_rows(snapshot.result_rows, option)
    assert [row["symbol"] for row in history_bar_chart_rows(sorted_rows, option)] == [
        "BBB",
        "CCC",
        "AAA",
    ]
    assert [row["symbol"] for row in history_signal_map_rows(sorted_rows)] == [
        "BBB",
        "AAA",
    ]


def test_restore_filters_uses_allowlist_and_clears_results(monkeypatch):
    session_state = {
        "market_data_ranking_rows": [{"symbol": "OLD"}],
        "market_data_ranking_error_rows": [{"error": "OLD"}],
    }
    monkeypatch.setattr("ui.ranking_state.st.session_state", session_state)
    result = restore_ranking_filters(
        {
            "market_data_ranking_product_type": "stock",
            "market_data_ranking_per_enabled": True,
            "unknown_filter": "ignored",
        }
    )
    assert session_state["market_data_ranking_product_type"] == "stock"
    assert session_state["market_data_ranking_per_enabled"] is True
    assert "market_data_ranking_rows" not in session_state
    assert result.ignored_keys == ("unknown_filter",)


def test_entering_ranking_from_another_page_resets_history_subview(monkeypatch):
    session_state = {
        "ranking_history_last_rendered_page": "cockpit",
        "ranking_view_mode": "history_detail",
        "selected_ranking_history_id": "rh_20260703T000000Z_aaaaaaaa",
    }
    monkeypatch.setattr("ui.ranking_history.st.session_state", session_state)

    assert prepare_ranking_history_view_for_page("ranking") is True
    assert session_state["ranking_view_mode"] == "live"
    assert "selected_ranking_history_id" not in session_state


def test_ranking_internal_rerun_keeps_history_subview(monkeypatch):
    session_state = {
        "ranking_history_last_rendered_page": "ranking",
        "ranking_view_mode": "history_list",
    }
    monkeypatch.setattr("ui.ranking_history.st.session_state", session_state)

    assert prepare_ranking_history_view_for_page("ranking") is False
    assert session_state["ranking_view_mode"] == "history_list"
