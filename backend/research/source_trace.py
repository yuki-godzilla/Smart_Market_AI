from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.research.external_fetch import (
    is_timeout_research_fetch_error,
    research_fetch_http_status,
)

RESEARCH_PROVIDER_TO_PROFILE_SOURCE = {
    "edinet": "edinet",
    "tdnet": "tdnet",
    "company_ir_site": "ir_pages",
    "google_news_rss": "news",
    "yahoo_finance": "yahoo_finance",
}

ResearchSourceTraceStatus = Literal[
    "success",
    "failed",
    "timeout",
    "no_result",
    "cache_hit",
    "skipped",
]


class ResearchSourceTrace(StrictBaseModel):
    """One source/adapter execution trace for external Research fetch diagnostics."""

    source: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    status: ResearchSourceTraceStatus
    elapsed_ms: int = Field(default=0, ge=0)
    retry_attempts: int = Field(default=0, ge=0)
    error_type: str = ""
    error_message_short: str = ""
    result_count: int = Field(default=0, ge=0)
    timestamp: datetime

    def to_summary_row(self) -> dict[str, object]:
        return self.model_dump(mode="json")


def research_profile_source_key_for_provider(provider: str) -> str:
    """Return the performance-profile source key for a research provider name."""

    normalized = provider.strip()
    return RESEARCH_PROVIDER_TO_PROFILE_SOURCE.get(normalized, normalized or "unknown")


def research_source_trace_from_result(
    *,
    provider: str,
    result_count: int,
    elapsed_ms: int,
    retry_attempts: int = 0,
    error: Exception | None = None,
) -> ResearchSourceTrace:
    status: ResearchSourceTraceStatus = "success" if result_count else "no_result"
    if error is not None and not result_count:
        status = research_trace_status_for_error(error)
    return ResearchSourceTrace(
        source=research_profile_source_key_for_provider(provider),
        provider=provider,
        status=status,
        elapsed_ms=elapsed_ms,
        retry_attempts=max(0, retry_attempts),
        error_type=type(error).__name__ if error is not None else "",
        error_message_short=short_research_error_message(error) if error is not None else "",
        result_count=max(0, result_count),
        timestamp=datetime.now(UTC),
    )


def research_trace_status_for_error(error: Exception) -> ResearchSourceTraceStatus:
    if research_error_is_timeout(error):
        return "timeout"
    if research_error_status_code(error) == 404:
        return "no_result"
    return "failed"


def research_error_is_timeout(error: Exception) -> bool:
    details = getattr(error, "details", None)
    if isinstance(details, dict):
        timeout = details.get("timeout")
        if isinstance(timeout, bool):
            return timeout
    return is_timeout_research_fetch_error(error)


def research_error_status_code(error: Exception) -> int | None:
    details = getattr(error, "details", None)
    if isinstance(details, dict):
        status_code = details.get("status_code")
        if isinstance(status_code, int):
            return status_code
    return research_fetch_http_status(error)


def short_research_error_message(error: Exception, *, max_chars: int = 180) -> str:
    message = getattr(error, "message", None)
    text = str(message or error).replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."
