from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.config import GatewaySettings
from app.schemas.common import LlmMessage, LlmProviderResult
from app.schemas.context_answer import (
    ContextAnswerRequest,
    ContextRadarOverviewInterpretation,
)
from app.services.context_answer_service import ContextAnswerService


class FakeRadarOverviewClient:
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


def test_gateway_returns_grounded_radar_overview_payload() -> None:
    client = FakeRadarOverviewClient(_payload_json())

    response = ContextAnswerService(client).answer(_request())  # type: ignore[arg-type]

    assert response.gateway_status == "ok"
    assert response.radar_overview_interpretation is not None
    assert response.radar_overview_interpretation.context_hash == "context-hash-1"
    assert [item.section_id for item in response.referenced_sections] == [
        "radar_scope",
        "radar_market_breadth",
        "radar_sector_comparison",
        "radar_theme:technology",
        "radar:direct_mention:AAA",
    ]
    assert client.timeout_seconds == 45.0
    assert client.max_tokens is not None
    prompt = "\n".join(item.content for item in client.messages)
    assert "radar_overview_interpretation.v1" in prompt
    assert "never the whole market" in prompt


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_context",
        "wrong_theme_candidate",
        "wrong_deep_candidate",
        "wrong_deep_order",
        "unknown_evidence",
        "wrong_evidence_relation",
    ],
)
def test_gateway_rejects_radar_overview_contract_mismatch(mutation: str) -> None:
    payload = {
        "wrong_context": _payload_json(context_hash="wrong"),
        "wrong_theme_candidate": _payload_json(
            theme_candidate_ids=["radar:direct_mention:UNKNOWN"]
        ),
        "wrong_deep_candidate": _payload_json(deep_candidate_id="radar:macro_proxy:SPY"),
        "wrong_deep_order": _payload_json(
            deep_candidate_ids=[
                "radar:inferred_candidate:BBB",
                "radar:direct_mention:AAA",
            ]
        ),
        "unknown_evidence": _payload_json(summary_evidence_id="unknown"),
        "wrong_evidence_relation": _payload_json(summary_evidence_id="radar_market_breadth"),
    }[mutation]
    response = ContextAnswerService(FakeRadarOverviewClient(payload)).answer(  # type: ignore[arg-type]
        _request()
    )

    assert response.gateway_status == "fallback"
    assert response.radar_overview_interpretation is None
    assert response.fallback_reason == "response_validation_failure"


def test_gateway_rejects_movement_when_market_snapshot_is_stale() -> None:
    response = ContextAnswerService(FakeRadarOverviewClient(_payload_json())).answer(  # type: ignore[arg-type]
        _request(market_state="stale")
    )

    assert response.gateway_status == "fallback"
    assert response.radar_overview_interpretation is None


def test_radar_overview_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ContextRadarOverviewInterpretation.model_validate(
            {
                "radar_context_id": "radar-overview:context-1",
                "context_hash": "context-hash-1",
                "summary": {"text": "確認します。", "cited_evidence_ids": ["radar_scope"]},
                "unexpected": "not allowed",
            }
        )


def _payload_json(
    *,
    context_hash: str = "context-hash-1",
    theme_candidate_ids: list[str] | None = None,
    deep_candidate_id: str = "radar:direct_mention:AAA",
    deep_candidate_ids: list[str] | None = None,
    summary_evidence_id: str = "radar_scope",
) -> str:
    payload = {
        "schema_version": "radar_overview_interpretation.v1",
        "radar_context_id": "radar-overview:context-1",
        "context_hash": context_hash,
        "summary": {
            "text": "本文言及とテーマ推測を分けて確認します。",
            "cited_evidence_ids": [summary_evidence_id],
        },
        "candidate_set_movement": {
            "text": "取得済み候補集合の値動きです。",
            "cited_evidence_ids": ["radar_market_breadth"],
        },
        "sector_notes": [
            {
                "sector_id": "radar_sector:technology",
                "reading": {
                    "text": "候補集合内の比較です。",
                    "cited_evidence_ids": ["radar_sector_comparison"],
                },
            }
        ],
        "theme_notes": [
            {
                "theme_id": "radar_theme:technology",
                "related_candidate_ids": theme_candidate_ids or ["radar:direct_mention:AAA"],
                "reading": {
                    "text": "ニュース量と鮮度を確認します。",
                    "cited_evidence_ids": ["radar_theme:technology"],
                },
            }
        ],
        "deep_dive_hints": [
            {
                "candidate_id": candidate_id,
                "reason": {
                    "text": "候補詳細で根拠を確認します。",
                    "cited_evidence_ids": [candidate_id],
                },
            }
            for candidate_id in (deep_candidate_ids or [deep_candidate_id])
        ],
        "unknowns": [],
        "next_checkpoints": [],
    }
    return json.dumps(payload, ensure_ascii=False)


def _request(*, market_state: str = "fresh") -> ContextAnswerRequest:
    return ContextAnswerRequest.model_validate(
        {
            "task": "explain",
            "language": "ja",
            "user_question": "intent: radar_overview_interpretation",
            "active_context_id": "radar_overview_interpretation",
            "response_schema": "radar_overview_interpretation.v1",
            "task_type": "radar_overview_interpretation",
            "execution_mode": "auto",
            "environment_profile": "desktop",
            "referenced_context_ids": [
                "radar_scope",
                "radar_market_breadth",
                "radar_sector_comparison",
                "radar_theme:technology",
                "radar:direct_mention:AAA",
                "radar:inferred_candidate:BBB",
            ],
            "context": {
                "bundle_id": "radar-overview-context-1",
                "title": "Investment Radar Overview",
                "source": "streamlit_context",
                "active_context_id": "radar_overview_interpretation",
                "sections": [
                    {
                        "section_id": "radar_scope",
                        "title": "範囲",
                        "source_kind": "radar_overview_scope",
                        "summary": {
                            "radar_context_id": "radar-overview:context-1",
                            "context_hash": "context-hash-1",
                        },
                    },
                    {
                        "section_id": "radar_market_breadth",
                        "title": "候補集合",
                        "source_kind": "radar_market_breadth",
                        "summary": {"market_state": market_state},
                    },
                    {
                        "section_id": "radar_sector_comparison",
                        "title": "セクター",
                        "source_kind": "radar_sector_comparison",
                        "rows": [{"sector_id": "radar_sector:technology"}],
                    },
                    {
                        "section_id": "radar_theme:technology",
                        "title": "半導体・AI",
                        "source_kind": "radar_news_theme",
                        "summary": {
                            "theme_id": "radar_theme:technology",
                            "related_candidate_ids": "radar:direct_mention:AAA",
                        },
                    },
                    {
                        "section_id": "radar:direct_mention:AAA",
                        "title": "AAA",
                        "source_kind": "radar_overview_candidate",
                        "summary": {"candidate_id": "radar:direct_mention:AAA"},
                    },
                    {
                        "section_id": "radar:inferred_candidate:BBB",
                        "title": "BBB",
                        "source_kind": "radar_overview_candidate",
                        "summary": {"candidate_id": "radar:inferred_candidate:BBB"},
                    },
                ],
            },
        }
    )
