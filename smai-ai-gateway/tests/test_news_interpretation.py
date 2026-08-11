from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult
from app.schemas.context_answer import ContextAnswerRequest, ContextNewsInterpretation
from app.services.context_answer_service import ContextAnswerService


class FakeNewsClient:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.settings = GatewaySettings()
        self.messages: list[LlmMessage] = []
        self.timeout_seconds: float | None = None

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
        return LlmProviderResult(
            answer=self.answer, model=model or "qwen3:8b", provider="fake", elapsed_ms=5
        )


def test_gateway_returns_grounded_news_interpretation() -> None:
    client = FakeNewsClient(_payload())
    response = ContextAnswerService(client).answer(_request())  # type: ignore[arg-type]

    assert response.gateway_status == "ok"
    assert response.news_interpretation is not None
    assert response.news_interpretation.context_hash == "news-hash-1"
    assert [item.section_id for item in response.referenced_sections] == [
        "news_scope",
        "news-material-1",
        "news_sector_relations",
        "news_source_quality",
        "news_cockpit_handoffs",
    ]
    assert client.timeout_seconds == 45.0
    prompt = "\n".join(item.content for item in client.messages)
    assert "news_interpretation.v1" in prompt
    assert "never stock-price direction" in prompt


@pytest.mark.parametrize(
    "mutation",
    ["wrong_context", "wrong_material", "wrong_sector", "wrong_handoff", "unknown_evidence"],
)
def test_gateway_rejects_news_contract_mismatch(mutation: str) -> None:
    response = ContextAnswerService(FakeNewsClient(_payload(mutation=mutation))).answer(_request())  # type: ignore[arg-type]
    assert response.gateway_status == "fallback"
    assert response.news_interpretation is None


def test_news_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ContextNewsInterpretation.model_validate(
            {
                "news_context_id": "news:1",
                "context_hash": "news-hash-1",
                "summary": {"text": "確認します。", "cited_evidence_ids": ["news_scope"]},
                "unexpected": True,
            }
        )


def _payload(*, mutation: str | None = None) -> str:
    payload = {
        "schema_version": "news_interpretation.v1",
        "news_context_id": "news:context-1",
        "context_hash": "wrong" if mutation == "wrong_context" else "news-hash-1",
        "summary": {
            "text": "表示中のニュースを整理します。",
            "cited_evidence_ids": ["unknown" if mutation == "unknown_evidence" else "news_scope"],
        },
        "material_notes": [
            {
                "material_id": "unknown" if mutation == "wrong_material" else "news-material-1",
                "business_impact_direction": "unclear",
                "impact_horizon": "unclear",
                "related_sector_ids": [
                    "unknown" if mutation == "wrong_sector" else "news-sector-1"
                ],
                "reading": {
                    "text": "影響方向は未確認です。",
                    "cited_evidence_ids": ["news-material-1"],
                },
                "uncertainty": None,
            }
        ],
        "sector_notes": [
            {
                "sector_id": "news-sector-1",
                "reading": {
                    "text": "確認候補です。",
                    "cited_evidence_ids": ["news_sector_relations"],
                },
            }
        ],
        "noise_notes": [
            {"text": "鮮度を確認します。", "cited_evidence_ids": ["news_source_quality"]}
        ],
        "handoff_hints": [
            {
                "candidate_id": "unknown" if mutation == "wrong_handoff" else "candidate-1",
                "reason": {
                    "text": "コックピットで確認します。",
                    "cited_evidence_ids": ["news_cockpit_handoffs"],
                },
            }
        ],
        "unknowns": [],
        "next_checkpoints": [],
    }
    return json.dumps(payload, ensure_ascii=False)


def _request() -> ContextAnswerRequest:
    return ContextAnswerRequest.model_validate(
        {
            "task": "explain",
            "language": "ja",
            "user_question": "intent: news_interpretation",
            "active_context_id": "news_interpretation",
            "response_schema": "news_interpretation.v1",
            "task_type": "news_interpretation",
            "execution_mode": "auto",
            "environment_profile": "desktop",
            "referenced_context_ids": [
                "news_scope",
                "news_source_quality",
                "news-material-1",
                "news_sector_relations",
                "news_cockpit_handoffs",
            ],
            "context": {
                "bundle_id": "news-context-1",
                "title": "News Interpretation",
                "source": "manual",
                "sections": [
                    {
                        "section_id": "news_scope",
                        "title": "範囲",
                        "source_kind": "news_interpretation_scope",
                        "summary": {
                            "news_context_id": "news:context-1",
                            "context_hash": "news-hash-1",
                        },
                    },
                    {
                        "section_id": "news_source_quality",
                        "title": "品質",
                        "source_kind": "news_source_quality",
                    },
                    {
                        "section_id": "news-material-1",
                        "title": "材料",
                        "source_kind": "news_material_group",
                        "summary": {"related_sector_ids": "news-sector-1"},
                    },
                    {
                        "section_id": "news_sector_relations",
                        "title": "セクター",
                        "source_kind": "news_sector_relations",
                        "rows": [{"sector_id": "news-sector-1"}],
                    },
                    {
                        "section_id": "news_cockpit_handoffs",
                        "title": "候補",
                        "source_kind": "news_cockpit_handoffs",
                        "rows": [{"candidate_id": "candidate-1"}],
                    },
                ],
            },
        }
    )
