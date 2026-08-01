from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal

from backend.research import (
    CompanyResearchReport,
    ResearchDataQuality,
    ResearchEvidence,
    ResearchSummaryPoint,
)
from ui.cockpit_research_presenter import build_cockpit_research_operation_card


def test_cockpit_research_operation_card_is_a_streamlit_independent_model():
    card = build_cockpit_research_operation_card(None, None)

    assert card.title == "AI調査はまだ未取得です"
    assert card.action_label == "AIメモを更新"
    assert card.material_groups == ()
    assert ("レポート", "未取得") in card.status_chips
    assert "st." not in inspect.getsource(build_cockpit_research_operation_card)


def test_cockpit_research_operation_card_preserves_report_source_states_and_materials():
    official_evidence = ResearchEvidence(
        symbol="7203.T",
        document_id="earnings",
        chunk_id="earnings-1",
        title="決算短信",
        source_type="earnings_report",
        published_at=date(2026, 7, 31),
        section_title="業績",
        excerpt="売上高は増加し、成長投資と安定配当を継続します。",
        relevance_score=Decimal("0.80"),
        reliability=Decimal("0.95"),
    )
    report = CompanyResearchReport(
        symbol="7203.T",
        as_of=date(2026, 8, 2),
        summary="根拠資料を整理しました。",
        points=[
            ResearchSummaryPoint(
                category="growth",
                label="成長材料",
                summary="売上高の増加と成長投資を確認します。",
                evidence=[official_evidence],
            )
        ],
        evidence=[official_evidence],
        data_quality=ResearchDataQuality(
            status="OK",
            latest_document_date=date(2026, 7, 31),
            document_count=1,
            evidence_count=1,
            warnings=[],
        ),
    )

    card = build_cockpit_research_operation_card(report, None)

    assert card.title == "AI調査結果"
    assert card.action_label == "AI調査を更新"
    assert ("レポート", "作成済み") in card.status_chips
    assert ("IR/開示", "1件") in card.status_chips
    assert [group.label for group in card.material_groups] == ["注目材料"]
    assert "成長材料" in card.material_groups[0].items[0]
    assert "決算短信" in card.material_groups[0].items[0]
