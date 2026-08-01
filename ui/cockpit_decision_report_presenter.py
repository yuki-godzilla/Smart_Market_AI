"""Streamlit-independent HTML presenters for the Cockpit Decision Report."""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import Mapping


def cockpit_decision_report_overview_card_html(overview: Mapping[str, str]) -> str:
    """Render the stable overview card from an already prepared decision-report context."""

    fields = [
        ("総合判断", overview.get("overall_judgement", "未判定")),
        ("スコア", f"{overview.get('total_score', '未計算')} / 100"),
        ("信頼度", overview.get("confidence", "低め")),
        ("確認スタンス", overview.get("investment_stance", "様子見 / 追加根拠確認")),
        ("注意材料", overview.get("key_risks", "価格トレンド・外部環境")),
    ]
    field_html = "".join(
        '<div class="decision-report-field">'
        f'<div class="decision-report-field-label">{html.escape(label)}</div>'
        f'<div class="decision-report-field-value">{html.escape(value)}</div>'
        "</div>"
        for label, value in fields
    )
    title = f"確認レポート - {overview.get('symbol', '選択銘柄')}"
    company_name = overview.get("company_name", "")
    if company_name and company_name != "未取得":
        title = f"{title} / {company_name}"
    return (
        '<section class="decision-report-card">'
        f'<div class="decision-report-title">{html.escape(title)}</div>'
        f'<div class="decision-report-grid">{field_html}</div>'
        "</section>"
    )


def cockpit_decision_summary_list_html(lines: Sequence[str]) -> str:
    """Render the first three context-frozen summary lines without reading UI state."""

    items = "".join(f"<li>{html.escape(line)}</li>" for line in lines[:3])
    return f'<ol class="decision-summary-list">{items}</ol>'
