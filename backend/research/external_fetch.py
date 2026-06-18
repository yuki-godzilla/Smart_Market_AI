from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar
from urllib.error import HTTPError, URLError

from backend.research.errors import ResearchDocumentError

DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS = 10.0

_T = TypeVar("_T")


def research_fetch_with_retry(
    operation: Callable[[], _T],
    *,
    provider: str,
    error_message: str,
    retry_count: int,
    retry_backoff_sec: float,
    url: str | None = None,
) -> tuple[_T, int]:
    retry_attempts = 0
    while True:
        try:
            return operation(), retry_attempts
        except Exception as exc:
            if retry_attempts >= retry_count or not is_retryable_research_fetch_error(exc):
                details: dict[str, object] = {
                    "provider": provider,
                    "retry_attempts": retry_attempts,
                    "error_type": type(exc).__name__,
                    "timeout": is_timeout_research_fetch_error(exc),
                }
                status_code = research_fetch_http_status(exc)
                if status_code is not None:
                    details["status_code"] = status_code
                if url:
                    details["url"] = url
                raise ResearchDocumentError(error_message, details=details) from exc
            retry_attempts += 1
            if retry_backoff_sec > 0:
                time.sleep(retry_backoff_sec * retry_attempts)


def is_retryable_research_fetch_error(exc: Exception) -> bool:
    status_code = research_fetch_http_status(exc)
    if status_code is not None:
        return 500 <= status_code <= 599
    if is_timeout_research_fetch_error(exc):
        return True
    if isinstance(exc, (ConnectionError, URLError)):
        return True
    message = str(exc).lower()
    name = type(exc).__name__.lower()
    return any(
        marker in message or marker in name
        for marker in (
            "connection reset",
            "connection aborted",
            "temporarily unavailable",
            "remote disconnected",
            "server disconnected",
            "network is unreachable",
        )
    )


def is_timeout_research_fetch_error(exc: Exception) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    message = str(exc).lower()
    name = type(exc).__name__.lower()
    return any(
        marker in message or marker in name
        for marker in (
            "timeout",
            "timed out",
            "readtimeout",
            "connecttimeout",
            "pooltimeout",
        )
    )


def research_fetch_http_status(exc: Exception) -> int | None:
    if isinstance(exc, HTTPError):
        return int(exc.code)
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    code = getattr(exc, "code", None)
    return int(code) if isinstance(code, int) else None
