from datetime import UTC, date, datetime

from backend.ranking_history.models import (
    RankingHistoryIndexItem,
    RankingHistoryTarget,
)
from ui.ranking_history import filter_ranking_history_items, ranking_history_sections
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
