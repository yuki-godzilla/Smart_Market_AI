from __future__ import annotations

from datetime import date

from backend.research import CompanyResearchReport, ResearchDataQuality
from ui.views.cockpit import (
    cockpit_direction_signal_cards,
    cockpit_direction_signal_detail_rows,
    cockpit_direction_signal_summary,
    cockpit_kpi_cards,
    cockpit_summary_items,
    research_evidence_summary_items,
)


def test_cockpit_summary_items_use_existing_score_and_metadata_values():
    items = cockpit_summary_items(
        symbol="7203.T",
        name="Toyota Motor",
        provider="yahoo",
        as_of="2026-05-24",
        reference_period_days=90,
        forecast_horizon_days=7,
        score_row={
            "総合スコア": "72",
            "見方": "比較候補",
            "データ品質": "95",
            "Risk": "68",
        },
        symbol_metadata={
            "asset_type": "stock",
            "region": "japan",
            "sector": "Automobiles",
        },
    )

    assert items[0]["value"] == "7203.T"
    assert items[1]["value"] == "Toyota Motor"
    assert items[5]["value"] == "stock / japan / Automobiles"
    assert items[6]["value"] == "72"
    assert "投資魅力度ではなく" in items[8]["help_text"]
    assert "今回: 高め" in items[8]["caption"]


def test_cockpit_kpi_cards_do_not_create_new_scores():
    cards = cockpit_kpi_cards(
        {
            "総合スコア": "72",
            "見方": "比較候補",
            "方向スコア": "64",
            "データ品質": "95",
            "Risk": "68",
        }
    )

    assert [card["label"] for card in cards] == [
        "Investment Score",
        "Decision View",
        "方向バランス",
        "Data Confidence",
        "Risk",
    ]
    assert [card["value"] for card in cards] == ["72", "比較候補", "64", "95", "68"]
    assert "投資魅力度ではなく" in cards[3]["help_text"]
    assert "今回: やや上向き" in cards[2]["caption"]
    assert "今回: やや落ち着き" in cards[4]["caption"]


def test_cockpit_direction_signal_cards_use_existing_direction_values():
    cards = cockpit_direction_signal_cards(
        {
            "方向スコア": "72",
            "上昇気配": "78",
            "下降警戒": "34",
            "予測変化率": "+3.2%",
        },
        {
            "direction_net_score": "50",
            "upside_signal_score": "50",
            "downside_signal_score": "50",
            "forecast_return_pct": "0.0%",
        },
    )

    assert [card["label"] for card in cards] == [
        "方向バランス",
        "上昇気配",
        "下降警戒",
        "予測変化率",
    ]
    assert [card["value"] for card in cards] == ["72", "78", "34", "+3.2%"]
    assert "今回: 上向き寄り" in cards[0]["caption"]
    assert "今回: 強め" in cards[1]["caption"]
    assert "今回: 低め" in cards[2]["caption"]
    assert "今回: やや上向き" in cards[3]["caption"]
    assert "50付近は中立" in cards[0]["help_text"]


def test_cockpit_direction_signal_detail_rows_explain_balance_and_model_spread():
    rows = cockpit_direction_signal_detail_rows(
        {
            "方向スコア": "72",
            "上昇気配": "78",
            "下降警戒": "34",
            "予測変化率": "+3.2%",
            "方向一致": "上昇 2 / 下降 1 / 横ばい 0",
            "方向感": "上昇気配あり",
        },
        {
            "forecast_range_pct": "12.4%",
            "agreement": "LOW",
        },
    )

    assert rows[0]["観点"] == "方向感"
    assert rows[0]["内容"] == "上昇気配あり / 方向バランス 72"
    assert rows[1]["観点"] == "上昇・下降バランス"
    assert "上昇気配 78 / 下降警戒 34 / 方向バランス 72" in rows[1]["内容"]
    assert rows[3]["内容"] == "上昇 2 / 下降 1 / 横ばい 0"
    assert rows[4]["内容"] == "12.4% / モデル一致度 LOW"


def test_cockpit_direction_signal_summary_warns_on_high_downside():
    summary = cockpit_direction_signal_summary(
        {
            "方向スコア": "44",
            "上昇気配": "58",
            "下降警戒": "72",
            "予測変化率": "-2.4%",
        },
        None,
    )

    assert "下降警戒が72" in summary
    assert "予測変化率 -2.4%" in summary


def test_research_evidence_summary_items_explain_report_coverage():
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 5, 24),
        summary="3件の根拠を確認しました。",
        data_quality=ResearchDataQuality(
            status="WARN",
            document_count=1,
            evidence_count=3,
            latest_document_date=date(2026, 5, 23),
            warnings=["登録資料が少ない"],
        ),
        points=[],
        evidence=[],
    )

    items = research_evidence_summary_items(report)

    assert items[0]["value"] == "1"
    assert items[1]["value"] == "3"
    assert items[2]["value"] == "2026-05-23"
    assert items[3]["value"] == "WARN"
    assert items[4]["value"] == "1"
