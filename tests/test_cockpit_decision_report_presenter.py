from __future__ import annotations

from datetime import date

from backend.reporting import build_decision_report_context, build_report_section
from ui.cockpit_application import (
    build_cockpit_decision_report_render_context,
    build_cockpit_research_context,
)
from ui.cockpit_decision_report_presenter import (
    build_cockpit_decision_report_detail_model,
    cockpit_decision_report_overview_card_html,
    cockpit_decision_summary_list_html,
)


def test_cockpit_decision_report_overview_escapes_context_values_without_changing_them():
    markup = cockpit_decision_report_overview_card_html(
        {
            "symbol": "7203.T",
            "company_name": "Toyota <Motor>",
            "total_score": "72",
            "confidence": "中くらい",
            "overall_judgement": "比較候補",
            "investment_stance": "確認継続",
            "key_risks": "為替",
        }
    )

    assert "確認レポート - 7203.T / Toyota &lt;Motor&gt;" in markup
    assert "72 / 100" in markup
    assert "比較候補" in markup
    assert "確認継続" in markup


def test_cockpit_decision_summary_list_keeps_only_the_primary_three_lines():
    markup = cockpit_decision_summary_list_html(["第一", "第二", "第三", "第四"])

    assert "第一" in markup
    assert "第三" in markup
    assert "第四" not in markup
    assert markup.count("<li>") == 3


def test_cockpit_decision_report_detail_model_freezes_context_evidence_and_row_inputs():
    research = build_cockpit_research_context(
        symbol="7203.T",
        as_of=date(2026, 8, 2),
        report=None,
        news_report=None,
        external_research_result=None,
    )
    render_context = build_cockpit_decision_report_render_context(
        decision_report=build_decision_report_context(
            title="確認レポート - 7203.T",
            sections=[
                build_report_section(
                    title="確認材料",
                    source_kind="cockpit",
                    summary={"symbol": "7203.T"},
                )
            ],
        ),
        overview={"symbol": "7203.T"},
        summary_lines=["確認ポイント"],
        evidence_rows=[{"根拠": "価格トレンド", "読み取り": "横ばい"}],
        score_row={"総合スコア": "70"},
        symbol_row=None,
        research=research,
    )
    policy_rows = [{"項目": "総合判断", "内容": "比較候補"}]
    detail_model = build_cockpit_decision_report_detail_model(
        render_context,
        policy_rows=policy_rows,
        score_rows=[],
        price_forecast_rows=[],
        fundamental_rows=[],
        valuation_rows=[],
        risk_rows=[],
        evidence_card_rows=[],
        context_summary_rows=[],
    )
    policy_rows[0]["内容"] = "変更後"

    assert detail_model.summary_lines == ("確認ポイント",)
    assert detail_model.policy_rows == ({"項目": "総合判断", "内容": "比較候補"},)
    assert detail_model.evidence_rows == ({"根拠": "価格トレンド", "読み取り": "横ばい"},)
