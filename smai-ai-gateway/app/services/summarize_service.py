from __future__ import annotations

from app.clients.ollama_client import OllamaClient
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
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
        result = self.client.chat(messages, model=request.model)
        return SummarizeResponse(**result.model_dump())
