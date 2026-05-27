from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.research import (
    CompanyResearchReport,
    ResearchDataQuality,
    ResearchEvidence,
    ResearchSummaryPoint,
)
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
            "上昇気配": "76",
            "下降警戒": "38",
            "データ品質": "95",
            "Risk": "68",
        }
    )

    assert [card["label"] for card in cards] == [
        "Investment Score",
        "上昇気配",
        "下降警戒",
        "Data Confidence",
        "Risk",
    ]
    assert [card["value"] for card in cards] == ["72", "76", "38", "95", "68"]
    assert "投資魅力度ではなく" in cards[3]["help_text"]
    assert "今回: 強め" in cards[1]["caption"]
    assert "今回: 低め" in cards[2]["caption"]
    assert "今回: やや落ち着き" in cards[4]["caption"]


def test_cockpit_direction_signal_cards_use_existing_direction_values():
    cards = cockpit_direction_signal_cards(
        {
            "上昇気配": "78",
            "下降警戒": "34",
            "予測変化率": "+3.2%",
        },
        {
            "upside_signal_score": "50",
            "downside_signal_score": "50",
            "forecast_return_pct": "0.0%",
        },
    )

    assert [card["label"] for card in cards] == [
        "上昇気配",
        "下降警戒",
        "予測変化率",
    ]
    assert [card["value"] for card in cards] == ["78", "34", "+3.2%"]
    assert "今回: 強め" in cards[0]["caption"]
    assert "今回: 低め" in cards[1]["caption"]
    assert "今回: やや上向き" in cards[2]["caption"]
    assert "予測エッジ" in cards[0]["help_text"]


def test_cockpit_direction_signal_detail_rows_explain_balance_and_model_spread():
    rows = cockpit_direction_signal_detail_rows(
        {
            "上昇気配": "78",
            "下降警戒": "34",
            "予測変化率": "+3.2%",
            "方向一致": "上昇 2 / 下降 1 / 横ばい 0",
        },
        {
            "forecast_range_pct": "12.4%",
            "agreement": "LOW",
        },
    )

    assert rows[0]["観点"] == "読み取り"
    assert rows[0]["内容"] == "上昇気配優勢 / 予測は上向き / ばらつき大きめ"
    assert "価格チャート" in rows[0]["確認ポイント"]
    assert rows[1]["観点"] == "上昇気配"
    assert rows[1]["内容"] == "78"
    assert rows[2]["観点"] == "下降警戒"
    assert rows[2]["内容"] == "34"
    assert "今回は上昇気配のほうが優勢" in rows[2]["確認ポイント"]
    assert rows[4]["内容"] == "上昇 2 / 下降 1 / 横ばい 0"
    assert rows[5]["内容"] == "12.4% / モデル一致度 LOW"
    assert "モデル一致度も低め" in rows[5]["確認ポイント"]


def test_cockpit_direction_signal_summary_warns_on_high_downside():
    summary = cockpit_direction_signal_summary(
        {
            "上昇気配": "58",
            "下降警戒": "72",
            "予測変化率": "-2.4%",
        },
        None,
    )

    assert "下降警戒が72" in summary
    assert "予測変化率は-2.4%" in summary
    assert "直近終値を下回っています" in summary


def test_cockpit_direction_signal_summary_handles_split_downside_case():
    summary = cockpit_direction_signal_summary(
        {
            "上昇気配": "36.71",
            "下降警戒": "65.04",
            "予測変化率": "-2.4%",
            "方向一致": "上昇 1 / 下降 1 / 横ばい 1",
        },
        {
            "forecast_range_pct": "13.29%",
            "agreement": "LOW",
        },
    )

    assert "下降警戒が65" in summary
    assert "上昇気配36.7" in summary
    assert "モデル方向は割れていて" in summary
    assert "予測の開きも13.29%" in summary
    assert "下落継続リスクと反転材料" in summary


def test_cockpit_direction_signal_summary_splits_high_low_and_missing_patterns():
    both_high = cockpit_direction_signal_summary(
        {
            "上昇気配": "72",
            "下降警戒": "69",
            "予測変化率": "+1.2%",
        },
        {"forecast_range_pct": "4.0%", "agreement": "70"},
    )
    both_low = cockpit_direction_signal_summary(
        {
            "上昇気配": "38",
            "下降警戒": "41",
            "予測変化率": "0.2%",
        },
        {"forecast_range_pct": "3.0%", "agreement": "80"},
    )
    missing = cockpit_direction_signal_summary(
        {
            "上昇気配": "50",
            "下降警戒": "50",
            "予測変化率": "0.0%",
            "方向一致": "上昇 0 / 下降 0 / 横ばい 0",
        },
        {"forecast_range_pct": "未計算", "agreement": "未計算"},
    )

    assert "どちらも強め" in both_high
    assert "どちらの方向材料も控えめ" in both_low
    assert "モデル方向の材料も不足" in missing


def test_cockpit_direction_signal_summary_prioritizes_spread_and_model_split():
    spread = cockpit_direction_signal_summary(
        {
            "上昇気配": "58",
            "下降警戒": "53",
            "予測変化率": "+0.8%",
        },
        {"forecast_range_pct": "14.2%", "agreement": "LOW"},
    )
    split = cockpit_direction_signal_summary(
        {
            "上昇気配": "56",
            "下降警戒": "51",
            "予測変化率": "+0.6%",
            "方向一致": "上昇 1 / 下降 1 / 横ばい 1",
        },
        {"forecast_range_pct": "4.0%", "agreement": "80"},
    )

    assert "予測のばらつきが14.2%" in spread
    assert "モデル方向が分散" in split
    assert "1モデルだけの見方" in split


def test_research_evidence_summary_items_explain_report_coverage():
    growth_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-growth",
        chunk_id="chunk-growth",
        title="Growth note",
        source_type="user_note",
        published_at=date(2026, 5, 22),
        excerpt="Growth strategy.",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.70"),
    )
    risk_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-risk",
        chunk_id="chunk-risk",
        title="Risk note",
        source_type="user_note",
        published_at=date(2026, 5, 22),
        excerpt="Risk factor.",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.70"),
    )
    news_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="doc-news",
        chunk_id="chunk-news",
        title="News note",
        source_type="news",
        published_at=date(2026, 5, 23),
        excerpt="News factor.",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.70"),
    )
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
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="成長材料を確認しました。",
                evidence=[growth_evidence],
            ),
            ResearchSummaryPoint(
                category="business_risk",
                label="事業リスク",
                summary="リスク材料を確認しました。",
                evidence=[risk_evidence],
            ),
        ],
        evidence=[news_evidence, growth_evidence, risk_evidence],
    )

    items = research_evidence_summary_items(report)

    assert items[0]["value"] == "1件"
    assert items[1]["value"] == "1件"
    assert items[2]["value"] == "1件"
    assert items[3]["value"] == "Medium"
    assert items[4]["value"] == "2026-05-23"
