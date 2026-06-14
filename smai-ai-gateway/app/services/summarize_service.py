from __future__ import annotations

from app.clients.ollama_client import OllamaClient
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.services.model_router import resolve_model_route
from app.services.prompt_service import PromptService


class SummarizeService:
    """Generic summarization service."""

    def __init__(
        self,
        client: OllamaClient,
        *,
        prompt_service: PromptService | None = None,
    ) -> None:
        self.client = client
        self.prompt_service = prompt_service or PromptService()

    def summarize(self, request: SummarizeRequest) -> SummarizeResponse:
        messages = self.prompt_service.build_summarize_messages(
            text=request.text,
            purpose=request.purpose,
        )
        route = resolve_model_route(
            settings=self.client.settings,
            task_type="rag_summary",
            preferred_profile=request.profile,
            requested_model=request.model,
        )
        result = self.client.chat(
            messages,
            model=route.model,
            timeout_seconds=route.timeout_seconds,
            max_tokens=route.max_tokens,
        )
        return SummarizeResponse(**result.model_dump())
