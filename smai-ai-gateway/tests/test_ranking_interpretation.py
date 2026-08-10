from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult
from app.schemas.context_answer import (
    ContextAnswerRequest,
    ContextRankingInterpretation,
)
from app.services.context_answer_service import ContextAnswerService


class FakeRankingClient:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.settings = GatewaySettings()
        self.messages: list[LlmMessage] = []
        self.timeout_seconds: float | None = None
        self.max_tokens: int | None = None

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmProviderResult:
        self.messages = messages
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        return LlmProviderResult(
            answer=self.answer,
            model=model or "qwen3:8b",
            provider="fake",
            elapsed_ms=8,
            prompt_chars=sum(len(item.content) for item in messages),
            response_chars=len(self.answer),
        )


def test_gateway_returns_evidence_bound_ranking_payload() -> None:
    client = FakeRankingClient(_payload_json())
    response = ContextAnswerService(client).answer(_request())  # type: ignore[arg-type]

    assert response.gateway_status == "ok"
    assert response.ranking_interpretation is not None
    assert response.ranking_interpretation.ranking_context_id == "ranking:context-1"
    assert [note.candidate_id for note in response.ranking_interpretation.candidate_notes] == [
        "ranking_candidate:7203.T",
        "ranking_candidate:6758.T",
    ]
    assert [item.section_id for item in response.referenced_sections] == [
        "ranking_scope",
        "ranking_metrics",
        "ranking_sectors",
        "ranking_candidate:7203.T",
        "ranking_candidate:6758.T",
    ]
    assert client.timeout_seconds == 45.0
    assert client.max_tokens is not None
    prompt = "\n".join(item.content for item in client.messages)
    assert "ranking_interpretation.v1" in prompt
    assert "Preserve the supplied candidate order" in prompt


def test_gateway_rejects_ranking_payload_with_wrong_order_or_evidence() -> None:
    answers = [
        _payload_json(candidate_ids=["ranking_candidate:6758.T", "ranking_candidate:7203.T"]),
        _payload_json(summary_evidence_id="unknown"),
    ]
    for answer in answers:
        response = ContextAnswerService(FakeRankingClient(answer)).answer(  # type: ignore[arg-type]
            _request()
        )

        assert response.gateway_status == "fallback"
        assert response.ranking_interpretation is None
        assert response.fallback_reason == "response_validation_failure"


def test_ranking_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ContextRankingInterpretation.model_validate(
            {
                "ranking_context_id": "ranking:context-1",
                "summary": {"text": "確認します。", "cited_evidence_ids": ["ranking_scope"]},
                "unexpected": "not allowed",
            }
        )


def _payload_json(
    *,
    candidate_ids: list[str] | None = None,
    summary_evidence_id: str = "ranking_scope",
) -> str:
    first, second = candidate_ids or [
        "ranking_candidate:7203.T",
        "ranking_candidate:6758.T",
    ]
    return (
        '{"schema_version":"ranking_interpretation.v1",'
        '"ranking_context_id":"ranking:context-1",'
        f'"summary":{{"text":"候補の比較観点を確認します。","cited_evidence_ids":["{summary_evidence_id}"]}},'
        '"common_strengths":[{"text":"主要指標を比較します。","cited_evidence_ids":["ranking_metrics"]}],'
        '"common_cautions":[],"metric_notes":[],'
        '"sector_notes":[{"text":"候補集合内の傾向です。","cited_evidence_ids":["ranking_sectors"]}],'
        f'"candidate_notes":[{{"candidate_id":"{first}",'
        f'"reading":{{"text":"候補を確認します。","cited_evidence_ids":["{first}"]}},'
        '"caution":null,'
        f'"next_check":{{"text":"根拠を確認します。","cited_evidence_ids":["{first}"]}}}},'
        f'{{"candidate_id":"{second}",'
        f'"reading":{{"text":"候補を確認します。","cited_evidence_ids":["{second}"]}},'
        '"caution":null,'
        f'"next_check":{{"text":"根拠を確認します。","cited_evidence_ids":["{second}"]}}}}],'
        '"next_checkpoints":[]}'
    )


def _request() -> ContextAnswerRequest:
    return ContextAnswerRequest.model_validate(
        {
            "task": "explain",
            "language": "ja",
            "user_question": "intent: ranking_interpretation",
            "active_context_id": "ranking_interpretation",
            "response_schema": "ranking_interpretation.v1",
            "task_type": "ranking_interpretation",
            "execution_mode": "auto",
            "environment_profile": "desktop",
            "referenced_context_ids": [
                "ranking_scope",
                "ranking_metrics",
                "ranking_sectors",
                "ranking_candidate:7203.T",
                "ranking_candidate:6758.T",
            ],
            "context": {
                "bundle_id": "ranking-context-1",
                "title": "Ranking Interpretation",
                "source": "streamlit_context",
                "active_context_id": "ranking_interpretation",
                "sections": [
                    {
                        "section_id": "ranking_scope",
                        "title": "ランキング条件",
                        "source_kind": "ranking_scope",
                        "summary": {"ranking_context_id": "ranking:context-1"},
                    },
                    {
                        "section_id": "ranking_metrics",
                        "title": "主要指標",
                        "source_kind": "ranking_metrics",
                        "summary": {"candidate_count": "2"},
                    },
                    {
                        "section_id": "ranking_sectors",
                        "title": "セクター",
                        "source_kind": "ranking_sector_comparison",
                        "summary": {"sector_group_count": "1"},
                    },
                    {
                        "section_id": "ranking_candidate:7203.T",
                        "title": "1位 7203.T",
                        "source_kind": "ranking_candidate",
                        "summary": {"candidate_id": "ranking_candidate:7203.T"},
                    },
                    {
                        "section_id": "ranking_candidate:6758.T",
                        "title": "2位 6758.T",
                        "source_kind": "ranking_candidate",
                        "summary": {"candidate_id": "ranking_candidate:6758.T"},
                    },
                ],
            },
        }
    )
