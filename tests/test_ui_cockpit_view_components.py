from __future__ import annotations

from datetime import date

from backend.research import CompanyResearchReport, ResearchDataQuality
from ui.views.cockpit import (
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
    assert items[8]["help"] == "投資魅力度ではなく、評価に使えるデータの充実度です。"


def test_cockpit_kpi_cards_do_not_create_new_scores():
    cards = cockpit_kpi_cards(
        {
            "総合スコア": "72",
            "見方": "比較候補",
            "予測一致": "64",
            "データ品質": "95",
            "Risk": "68",
        }
    )

    assert [card["label"] for card in cards] == [
        "Investment Score",
        "Decision View",
        "Forecast Agreement",
        "Data Confidence",
        "Risk",
    ]
    assert [card["value"] for card in cards] == ["72", "比較候補", "64", "95", "68"]
    assert "投資魅力度ではありません" in cards[3]["help"]


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
