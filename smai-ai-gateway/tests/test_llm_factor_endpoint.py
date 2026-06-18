from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module
from app.config import GatewaySettings
from app.main import app
from app.schemas.common import LlmMessage, LlmProviderResult


class FakeOllamaClient:
    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings

    def chat(
        self,
        messages: list[LlmMessage],
        *,
        model: str | None = None,
        timeout_seconds: float | None = None,
        max_tokens: int | None = None,
    ) -> LlmProviderResult:
        answer = (
            '{"schema_version":"llm_factor.v1","symbol":"7203.T",'
            '"overall_summary":"株主還元が材料です。","sentiment_label":"positive",'
            '"confidence":0.7,'
            '"factors":[{"title":"株主還元","direction":"positive",'
            '"summary":"増配と自社株買い。","strength":0.8,'
            '"evidence_ids":["evidence_001"]}],'
            '"risks":[],"opportunities":[],"evidence":[],'
            '"missing_fields":[],"warnings":[],'
            '"prompt_version":"llm_factor_live_mvp.v1"}'
        )
        return LlmProviderResult(
            answer=answer,
            model=model or "qwen3:14b",
            provider="fake",
            elapsed_ms=8,
            prompt_chars=sum(len(message.content) for message in messages),
            response_chars=len(answer),
        )


def test_llm_factor_generate_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "OllamaClient", FakeOllamaClient)
    client = TestClient(app)

    response = client.post(
        "/api/v1/llm-factor/generate",
        json={
            "symbol": "7203.T",
            "company_name": "Toyota Motor",
            "as_of": "2026-06-12",
            "context": {
                "symbol_profile": {"company_name": "Toyota Motor"},
                "research_summary": ["増配と自社株買い。"],
                "evidence": [
                    {
                        "evidence_id": "evidence_001",
                        "title": "増配と自社株買いを発表",
                        "source_type": "company_ir",
                        "source_url": "https://example.com/ir/7203",
                        "source_date": "2026-06-12",
                        "summary": "増配と自社株買い。",
                    }
                ],
            },
            "preferred_profile": "desktop_analysis",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "llm_factor.v1"
    assert payload["symbol"] == "7203.T"
    assert payload["gateway_status"] == "ok"
    assert payload["provider"] == "fake"
