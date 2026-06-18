from urllib.error import HTTPError

from backend.core.errors import ProviderUnavailableError
from backend.research import (
    ResearchSourceTrace as PublicResearchSourceTrace,
)
from backend.research import (
    research_profile_source_key_for_provider as public_research_profile_source_key_for_provider,
)
from backend.research.source_trace import (
    ResearchSourceTrace,
    research_profile_source_key_for_provider,
    research_source_trace_from_result,
)


def test_research_source_trace_public_exports_stay_compatible():
    assert PublicResearchSourceTrace is ResearchSourceTrace
    assert public_research_profile_source_key_for_provider("google_news_rss") == "news"


def test_research_source_trace_provider_mapping():
    assert research_profile_source_key_for_provider("edinet") == "edinet"
    assert research_profile_source_key_for_provider("tdnet") == "tdnet"
    assert research_profile_source_key_for_provider("company_ir_site") == "ir_pages"
    assert research_profile_source_key_for_provider("google_news_rss") == "news"
    assert research_profile_source_key_for_provider("yahoo_finance") == "yahoo_finance"
    assert research_profile_source_key_for_provider("custom_provider") == "custom_provider"
    assert research_profile_source_key_for_provider("   ") == "unknown"


def test_research_source_trace_from_result_classifies_statuses():
    success = research_source_trace_from_result(
        provider="company_ir_site",
        result_count=2,
        elapsed_ms=25,
        retry_attempts=1,
    )
    no_result = research_source_trace_from_result(
        provider="google_news_rss",
        result_count=0,
        elapsed_ms=5,
    )
    timeout = research_source_trace_from_result(
        provider="tdnet",
        result_count=0,
        elapsed_ms=100,
        error=ProviderUnavailableError("provider timed out", details={"timeout": True}),
    )
    not_found = research_source_trace_from_result(
        provider="edinet",
        result_count=0,
        elapsed_ms=10,
        error=HTTPError("https://example.invalid", 404, "Not Found", hdrs=None, fp=None),
    )
    failed = research_source_trace_from_result(
        provider="yahoo_finance",
        result_count=0,
        elapsed_ms=30,
        error=ProviderUnavailableError("provider unavailable", details={"status_code": 503}),
    )

    assert success.status == "success"
    assert success.source == "ir_pages"
    assert success.retry_attempts == 1
    assert no_result.status == "no_result"
    assert timeout.status == "timeout"
    assert timeout.error_type == "ProviderUnavailableError"
    assert not_found.status == "no_result"
    assert failed.status == "failed"
    assert failed.error_message_short == "provider unavailable"
    assert isinstance(success.to_summary_row()["timestamp"], str)
