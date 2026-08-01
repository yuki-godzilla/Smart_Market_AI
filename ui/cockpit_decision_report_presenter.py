"""Streamlit-independent HTML presenters for the Cockpit Decision Report."""

from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Mapping

from ui.cockpit_application import CockpitDecisionReportRenderContext


@dataclass(frozen=True)
class CockpitDecisionReportDetailModel:
    """Context-frozen rows consumed by the Decision Report detail page."""

    summary_lines: tuple[str, ...]
    policy_rows: tuple[dict[str, str], ...]
    score_rows: tuple[dict[str, str], ...]
    price_forecast_rows: tuple[dict[str, str], ...]
    fundamental_rows: tuple[dict[str, str], ...]
    valuation_rows: tuple[dict[str, str], ...]
    risk_rows: tuple[dict[str, str], ...]
    evidence_rows: tuple[dict[str, str], ...]
    evidence_card_rows: tuple[dict[str, str], ...]
    context_summary_rows: tuple[dict[str, str], ...]


def build_cockpit_decision_report_detail_model(
    render_context: CockpitDecisionReportRenderContext,
    *,
    policy_rows: Sequence[Mapping[str, str]],
    score_rows: Sequence[Mapping[str, str]],
    price_forecast_rows: Sequence[Mapping[str, str]],
    fundamental_rows: Sequence[Mapping[str, str]],
    valuation_rows: Sequence[Mapping[str, str]],
    risk_rows: Sequence[Mapping[str, str]],
    evidence_card_rows: Sequence[Mapping[str, str]],
    context_summary_rows: Sequence[Mapping[str, str]],
) -> CockpitDecisionReportDetailModel:
    """Freeze detail-section rows without reading Streamlit state or recalculating report evidence."""

    return CockpitDecisionReportDetailModel(
        summary_lines=tuple(render_context.summary_lines),
        policy_rows=tuple(dict(row) for row in policy_rows),
        score_rows=tuple(dict(row) for row in score_rows),
        price_forecast_rows=tuple(dict(row) for row in price_forecast_rows),
        fundamental_rows=tuple(dict(row) for row in fundamental_rows),
        valuation_rows=tuple(dict(row) for row in valuation_rows),
        risk_rows=tuple(dict(row) for row in risk_rows),
        evidence_rows=tuple(dict(row) for row in render_context.evidence_rows),
        evidence_card_rows=tuple(dict(row) for row in evidence_card_rows),
        context_summary_rows=tuple(dict(row) for row in context_summary_rows),
    )


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
