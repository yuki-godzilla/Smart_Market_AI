from urllib.error import HTTPError

import pytest

from backend.research import ResearchDocumentError as PublicResearchDocumentError
from backend.research.errors import ResearchDocumentError
from backend.research.external_fetch import (
    is_retryable_research_fetch_error,
    research_fetch_with_retry,
)
from backend.research.service import ResearchDocumentError as ServiceResearchDocumentError


def test_research_document_error_public_exports_stay_compatible():
    assert PublicResearchDocumentError is ResearchDocumentError
    assert ServiceResearchDocumentError is ResearchDocumentError


def test_research_fetch_with_retry_retries_timeout_then_succeeds():
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("provider timed out")
        return "ok"

    result, retry_attempts = research_fetch_with_retry(
        operation,
        provider="google_news_rss",
        error_message="Google News RSS fetch failed.",
        retry_count=1,
        retry_backoff_sec=0,
        url="https://example.invalid/rss",
    )

    assert result == "ok"
    assert retry_attempts == 1
    assert calls == 2


def test_research_fetch_with_retry_wraps_non_retryable_http_status():
    def operation() -> str:
        raise HTTPError("https://example.invalid/missing", 404, "Not Found", hdrs=None, fp=None)

    with pytest.raises(ResearchDocumentError) as exc_info:
        research_fetch_with_retry(
            operation,
            provider="edinet",
            error_message="EDINET document list fetch failed.",
            retry_count=2,
            retry_backoff_sec=0,
            url="https://example.invalid/missing",
        )

    assert exc_info.value.message == "EDINET document list fetch failed."
    assert exc_info.value.details["provider"] == "edinet"
    assert exc_info.value.details["retry_attempts"] == 0
    assert exc_info.value.details["status_code"] == 404
    assert exc_info.value.details["timeout"] is False
    assert exc_info.value.details["url"] == "https://example.invalid/missing"


def test_is_retryable_research_fetch_error_classifies_http_status():
    retryable = HTTPError("https://example.invalid", 503, "Unavailable", hdrs=None, fp=None)
    not_found = HTTPError("https://example.invalid", 404, "Not Found", hdrs=None, fp=None)

    assert is_retryable_research_fetch_error(retryable) is True
    assert is_retryable_research_fetch_error(not_found) is False
