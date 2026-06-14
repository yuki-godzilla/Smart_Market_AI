from __future__ import annotations

from pydantic import Field

from app.schemas.common import AiTextResponse, GatewayBaseModel
from app.services.model_router import LlmProfileName


class ChatRequest(GatewayBaseModel):
    message: str = Field(min_length=1)
    system_prompt: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    profile: LlmProfileName | None = None


class ChatResponse(AiTextResponse):
    """Generic chat response."""
