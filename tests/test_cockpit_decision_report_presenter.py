from __future__ import annotations

from ui.cockpit_decision_report_presenter import (
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
