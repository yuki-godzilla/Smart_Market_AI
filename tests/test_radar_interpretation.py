from __future__ import annotations

from datetime import UTC, date, datetime

from backend.assistant import (
    AssistantGatewayReferencedSection,
    AssistantGatewayResponse,
    AssistantGatewayTimeoutError,
    MockAssistantGatewayClient,
)
from backend.core.config import RadarInterpretationConfig
from backend.news import (
    RadarCandidate,
    RadarCandidateEvidence,
    RadarEvidenceBundle,
    RadarEvidenceCitation,
    RadarInterpretationGatewayAdapter,
    RadarInterpretationService,
    RadarResearchContext,
    build_radar_interpretation_context,
)


def _candidate() -> RadarCandidate:
    evidence = RadarCandidateEvidence(
        evidence_id="radar-news-001",
        headline_title="Toyota raises production outlook",
        source_name="Example News",
        source_type="news",
        category="自動車",
        material_type="earnings",
        provenance="direct_mention",
        directness=1.0,
        published_at=datetime(2026, 7, 12, 1, 0, tzinfo=UTC),
        freshness_status="latest",
    )
    return RadarCandidate(
        candidate_id="radar:direct_mention:7203.T",
        symbol="7203.T",
        display_name="Toyota Motor",
        provenance="direct_mention",
        categories=["自動車"],
        evidence_ids=[evidence.evidence_id],
        evidence=[evidence],
        directness=1.0,
        confirmation_priority=70,
    )


def _bundle() -> RadarEvidenceBundle:
    return RadarEvidenceBundle(
        candidate_id="radar:direct_mention:7203.T",
        context=RadarResearchContext(
            candidate_id="radar:direct_mention:7203.T",
            symbol="7203.T",
            query="7203.T 自動車",
            as_of=date(2026, 7, 13),
            news_evidence_ids=["radar-news-001"],
        ),
        citations=[
            RadarEvidenceCitation(
                citation_id="radar-rag:doc-001:chunk-001",
                research_evidence_id="chunk-001",
                title="決算説明資料",
                source_type="company_ir",
                published_at=date(2026, 7, 10),
                retrieved_at=datetime(2026, 7, 13, 9, 0, tzinfo=UTC),
                freshness_status="recent",
                directness=1.0,
                excerpt="会社計画と生産方針を記載した短い根拠です。",
            )
        ],
        status="available",
        confirmation_gaps=["需要の持続性は追加確認が必要です。"],
        generated_at=datetime(2026, 7, 13, 9, 0, tzinfo=UTC),
    )


def test_radar_interpretation_context_keeps_only_safe_evidence_sections():
    context = build_radar_interpretation_context(
        _candidate(),
        _bundle(),
        now=datetime(2026, 7, 13, 9, 5, tzinfo=UTC),
    )

    assert context.allowed_evidence_ids == [
        "radar-news-001",
        "radar-rag:doc-001:chunk-001",
    ]
    assert {section.section_id for section in context.bundle.sections} == {
        "radar_candidate",
        "radar-news-001",
        "radar-rag:doc-001:chunk-001",
    }
    serialized = context.bundle.model_dump_json()
    assert "confirmation_priority" not in serialized
    assert "Investment Score" not in serialized
    assert "Forecast" not in serialized


def test_radar_interpretation_accepts_only_known_evidence_ids():
    context = build_radar_interpretation_context(_candidate(), _bundle())
    client = MockAssistantGatewayClient(
        response=AssistantGatewayResponse(
            answer="公式資料とニュースの時点差を確認する材料です。",
            materials=["生産方針に関する公式資料があります。"],
            cautions=["需要の持続性は未確認です。"],
            next_checkpoints=["次回開示で計画の前提を確認してください。"],
            referenced_sections=[
                AssistantGatewayReferencedSection(
                    section_id="radar-rag:doc-001:chunk-001",
                    title="決算説明資料",
                    source_kind="radar_rag_evidence",
                )
            ],
            confidence="medium",
            provider="local",
            model="test-model",
            profile="desktop_fast",
        )
    )
    service = RadarInterpretationService(
        RadarInterpretationGatewayAdapter(client),
        config=RadarInterpretationConfig(enabled=True),
    )

    result = service.interpret(context, now=datetime(2026, 7, 13, 10, 0, tzinfo=UTC))

    assert result.status == "live"
    assert result.referenced_evidence_ids == ["radar-rag:doc-001:chunk-001"]
    assert result.material_points[0].evidence_ids == ["radar-rag:doc-001:chunk-001"]
    assert client.requests[0].task_type == "news_materials"
    assert client.requests[0].referenced_context_ids == context.allowed_evidence_ids


def test_radar_interpretation_rejects_recommendations():
    context = build_radar_interpretation_context(_candidate(), _bundle())
    client = MockAssistantGatewayClient(
        response=AssistantGatewayResponse(
            answer="この銘柄は買うべきです。",
            referenced_sections=[
                AssistantGatewayReferencedSection(
                    section_id="unrelated-evidence",
                    title="unrelated",
                    source_kind="other",
                )
            ],
            provider="local",
            model="test-model",
            profile="desktop_fast",
        )
    )
    service = RadarInterpretationService(
        RadarInterpretationGatewayAdapter(client),
        config=RadarInterpretationConfig(enabled=True),
    )

    result = service.interpret(context, now=datetime(2026, 7, 13, 10, 0, tzinfo=UTC))

    assert result.status == "validation_error"
    assert result.fallback_reason == "policy_violation"
    assert result.is_fallback is True
    assert "この根拠だけでは判断できません" in result.overall_reading


def test_radar_interpretation_rejects_unknown_evidence_ids():
    context = build_radar_interpretation_context(_candidate(), _bundle())
    client = MockAssistantGatewayClient(
        response=AssistantGatewayResponse(
            answer="根拠の確認が必要です。",
            referenced_sections=[
                AssistantGatewayReferencedSection(
                    section_id="unrelated-evidence",
                    title="unrelated",
                    source_kind="other",
                )
            ],
            provider="local",
            model="test-model",
            profile="desktop_fast",
        )
    )
    service = RadarInterpretationService(
        RadarInterpretationGatewayAdapter(client),
        config=RadarInterpretationConfig(enabled=True),
    )

    result = service.interpret(context, now=datetime(2026, 7, 13, 10, 0, tzinfo=UTC))

    assert result.status == "fallback"
    assert result.fallback_reason == "unknown_evidence"
    assert result.is_fallback is True


def test_radar_interpretation_falls_back_for_timeout_and_malformed_gateway_response():
    context = build_radar_interpretation_context(_candidate(), _bundle())
    timeout_service = RadarInterpretationService(
        RadarInterpretationGatewayAdapter(
            MockAssistantGatewayClient(error=AssistantGatewayTimeoutError("timed out"))
        ),
        config=RadarInterpretationConfig(enabled=True),
    )
    malformed_service = RadarInterpretationService(
        RadarInterpretationGatewayAdapter(MockAssistantGatewayClient(response={"answer": ""})),
        config=RadarInterpretationConfig(enabled=True),
    )

    timeout_result = timeout_service.interpret(
        context,
        now=datetime(2026, 7, 13, 10, 0, tzinfo=UTC),
    )
    malformed_result = malformed_service.interpret(
        context,
        now=datetime(2026, 7, 13, 10, 0, tzinfo=UTC),
    )

    assert timeout_result.fallback_reason == "gateway_timeout"
    assert malformed_result.fallback_reason == "malformed_json"


def test_radar_interpretation_disabled_never_calls_gateway():
    context = build_radar_interpretation_context(_candidate(), _bundle())
    client = MockAssistantGatewayClient()
    service = RadarInterpretationService(
        RadarInterpretationGatewayAdapter(client),
        config=RadarInterpretationConfig(enabled=False),
    )

    result = service.interpret(context, now=datetime(2026, 7, 13, 10, 0, tzinfo=UTC))

    assert result.status == "disabled"
    assert result.fallback_reason == "disabled"
    assert client.requests == []
