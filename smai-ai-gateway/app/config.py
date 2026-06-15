from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

GATEWAY_ROOT = Path(__file__).resolve().parents[1]


class GatewaySettings(BaseModel):
    """Runtime settings for the standalone AI Gateway."""

    APP_NAME: str = Field(default="smai-ai-gateway", min_length=1)
    APP_ENV: str = Field(default="local", min_length=1)
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", min_length=1)
    DEFAULT_LLM_MODEL: str = Field(default="llama3.2:3b", min_length=1)
    DEFAULT_LLM_PROFILE: str = Field(default="notebook_dev", min_length=1)
    REQUEST_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    ENABLE_DEBUG_LOG: bool = False


@lru_cache(maxsize=1)
def get_settings() -> GatewaySettings:
    """Load settings from .env and environment variables."""

    _load_dotenv(GATEWAY_ROOT / ".env")
    base_url: str = (
        os.getenv("SMAI_OLLAMA_BASE_URL")
        or os.getenv("OLLAMA_BASE_URL")
        or "http://localhost:11434"
    )
    default_model = (
        os.getenv("SMAI_OLLAMA_MODEL")
        or os.getenv("DEFAULT_LLM_MODEL")
        or "llama3.2:3b"
    )
    return GatewaySettings(
        APP_NAME=os.getenv("APP_NAME", "smai-ai-gateway"),
        APP_ENV=os.getenv("APP_ENV", "local"),
        OLLAMA_BASE_URL=base_url,
        DEFAULT_LLM_MODEL=default_model,
        DEFAULT_LLM_PROFILE=os.getenv("SMAI_LLM_PROFILE", "notebook_dev"),
        REQUEST_TIMEOUT_SECONDS=_env_float("REQUEST_TIMEOUT_SECONDS", 30.0),
        ENABLE_DEBUG_LOG=_env_bool("ENABLE_DEBUG_LOG", False),
    )


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
