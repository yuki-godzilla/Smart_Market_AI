from __future__ import annotations

from pydantic import Field

from app.schemas.common import AiTextResponse, GatewayBaseModel


class SummarizeRequest(GatewayBaseModel):
    text: str = Field(min_length=1)
    purpose: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)


class SummarizeResponse(AiTextResponse):
    """Generic summarize response."""
