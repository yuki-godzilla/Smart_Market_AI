from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GatewayBaseModel(BaseModel):
    """Strict base schema for API contracts."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(GatewayBaseModel):
    status: Literal["ok"]
    service: str = Field(min_length=1)


class ModelsResponse(GatewayBaseModel):
    provider: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    default_profile: str = Field(min_length=1)
    default_model: str = Field(min_length=1)
    installed_models: list[str] = Field(default_factory=list)
    configured_model_installed: bool
    install_hint: str | None = Field(default=None, min_length=1)


class ErrorDetail(GatewayBaseModel):
    error: str = Field(min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    code: str = Field(min_length=1)
    retryable: bool = False


class LlmMessage(GatewayBaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class LlmProviderResult(GatewayBaseModel):
    answer: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    elapsed_ms: int = Field(ge=0)
    prompt_chars: int | None = Field(default=None, ge=0)
    response_chars: int | None = Field(default=None, ge=0)


class AiTextResponse(LlmProviderResult):
    """Common text response returned by chat and summarize endpoints."""
