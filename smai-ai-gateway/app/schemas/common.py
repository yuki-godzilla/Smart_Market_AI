from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GatewayBaseModel(BaseModel):
    """Strict base schema for API contracts."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(GatewayBaseModel):
    status: Literal["ok"]
    service: str = Field(min_length=1)


class LlmMessage(GatewayBaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class LlmProviderResult(GatewayBaseModel):
    answer: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    elapsed_ms: int = Field(ge=0)


class AiTextResponse(LlmProviderResult):
    """Common text response returned by chat and summarize endpoints."""
