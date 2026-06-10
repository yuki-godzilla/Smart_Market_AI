from __future__ import annotations

from app.clients.ollama_client import OllamaClient
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.prompt_service import PromptService


class ChatService:
    """Generic chat service."""

    def __init__(
        self,
        client: OllamaClient,
        *,
        prompt_service: PromptService | None = None,
    ) -> None:
        self.client = client
        self.prompt_service = prompt_service or PromptService()

    def chat(self, request: ChatRequest) -> ChatResponse:
        messages = self.prompt_service.build_chat_messages(
            message=request.message,
            system_prompt=request.system_prompt,
        )
        result = self.client.chat(messages, model=request.model)
        return ChatResponse(**result.model_dump())
