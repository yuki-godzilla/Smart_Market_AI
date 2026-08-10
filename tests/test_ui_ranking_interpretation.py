from __future__ import annotations

from datetime import date

from ui.ranking_interpretation import (
    build_ranking_interpretation_input,
    ranking_summary_cards,
)
from ui.views.ranking import ranking_interpretation_state_owner


def test_ui_adapter_copies_only_top_displayed_candidates_and_sector_metadata() -> None:
    rows = [_row("7203.T", "1", "82"), _row("6758.T", "2", "79")]
    cards = [
        _card("7203.T", "1", "総合スコア", "82"),
        _card("6758.T", "2", "総合スコア", "79"),
    ]

    value = build_ranking_interpretation_input(
        rows,
        cards,
        result_id="result-1",
        as_of=date(2026, 8, 10),
        ranking_policy="総合比較",
        weight_preset="バランス",
        region="日本",
        product_type="個別株",
        metadata_by_symbol={
            "7203.T": {"sector": "一般消費財", "provider_raw": "secret"},
            "6758.T": {"sector": "一般消費財", "user_note": "private"},
        },
        candidate_count=20,
    )

    assert value.candidate_count == 20
    assert [item.symbol for item in value.candidates] == ["7203.T", "6758.T"]
    assert value.sector_groups[0].candidate_count == 2
    assert value.sector_groups[0].primary_metric_average == "80.5"
    serialized = value.model_dump_json()
    assert "provider_raw" not in serialized
    assert "secret" not in serialized
    assert "user_note" not in serialized
    assert "private" not in serialized


def test_ranking_interpretation_state_owner_separates_user_and_context() -> None:
    first = ranking_interpretation_state_owner(user_id="user-a", context_hash="hash-a")

    assert first != ranking_interpretation_state_owner(user_id="user-b", context_hash="hash-a")
    assert first != ranking_interpretation_state_owner(user_id="user-a", context_hash="hash-b")


def test_ranking_summary_cards_remain_compatible_after_view_extraction() -> None:
    cards = ranking_summary_cards(
        [_row("7203.T", "1", "82"), _row("6758.T", "2", "78")],
        ranking_axis="総合比較",
        weight_preset="バランス",
        region="日本",
        product_type="個別株",
        selected_count=10,
    )

    assert [card["value"] for card in cards] == ["10", "2", "80.0", "2"]


def _row(symbol: str, rank: str, score: str) -> dict[str, str]:
    return {
        "順位": rank,
        "銘柄": symbol,
        "銘柄名": symbol,
        "総合スコア": score,
        "Screening": "75",
        "上昇気配": "62",
        "上向き兆候": "58",
        "下降警戒": "35",
        "Risk": "40",
        "データ品質": "90",
        "条件適合度": "85",
        "DB信頼度": "88",
        "予測変化率": "1.5%",
        "方向一致": "上昇 2 / 下降 1 / 横ばい 0",
        "注意点": "確認が必要です。",
    }


def _card(symbol: str, rank: str, label: str, value: str) -> dict[str, str]:
    return {
        "rank": rank,
        "symbol": symbol,
        "name": symbol,
        "score": value,
        "primary_label": label,
        "primary_value": value,
        "reason": "主要指標を確認します。",
        "confidence": "88",
        "downside": "35",
        "caution": "確認が必要です。",
        "research_status": "根拠あり",
    }
