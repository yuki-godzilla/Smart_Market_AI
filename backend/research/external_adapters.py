from __future__ import annotations

import html
import json
import math
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from typing import Any, Callable, cast
from urllib.parse import urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from backend.core.config import ExternalFetchPerformanceConfig, resolve_performance_profile
from backend.core.errors import ProviderUnavailableError
from backend.research.errors import ResearchDocumentError
from backend.research.external_contracts import (
    ExternalResearchFetchRequest,
    ExternalResearchSourceAdapter,
    ExternalResearchSourcePayload,
    ResearchSourceType,
)
from backend.research.external_fetch import (
    DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS,
)
from backend.research.external_fetch import (
    research_fetch_with_retry as _research_fetch_with_retry,
)
from backend.research.source_trace import (
    ResearchSourceTrace,
    research_profile_source_key_for_provider,
    research_source_trace_from_result,
)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _excerpt(text: str, *, max_chars: int = 220) -> str:
    single_line = re.sub(r"\s+", " ", text).strip()
    if len(single_line) <= max_chars:
        return single_line
    return f"{single_line[: max_chars - 3].rstrip()}..."


def _unique_text(values: Sequence[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique


YAHOO_RESEARCH_PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("longName", "Company Name"),
    ("symbol", "Provider Symbol"),
    ("quoteType", "Quote Type"),
    ("exchange", "Exchange"),
    ("currency", "Currency"),
    ("sector", "Sector"),
    ("industry", "Industry"),
    ("country", "Country"),
    ("website", "Website"),
    ("marketCap", "Market Cap"),
    ("enterpriseValue", "Enterprise Value"),
    ("totalRevenue", "Total Revenue"),
    ("revenue", "Revenue"),
    ("operatingIncome", "Operating Income"),
    ("netIncomeToCommon", "Net Income To Common"),
    ("netIncome", "Net Income"),
    ("trailingEps", "Trailing EPS"),
    ("forwardEps", "Forward EPS"),
    ("trailingPE", "Trailing PE"),
    ("forwardPE", "Forward PE"),
    ("priceToBook", "Price To Book"),
    ("returnOnEquity", "Return On Equity"),
    ("dividendYield", "Dividend Yield"),
    ("yield", "Yield"),
    ("trailingAnnualDividendYield", "Trailing Annual Dividend Yield"),
    ("expenseRatio", "Expense Ratio"),
    ("annualReportExpenseRatio", "Annual Report Expense Ratio"),
    ("netAssets", "Net Assets"),
    ("totalAssets", "Total Assets"),
    ("navPrice", "NAV Price"),
    ("regularMarketPrice", "Regular Market Price"),
    ("fundFamily", "Fund Family"),
    ("category", "Category"),
    ("topHoldings", "Top Holdings"),
    ("holdings", "Holdings"),
    ("fullTimeEmployees", "Full Time Employees"),
    ("payoutRatio", "Payout Ratio"),
    ("beta", "Beta"),
)
COMPANY_IR_CANDIDATE_PATHS: tuple[str, ...] = (
    "ir",
    "jp/ir",
    "en/ir",
    "investor-relations",
    "investors",
    "investor",
    "ir/library",
    "ir/news",
)
TDNET_BASE_URL = "https://www.release.tdnet.info/inbs/"
TDNET_LIST_URL_TEMPLATE = TDNET_BASE_URL + "I_list_{page:03d}_{yyyymmdd}.html"
GOOGLE_NEWS_RSS_SEARCH_URL = "https://news.google.com/rss/search"
GOOGLE_NEWS_QUERY_TERM_LIMIT = 4
GOOGLE_NEWS_INVESTMENT_QUERY_TERMS: tuple[str, ...] = (
    "株価",
    "決算",
    "業績",
    "配当",
    "投資",
    "買収",
    "提携",
)
EDINET_API_KEY_ENV = "EDINET_API_KEY"
EDINET_DOCUMENTS_LIST_URL = "https://disclosure.edinet-fsa.go.jp/api/v2/documents.json"
EDINET_DOCUMENT_URL_TEMPLATE = "https://disclosure.edinet-fsa.go.jp/api/v2/documents/{doc_id}"


def _reset_research_adapter_trace_state(adapter: object) -> None:
    setattr(adapter, "_last_retry_attempts", 0)
    setattr(adapter, "_last_research_error", None)


def _add_research_adapter_retry_attempts(adapter: object, retry_attempts: int) -> None:
    current = getattr(adapter, "_last_retry_attempts", 0)
    if isinstance(current, int):
        setattr(adapter, "_last_retry_attempts", current + max(0, retry_attempts))
    else:
        setattr(adapter, "_last_retry_attempts", max(0, retry_attempts))


def _remember_research_adapter_error(adapter: object, exc: ResearchDocumentError) -> None:
    setattr(adapter, "_last_research_error", exc)


def _research_source_trace_from_adapter(
    *,
    adapter: ExternalResearchSourceAdapter,
    payloads: list[ExternalResearchSourcePayload],
    error: Exception | None,
    elapsed_ms: int,
) -> ResearchSourceTrace:
    recorded_error = error
    if recorded_error is None and not payloads:
        maybe_error = getattr(adapter, "_last_research_error", None)
        if isinstance(maybe_error, Exception):
            recorded_error = maybe_error
    retry_attempts = getattr(adapter, "_last_retry_attempts", 0)
    if not isinstance(retry_attempts, int):
        retry_attempts = 0
    return research_source_trace_from_result(
        provider=adapter.provider,
        result_count=len(payloads),
        error=recorded_error,
        elapsed_ms=elapsed_ms,
        retry_attempts=retry_attempts,
    )


class GoogleNewsRSSResearchAdapter:
    """Opt-in Google News RSS search adapter for general investment headlines."""

    provider = "google_news_rss"
    requires_network = True

    def __init__(
        self,
        *,
        http_get: Callable[[str], str] | None = None,
        hl: str = "ja",
        gl: str = "JP",
        ceid: str = "JP:ja",
        lookback_days: int = 14,
        max_results: int = 5,
        request_timeout_sec: float = DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS,
        retry_count: int = 0,
        retry_backoff_sec: float = 0.0,
    ) -> None:
        self._http_get = http_get
        self.hl = hl
        self.gl = gl
        self.ceid = ceid
        self.lookback_days = max(1, lookback_days)
        self.max_results = max(1, max_results)
        self.request_timeout_sec = max(0.1, float(request_timeout_sec))
        self.retry_count = max(0, int(retry_count))
        self.retry_backoff_sec = max(0.0, float(retry_backoff_sec))
        _reset_research_adapter_trace_state(self)

    def fetch_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> list[ExternalResearchSourcePayload]:
        _reset_research_adapter_trace_state(self)
        query = _google_news_query(request, lookback_days=self.lookback_days)
        if not query:
            return []
        fetched_at = datetime.now(UTC)
        feed_url = _google_news_rss_url(query, hl=self.hl, gl=self.gl, ceid=self.ceid)
        try:
            rss_text = self._get_text(feed_url)
        except ResearchDocumentError as exc:
            _remember_research_adapter_error(self, exc)
            return []
        return _google_news_payloads_from_rss(
            request,
            rss_text,
            fetched_at=fetched_at,
            max_results=self.max_results,
        )

    def _get_text(self, url: str) -> str:
        def operation() -> str:
            if self._http_get is not None:
                return self._http_get(url)
            url_request = UrlRequest(url, headers={"User-Agent": "SmartMarketAI/1.0"})
            with urlopen(url_request, timeout=self.request_timeout_sec) as response:  # noqa: S310
                return response.read().decode("utf-8", errors="replace")

        text, retry_attempts = _research_fetch_with_retry(
            operation,
            provider=self.provider,
            error_message="Google News RSS fetch failed.",
            retry_count=self.retry_count,
            retry_backoff_sec=self.retry_backoff_sec,
            url=url,
        )
        _add_research_adapter_retry_attempts(self, retry_attempts)
        return text


class YahooFinanceResearchAdapter:
    """Opt-in Yahoo Finance adapter for provider profile and recent news payloads."""

    provider = "yahoo_finance"
    requires_network = True

    def __init__(
        self,
        ticker_factory: Callable[[str], Any] | None = None,
        *,
        request_timeout_sec: float = DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS,
    ) -> None:
        self._ticker_factory = ticker_factory
        self.request_timeout_sec = max(0.1, float(request_timeout_sec))
        _reset_research_adapter_trace_state(self)

    def fetch_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> list[ExternalResearchSourcePayload]:
        _reset_research_adapter_trace_state(self)
        fetched_at = datetime.now(UTC)
        ticker = self._ticker(request.symbol)
        payloads: list[ExternalResearchSourcePayload] = []
        info = _ticker_info(ticker)
        if info:
            payloads.append(_yahoo_profile_payload(request, info, fetched_at=fetched_at))
        payloads.extend(_yahoo_news_payloads(request, _ticker_news(ticker), fetched_at=fetched_at))
        return payloads

    def _ticker(self, symbol: str) -> Any:
        if self._ticker_factory is not None:
            return self._ticker_factory(symbol)
        yf, session = _research_yfinance_runtime(self.provider)
        return yf.Ticker(symbol, session=session)


def _research_yfinance_runtime(provider: str) -> tuple[Any, Any]:
    try:
        from backend.marketdata.providers.yahoo import (
            _load_yfinance,
            shared_yfinance_session,
        )
    except ImportError as exc:  # pragma: no cover - package-internal import
        raise ResearchDocumentError(
            "yfinance runtime is required for external research.",
            details={"provider": provider},
        ) from exc
    try:
        return _load_yfinance(), shared_yfinance_session()
    except ProviderUnavailableError as exc:
        details: dict[str, object] = {"provider": provider}
        details.update(exc.details)
        raise ResearchDocumentError(
            "yfinance runtime is unavailable for external research.",
            details=details,
        ) from exc


class CompanyIRSiteResearchAdapter:
    """Opt-in company IR site adapter using official website metadata."""

    provider = "company_ir_site"
    requires_network = True

    def __init__(
        self,
        *,
        ticker_factory: Callable[[str], Any] | None = None,
        http_get: Callable[[str], str] | None = None,
        website_resolver: Callable[[ExternalResearchFetchRequest], str | None] | None = None,
        candidate_paths: Sequence[str] = COMPANY_IR_CANDIDATE_PATHS,
        max_results: int = 1,
        request_timeout_sec: float = DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS,
        retry_count: int = 0,
        retry_backoff_sec: float = 0.0,
    ) -> None:
        self._ticker_factory = ticker_factory
        self._http_get = http_get
        self._website_resolver = website_resolver
        self.candidate_paths = tuple(candidate_paths)
        self.max_results = max(1, max_results)
        self.request_timeout_sec = max(0.1, float(request_timeout_sec))
        self.retry_count = max(0, int(retry_count))
        self.retry_backoff_sec = max(0.0, float(retry_backoff_sec))
        _reset_research_adapter_trace_state(self)

    def fetch_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> list[ExternalResearchSourcePayload]:
        _reset_research_adapter_trace_state(self)
        fetched_at = datetime.now(UTC)
        website = self._official_website(request)
        if not website:
            return []
        payloads: list[ExternalResearchSourcePayload] = []
        seen_urls: set[str] = set()
        for source_url in _company_ir_candidate_urls(website, self.candidate_paths):
            if source_url in seen_urls:
                continue
            seen_urls.add(source_url)
            try:
                html_text = self._get_text(source_url)
            except ResearchDocumentError as exc:
                _remember_research_adapter_error(self, exc)
                continue
            if not _company_ir_page_is_relevant(html_text):
                continue
            payloads.append(
                _company_ir_site_payload(
                    request,
                    html_text,
                    source_url=source_url,
                    fetched_at=fetched_at,
                )
            )
            if len(payloads) >= self.max_results:
                return payloads
        return payloads

    def _official_website(self, request: ExternalResearchFetchRequest) -> str:
        if self._website_resolver is not None:
            return _normalize_external_url(self._website_resolver(request))
        try:
            info = _ticker_info(self._ticker(request.symbol))
        except ResearchDocumentError as exc:
            _remember_research_adapter_error(self, exc)
            return ""
        return _normalize_external_url(_external_text_value(info.get("website")))

    def _ticker(self, symbol: str) -> Any:
        if self._ticker_factory is not None:
            return self._ticker_factory(symbol)
        yf, session = _research_yfinance_runtime(self.provider)
        return yf.Ticker(symbol, session=session)

    def _get_text(self, url: str) -> str:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency is pinned for runtime
            raise ResearchDocumentError(
                "httpx is required for the company IR site research adapter.",
                details={"provider": self.provider},
            ) from exc

        def operation() -> str:
            if self._http_get is not None:
                return self._http_get(url)
            with httpx.Client(timeout=self.request_timeout_sec, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                response.encoding = response.encoding or "utf-8"
                return response.text

        text, retry_attempts = _research_fetch_with_retry(
            operation,
            provider=self.provider,
            error_message="Company IR site fetch failed.",
            retry_count=self.retry_count,
            retry_backoff_sec=self.retry_backoff_sec,
            url=url,
        )
        _add_research_adapter_retry_attempts(self, retry_attempts)
        return text


class TDnetResearchAdapter:
    """TDnet timely-disclosure adapter for current Japanese IR source links."""

    provider = "tdnet"
    requires_network = True

    def __init__(
        self,
        *,
        http_get: Callable[[str], str] | None = None,
        lookback_days: int = 7,
        max_pages_per_day: int = 3,
        max_results: int = 5,
        request_timeout_sec: float = DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS,
        retry_count: int = 0,
        retry_backoff_sec: float = 0.0,
    ) -> None:
        self._http_get = http_get
        self.lookback_days = max(1, lookback_days)
        self.max_pages_per_day = max(1, max_pages_per_day)
        self.max_results = max(1, max_results)
        self.request_timeout_sec = max(0.1, float(request_timeout_sec))
        self.retry_count = max(0, int(retry_count))
        self.retry_backoff_sec = max(0.0, float(retry_backoff_sec))
        _reset_research_adapter_trace_state(self)

    def fetch_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> list[ExternalResearchSourcePayload]:
        _reset_research_adapter_trace_state(self)
        symbol_code = _tdnet_symbol_code(request.symbol)
        if not symbol_code:
            return []
        fetched_at = datetime.now(UTC)
        as_of = request.as_of or fetched_at.date()
        payloads: list[ExternalResearchSourcePayload] = []
        seen_urls: set[str] = set()
        for offset in range(self.lookback_days):
            published_at = date.fromordinal(as_of.toordinal() - offset)
            yyyymmdd = published_at.strftime("%Y%m%d")
            for page in range(1, self.max_pages_per_day + 1):
                list_url = TDNET_LIST_URL_TEMPLATE.format(page=page, yyyymmdd=yyyymmdd)
                try:
                    html_text = self._get_text(list_url)
                except ResearchDocumentError as exc:
                    _remember_research_adapter_error(self, exc)
                    continue
                if not html_text.strip():
                    continue
                for payload in _tdnet_payloads_from_html(
                    request,
                    html_text,
                    list_url=list_url,
                    fetched_at=fetched_at,
                    published_at=published_at,
                ):
                    if payload.source_url in seen_urls:
                        continue
                    seen_urls.add(payload.source_url)
                    payloads.append(payload)
                    if len(payloads) >= self.max_results:
                        return payloads
        return payloads

    def _get_text(self, url: str) -> str:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency is pinned for runtime
            raise ResearchDocumentError(
                "httpx is required for the TDnet research adapter.",
                details={"provider": self.provider},
            ) from exc

        def operation() -> str:
            if self._http_get is not None:
                return self._http_get(url)
            with httpx.Client(timeout=self.request_timeout_sec, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                response.encoding = response.encoding or "utf-8"
                return response.text

        text, retry_attempts = _research_fetch_with_retry(
            operation,
            provider=self.provider,
            error_message="TDnet disclosure list fetch failed.",
            retry_count=self.retry_count,
            retry_backoff_sec=self.retry_backoff_sec,
            url=url,
        )
        _add_research_adapter_retry_attempts(self, retry_attempts)
        return text


class EDINETResearchAdapter:
    """EDINET adapter for official Japanese securities report metadata links."""

    provider = "edinet"
    requires_network = True

    def __init__(
        self,
        *,
        http_get_json: Callable[[str], Mapping[str, Any]] | None = None,
        api_key: str | None = None,
        lookback_days: int = 45,
        max_results: int = 5,
        request_timeout_sec: float = DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS,
        retry_count: int = 0,
        retry_backoff_sec: float = 0.0,
    ) -> None:
        self._http_get_json = http_get_json
        self.api_key = api_key if api_key is not None else os.getenv(EDINET_API_KEY_ENV, "")
        self.lookback_days = max(1, lookback_days)
        self.max_results = max(1, max_results)
        self.request_timeout_sec = max(0.1, float(request_timeout_sec))
        self.retry_count = max(0, int(retry_count))
        self.retry_backoff_sec = max(0.0, float(retry_backoff_sec))
        _reset_research_adapter_trace_state(self)

    def fetch_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> list[ExternalResearchSourcePayload]:
        _reset_research_adapter_trace_state(self)
        if not self.api_key and self._http_get_json is None:
            return []
        fetched_at = datetime.now(UTC)
        as_of = request.as_of or fetched_at.date()
        payloads: list[ExternalResearchSourcePayload] = []
        seen_urls: set[str] = set()
        for offset in range(self.lookback_days):
            submitted_at = date.fromordinal(as_of.toordinal() - offset)
            list_url = _edinet_documents_list_url(submitted_at, api_key=self.api_key)
            try:
                response = self._get_json(list_url)
            except ResearchDocumentError as exc:
                _remember_research_adapter_error(self, exc)
                continue
            for payload in _edinet_payloads_from_response(
                request,
                response,
                fetched_at=fetched_at,
            ):
                if payload.source_url in seen_urls:
                    continue
                seen_urls.add(payload.source_url)
                payloads.append(payload)
                if len(payloads) >= self.max_results:
                    return payloads
        return payloads

    def _get_json(self, url: str) -> Mapping[str, Any]:
        def operation() -> str | Mapping[str, Any]:
            if self._http_get_json is not None:
                return self._http_get_json(url)
            url_request = UrlRequest(url, headers={"User-Agent": "SmartMarketAI/1.0"})
            with urlopen(url_request, timeout=self.request_timeout_sec) as response:  # noqa: S310
                return response.read().decode("utf-8")

        response_or_body, retry_attempts = _research_fetch_with_retry(
            operation,
            provider=self.provider,
            error_message="EDINET document list fetch failed.",
            retry_count=self.retry_count,
            retry_backoff_sec=self.retry_backoff_sec,
            url=_edinet_safe_url(url),
        )
        _add_research_adapter_retry_attempts(self, retry_attempts)
        if isinstance(response_or_body, Mapping):
            return response_or_body
        body = response_or_body
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:  # pragma: no cover - provider response issue
            raise ResearchDocumentError(
                "EDINET document list response was not JSON.",
                details={"provider": self.provider, "url": _edinet_safe_url(url)},
            ) from exc
        return cast(Mapping[str, Any], parsed) if isinstance(parsed, Mapping) else {}


class CompositeExternalResearchAdapter:
    """Run multiple external source adapters as one UI-facing provider."""

    provider = "tdnet_yahoo_finance"
    requires_network = True

    def __init__(
        self,
        adapters: Sequence[ExternalResearchSourceAdapter],
        *,
        provider: str | None = None,
        external_fetch_config: ExternalFetchPerformanceConfig | None = None,
        performance_profile_name: str | None = None,
    ) -> None:
        self.adapters = list(adapters)
        self.external_fetch_config = external_fetch_config
        self.performance_profile_name = performance_profile_name
        self.last_source_traces: list[ResearchSourceTrace] = []
        self._source_limiters: dict[str, threading.BoundedSemaphore] = {}
        if provider is not None:
            self.provider = provider
        self.requires_network = any(adapter.requires_network for adapter in self.adapters)

    def fetch_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> list[ExternalResearchSourcePayload]:
        self.last_source_traces = []
        if not self.adapters:
            return []
        payloads_by_index: dict[int, list[ExternalResearchSourcePayload]] = {}
        traces_by_index: dict[int, ResearchSourceTrace] = {}
        futures: dict[Future[tuple[list[ExternalResearchSourcePayload], ResearchSourceTrace]], int]
        futures = {}
        started_at = time.perf_counter()
        executor = ThreadPoolExecutor(max_workers=self._max_workers())
        try:
            for index, adapter in enumerate(self.adapters):
                adapter_request = request.model_copy(update={"provider": adapter.provider})
                future = executor.submit(self._fetch_adapter_with_trace, adapter, adapter_request)
                futures[future] = index
            done, not_done = wait(futures, timeout=self._global_timeout_sec())
            for future in done:
                index = futures[future]
                try:
                    adapter_payloads, trace = future.result()
                except Exception as exc:  # pragma: no cover - defensive boundary
                    adapter = self.adapters[index]
                    adapter_payloads = []
                    trace = research_source_trace_from_result(
                        provider=adapter.provider,
                        result_count=0,
                        error=exc,
                        elapsed_ms=max(0, int(round((time.perf_counter() - started_at) * 1000))),
                    )
                payloads_by_index[index] = adapter_payloads
                traces_by_index[index] = trace
            elapsed_ms = max(0, int(round((time.perf_counter() - started_at) * 1000)))
            for future in not_done:
                index = futures[future]
                adapter = self.adapters[index]
                future.cancel()
                traces_by_index[index] = self._global_timeout_trace(
                    adapter.provider,
                    elapsed_ms=elapsed_ms,
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        payloads: list[ExternalResearchSourcePayload] = []
        for index in range(len(self.adapters)):
            payloads.extend(payloads_by_index.get(index, []))
        self.last_source_traces = [
            traces_by_index[index]
            for index in range(len(self.adapters))
            if index in traces_by_index
        ]
        return payloads

    def _global_timeout_sec(self) -> float:
        configured_timeout = (
            self.external_fetch_config.global_timeout_sec
            if self.external_fetch_config is not None
            else DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS * 3
        )
        return max(0.1, float(configured_timeout))

    def _global_timeout_trace(self, provider: str, *, elapsed_ms: int) -> ResearchSourceTrace:
        timeout_sec = self._global_timeout_sec()
        return ResearchSourceTrace(
            source=research_profile_source_key_for_provider(provider),
            provider=provider,
            status="timeout",
            elapsed_ms=elapsed_ms,
            retry_attempts=0,
            error_type="TimeoutError",
            error_message_short=(
                f"{provider} did not finish within the "
                f"{timeout_sec:.1f}s AI research fetch limit."
            ),
            result_count=0,
            timestamp=datetime.now(UTC),
        )

    def _max_workers(self) -> int:
        configured_workers = (
            self.external_fetch_config.max_workers
            if self.external_fetch_config is not None
            else len(self.adapters)
        )
        return max(1, min(int(configured_workers), len(self.adapters)))

    def _source_worker_limit(self, provider: str) -> int:
        source = research_profile_source_key_for_provider(provider)
        configured_workers = (
            self.external_fetch_config.per_source_workers.get(source)
            if self.external_fetch_config is not None
            else None
        )
        if configured_workers is None:
            return 1
        return max(1, int(configured_workers))

    def _source_limiter(self, provider: str) -> threading.BoundedSemaphore:
        source = research_profile_source_key_for_provider(provider)
        limiter = self._source_limiters.get(source)
        if limiter is None:
            limiter = threading.BoundedSemaphore(self._source_worker_limit(provider))
            self._source_limiters[source] = limiter
        return limiter

    def _fetch_adapter_with_trace(
        self,
        adapter: ExternalResearchSourceAdapter,
        request: ExternalResearchFetchRequest,
    ) -> tuple[list[ExternalResearchSourcePayload], ResearchSourceTrace]:
        _reset_research_adapter_trace_state(adapter)
        started_at = time.perf_counter()
        error: Exception | None = None
        payloads: list[ExternalResearchSourcePayload] = []
        with self._source_limiter(adapter.provider):
            try:
                payloads = adapter.fetch_sources(request)
            except Exception as exc:  # noqa: BLE001
                error = exc
        trace = _research_source_trace_from_adapter(
            adapter=adapter,
            payloads=payloads,
            error=error,
            elapsed_ms=max(0, int(round((time.perf_counter() - started_at) * 1000))),
        )
        return payloads, trace


class DefaultExternalResearchAdapter(CompositeExternalResearchAdapter):
    """Default live research source set for the Cockpit AI refresh flow."""

    def __init__(self) -> None:
        profile = resolve_performance_profile()
        external_fetch = profile.external_fetch
        request_timeout_sec = external_fetch.request_timeout_sec
        retry_count = external_fetch.retry_count
        retry_backoff_sec = external_fetch.retry_backoff_sec
        super().__init__(
            [
                EDINETResearchAdapter(
                    request_timeout_sec=request_timeout_sec,
                    retry_count=retry_count,
                    retry_backoff_sec=retry_backoff_sec,
                ),
                TDnetResearchAdapter(
                    request_timeout_sec=request_timeout_sec,
                    retry_count=retry_count,
                    retry_backoff_sec=retry_backoff_sec,
                ),
                CompanyIRSiteResearchAdapter(
                    request_timeout_sec=request_timeout_sec,
                    retry_count=retry_count,
                    retry_backoff_sec=retry_backoff_sec,
                ),
                GoogleNewsRSSResearchAdapter(
                    request_timeout_sec=request_timeout_sec,
                    retry_count=retry_count,
                    retry_backoff_sec=retry_backoff_sec,
                ),
                YahooFinanceResearchAdapter(request_timeout_sec=request_timeout_sec),
            ],
            provider="edinet_tdnet_company_ir_google_news_yahoo_finance",
            external_fetch_config=external_fetch,
            performance_profile_name=profile.selected_profile,
        )


def _google_news_query(
    request: ExternalResearchFetchRequest,
    *,
    lookback_days: int,
) -> str:
    base_terms = _google_news_query_base_terms(request)
    if not base_terms:
        return ""
    # Retain the company alias plus both exchange-form and numeric ticker forms.
    # Japanese and US articles often use different representations, and this is
    # still a single provider request rather than a wider fetch fan-out.
    base_query = " OR ".join(
        _google_news_quote_query_term(term) for term in base_terms[:GOOGLE_NEWS_QUERY_TERM_LIMIT]
    )
    if len(base_terms) > 1:
        base_query = f"({base_query})"
    investment_query = " OR ".join(GOOGLE_NEWS_INVESTMENT_QUERY_TERMS)
    return f"{base_query} ({investment_query}) when:{max(1, lookback_days)}d"


def _google_news_query_base_terms(request: ExternalResearchFetchRequest) -> list[str]:
    company_terms = [request.company_name] if request.company_name else []
    related_terms = _dedupe_non_empty_text(request.related_keywords)
    symbol = _normalize_symbol(request.symbol)
    symbol_terms = [symbol]
    if "." in symbol:
        symbol_terms.append(symbol.split(".", 1)[0])
    # The query is bounded to four terms.  Put the first user/company alias
    # before the exchange forms, then retain the rest only if the bound allows.
    # This prevents a long keyword list from crowding out the unambiguous ticker.
    return _dedupe_non_empty_text(
        [*company_terms, *related_terms[:1], *symbol_terms, *related_terms[1:]]
    )


def _dedupe_non_empty_text(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        key = stripped.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(stripped)
    return deduped


def _google_news_quote_query_term(term: str) -> str:
    stripped = term.strip()
    if not stripped:
        return ""
    if re.search(r"\s", stripped):
        return f'"{stripped}"'
    return stripped


def _google_news_rss_url(
    query: str,
    *,
    hl: str,
    gl: str,
    ceid: str,
) -> str:
    return (
        f"{GOOGLE_NEWS_RSS_SEARCH_URL}?"
        f"{urlencode({'q': query, 'hl': hl, 'gl': gl, 'ceid': ceid})}"
    )


def _google_news_payloads_from_rss(
    request: ExternalResearchFetchRequest,
    rss_text: str,
    *,
    fetched_at: datetime,
    max_results: int,
) -> list[ExternalResearchSourcePayload]:
    try:
        root = ET.fromstring(rss_text)
    except ET.ParseError:
        return []
    payloads: list[ExternalResearchSourcePayload] = []
    seen_urls: set[str] = set()
    for item in root.findall(".//item"):
        payload = _google_news_payload_from_item(
            request,
            item,
            fetched_at=fetched_at,
        )
        if payload is None:
            continue
        key = payload.source_url.casefold()
        if key in seen_urls:
            continue
        seen_urls.add(key)
        payloads.append(payload)
        if len(payloads) >= max_results:
            return payloads
    return payloads


def _google_news_payload_from_item(
    request: ExternalResearchFetchRequest,
    item: ET.Element,
    *,
    fetched_at: datetime,
) -> ExternalResearchSourcePayload | None:
    title = _google_news_rss_child_text(item, "title")
    link = _normalize_external_url(_google_news_rss_child_text(item, "link"))
    if not title or not link:
        return None
    source = _google_news_rss_child_text(item, "source") or "Google News"
    description = _google_news_description_text(_google_news_rss_child_text(item, "description"))
    published_at = _google_news_published_date(_google_news_rss_child_text(item, "pubDate"))
    summary = description or title
    content = "\n".join(
        [
            f"source: {source}",
            f"url: {link}",
            f"summary: {_excerpt(summary, max_chars=220)}",
            "",
            "Google News RSSで確認できた一般ニュースのヘッドラインです。",
            "売買推奨ではなく、公式IRや一次情報と合わせて確認してください。",
        ]
    )
    return ExternalResearchSourcePayload(
        symbol=_normalize_symbol(request.symbol),
        title=title,
        content=content,
        source_type="news",
        source_url=link,
        provider=GoogleNewsRSSResearchAdapter.provider,
        company_name=request.company_name,
        published_at=published_at,
        fetched_at=fetched_at,
        reliability=Decimal("0.60"),
    )


def _google_news_rss_child_text(item: ET.Element, tag_name: str) -> str:
    child = item.find(tag_name)
    if child is None or child.text is None:
        return ""
    return html.unescape(child.text).strip()


def _google_news_description_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return _excerpt(" ".join(html.unescape(without_tags).split()), max_chars=240)


def _google_news_published_date(value: str) -> date | None:
    if not value.strip():
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return parsed.date()


def _ticker_info(ticker: Any) -> dict[str, Any]:
    getter = getattr(ticker, "get_info", None)
    try:
        info = getter() if callable(getter) else getattr(ticker, "info", {})
    except Exception as exc:  # pragma: no cover - provider-specific failure shape
        raise ResearchDocumentError(
            "Yahoo Finance profile fetch failed.",
            details={"provider": YahooFinanceResearchAdapter.provider},
        ) from exc
    return info if isinstance(info, dict) else {}


def _ticker_news(ticker: Any) -> list[dict[str, Any]]:
    try:
        raw_news = getattr(ticker, "news", [])
    except Exception:
        raw_news = []
    if callable(raw_news):
        raw_news = raw_news()
    if not isinstance(raw_news, list):
        return []
    return [item for item in raw_news if isinstance(item, dict)]


def _yahoo_profile_payload(
    request: ExternalResearchFetchRequest,
    info: Mapping[str, Any],
    *,
    fetched_at: datetime,
) -> ExternalResearchSourcePayload:
    symbol = _normalize_symbol(request.symbol)
    company_name = _external_text_value(info.get("longName")) or request.company_name or symbol
    currency = _external_text_value(info.get("currency"))
    lines = [
        f"{label}: {_external_profile_field_value(key, info.get(key), currency=currency)}"
        for key, label in YAHOO_RESEARCH_PROFILE_FIELDS
    ]
    summary = _external_text_value(info.get("longBusinessSummary"))
    if summary:
        lines.extend(["", "Business Summary:", summary])
    lines.extend(
        [
            "",
            "Data Quality Notes:",
            "This provider profile is a market-data provider snapshot, not an audited filing.",
            "Confirm important facts against official IR, annual report, or regulatory filings.",
        ]
    )
    return ExternalResearchSourcePayload(
        symbol=symbol,
        title=f"{company_name} Yahoo Finance Profile",
        content="\n".join(line for line in lines if line.strip()),
        source_type="provider_profile",
        source_url=f"https://finance.yahoo.com/quote/{symbol}/profile",
        provider=YahooFinanceResearchAdapter.provider,
        company_name=company_name,
        published_at=request.as_of,
        fetched_at=fetched_at,
        reliability=Decimal("0.65"),
    )


def _yahoo_news_payloads(
    request: ExternalResearchFetchRequest,
    news_items: Sequence[Mapping[str, Any]],
    *,
    fetched_at: datetime,
) -> list[ExternalResearchSourcePayload]:
    payloads: list[ExternalResearchSourcePayload] = []
    symbol = _normalize_symbol(request.symbol)
    for item in news_items:
        title = _external_text_value(item.get("title"))
        url = _external_text_value(item.get("link") or item.get("url"))
        if not title or not url:
            continue
        publisher = _external_text_value(item.get("publisher")) or "Yahoo Finance"
        summary = _external_text_value(item.get("summary") or item.get("content")) or title
        published_at = _date_from_epoch(item.get("providerPublishTime"))
        content = "\n".join(
            [
                f"source: {publisher}",
                f"url: {url}",
                f"summary: {summary}",
                "",
                summary,
            ]
        )
        payloads.append(
            ExternalResearchSourcePayload(
                symbol=symbol,
                title=title,
                content=content,
                source_type="news",
                source_url=url,
                provider=YahooFinanceResearchAdapter.provider,
                company_name=request.company_name,
                published_at=published_at,
                fetched_at=fetched_at,
                reliability=Decimal("0.60"),
            )
        )
    return payloads


def _tdnet_symbol_code(symbol: str) -> str:
    match = re.match(r"^\s*(\d{4})", symbol)
    return match.group(1) if match else ""


def _tdnet_payloads_from_html(
    request: ExternalResearchFetchRequest,
    html_text: str,
    *,
    list_url: str,
    fetched_at: datetime,
    published_at: date,
) -> list[ExternalResearchSourcePayload]:
    symbol_code = _tdnet_symbol_code(request.symbol)
    if not symbol_code:
        return []
    rows = re.findall(r"<tr\b[^>]*>.*?</tr>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if not rows:
        rows = html_text.splitlines()
    payloads: list[ExternalResearchSourcePayload] = []
    for row in rows:
        row_text = _clean_html_text(row)
        if symbol_code not in row_text:
            continue
        href = _first_href(row)
        if not href:
            continue
        title = _tdnet_row_title(row) or row_text
        source_url = urljoin(list_url, html.unescape(href))
        company_name = request.company_name or _tdnet_company_name(row_text, symbol_code)
        payloads.append(
            ExternalResearchSourcePayload(
                symbol=_normalize_symbol(request.symbol),
                title=f"{symbol_code} TDnet {title}",
                content=_tdnet_payload_content(
                    title=title,
                    row_text=row_text,
                    source_url=source_url,
                    company_name=company_name,
                    published_at=published_at,
                ),
                source_type="tdnet",
                source_url=source_url,
                provider=TDnetResearchAdapter.provider,
                company_name=company_name,
                published_at=published_at,
                fetched_at=fetched_at,
                reliability=Decimal("0.85"),
            )
        )
    return payloads


def _first_href(row_html: str) -> str | None:
    match = re.search(r"""href\s*=\s*["']([^"']+)["']""", row_html, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _tdnet_row_title(row_html: str) -> str:
    anchor_match = re.search(
        r"<a\b[^>]*>(.*?)</a>",
        row_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if anchor_match:
        return _clean_html_text(anchor_match.group(1))
    return ""


def _clean_html_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _tdnet_company_name(row_text: str, symbol_code: str) -> str | None:
    after_code = row_text.split(symbol_code, 1)[-1].strip()
    if not after_code:
        return None
    parts = re.split(r"\s{2,}| 適時開示 | 決算短信 | Notice | Summary ", after_code, maxsplit=1)
    company = parts[0].strip(" -")
    return company or None


def _tdnet_payload_content(
    *,
    title: str,
    row_text: str,
    source_url: str,
    company_name: str | None,
    published_at: date,
) -> str:
    lines = [
        f"title: {title}",
        f"url: {source_url}",
        f"published_at: {published_at.isoformat()}",
        "source: TDnet timely disclosure",
    ]
    if company_name:
        lines.append(f"company: {company_name}")
    lines.extend(
        [
            "",
            "Disclosure summary:",
            row_text,
            "",
            "Data Quality Notes:",
            "TDnet is an official timely-disclosure source for Japanese listed companies.",
            "Confirm PDF details before using the information in an investment decision.",
        ]
    )
    return "\n".join(lines)


def _edinet_documents_list_url(submitted_at: date, *, api_key: str) -> str:
    params = {"date": submitted_at.isoformat(), "type": "2"}
    if api_key:
        params["Subscription-Key"] = api_key
    return f"{EDINET_DOCUMENTS_LIST_URL}?{urlencode(params)}"


def _edinet_safe_url(url: str) -> str:
    return re.sub(r"([?&]Subscription-Key=)[^&]+", r"\1***", url)


def _edinet_payloads_from_response(
    request: ExternalResearchFetchRequest,
    response: Mapping[str, Any],
    *,
    fetched_at: datetime,
) -> list[ExternalResearchSourcePayload]:
    results = response.get("results", [])
    if not isinstance(results, list):
        return []
    symbol_code = _tdnet_symbol_code(request.symbol)
    payloads: list[ExternalResearchSourcePayload] = []
    for row in results:
        if not isinstance(row, Mapping):
            continue
        typed_row = cast(Mapping[str, Any], row)
        if not _edinet_row_matches_request(typed_row, request, symbol_code=symbol_code):
            continue
        doc_id = _edinet_row_text(typed_row, "docID", "docId", "documentId")
        if not doc_id:
            continue
        description = (
            _edinet_row_text(typed_row, "docDescription", "documentDescription")
            or "EDINET disclosure"
        )
        filer_name = _edinet_row_text(typed_row, "filerName", "issuerName")
        published_at = _edinet_published_at(typed_row)
        source_url = _edinet_document_url(doc_id)
        payloads.append(
            ExternalResearchSourcePayload(
                symbol=_normalize_symbol(request.symbol),
                title=_edinet_payload_title(
                    request.symbol,
                    description=description,
                    symbol_code=symbol_code,
                ),
                content=_edinet_payload_content(
                    typed_row,
                    description=description,
                    source_url=source_url,
                    filer_name=filer_name,
                    published_at=published_at,
                ),
                source_type=_edinet_source_type(typed_row, description),
                source_url=source_url,
                provider=EDINETResearchAdapter.provider,
                company_name=request.company_name or filer_name or None,
                published_at=published_at,
                fetched_at=fetched_at,
                reliability=Decimal("0.90"),
            )
        )
    return payloads


def _edinet_row_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        text = _external_text_value(value)
        if text:
            return text
    return ""


def _edinet_row_matches_request(
    row: Mapping[str, Any],
    request: ExternalResearchFetchRequest,
    *,
    symbol_code: str,
) -> bool:
    sec_code = _edinet_row_text(row, "secCode", "securityCode")
    if symbol_code and sec_code.startswith(symbol_code):
        return True
    haystack = " ".join(
        _edinet_row_text(row, key)
        for key in ("filerName", "issuerName", "docDescription", "documentDescription")
    ).casefold()
    keywords = [
        request.company_name or "",
        *request.related_keywords,
        _normalize_symbol(request.symbol),
        symbol_code,
    ]
    return any(keyword.strip().casefold() in haystack for keyword in keywords if keyword.strip())


def _edinet_published_at(row: Mapping[str, Any]) -> date | None:
    for key in ("submitDateTime", "submitDate", "receiveDateTime", "opeDateTime"):
        text = _edinet_row_text(row, key)
        if not text:
            continue
        match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if not match:
            continue
        try:
            return date.fromisoformat(match.group(0))
        except ValueError:
            continue
    return None


def _edinet_document_url(doc_id: str) -> str:
    return f"{EDINET_DOCUMENT_URL_TEMPLATE.format(doc_id=doc_id)}?type=2"


def _edinet_payload_title(symbol: str, *, description: str, symbol_code: str) -> str:
    display_symbol = symbol_code or _normalize_symbol(symbol)
    return f"{display_symbol} EDINET {description}"


def _edinet_source_type(row: Mapping[str, Any], description: str) -> ResearchSourceType:
    doc_type_code = _edinet_row_text(row, "docTypeCode")
    if doc_type_code in {"120", "130", "140", "150"}:
        return "annual_report"
    if any(keyword in description for keyword in ("有価証券報告書", "四半期報告書", "半期報告書")):
        return "annual_report"
    if "臨時報告書" in description:
        return "annual_report"
    return "annual_report"


def _edinet_payload_content(
    row: Mapping[str, Any],
    *,
    description: str,
    source_url: str,
    filer_name: str,
    published_at: date | None,
) -> str:
    lines = [
        f"title: {description}",
        f"url: {source_url}",
        "source: EDINET official filing",
    ]
    if published_at:
        lines.append(f"published_at: {published_at.isoformat()}")
    details = [
        ("filer_name", filer_name),
        ("edinet_code", _edinet_row_text(row, "edinetCode")),
        ("securities_code", _edinet_row_text(row, "secCode", "securityCode")),
        ("document_id", _edinet_row_text(row, "docID", "docId", "documentId")),
        ("document_type_code", _edinet_row_text(row, "docTypeCode")),
        ("period_start", _edinet_row_text(row, "periodStart")),
        ("period_end", _edinet_row_text(row, "periodEnd")),
        ("submit_datetime", _edinet_row_text(row, "submitDateTime", "submitDate")),
    ]
    lines.extend(f"{label}: {value}" for label, value in details if value)
    lines.extend(
        [
            "",
            "Filing summary:",
            description,
            "",
            "Data Quality Notes:",
            "EDINET is an official disclosure source for Japanese securities reports.",
            "This adapter records the filing metadata and source link; confirm report body details before using the information in an investment decision.",
        ]
    )
    return "\n".join(lines)


def _normalize_external_url(value: str | None) -> str:
    text = _external_text_value(value)
    if not text:
        return ""
    if not re.match(r"^https?://", text, flags=re.IGNORECASE):
        text = f"https://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", ""))


def _company_ir_candidate_urls(
    website: str,
    candidate_paths: Sequence[str],
) -> list[str]:
    normalized = _normalize_external_url(website)
    if not normalized:
        return []
    parsed = urlparse(normalized)
    candidates: list[str] = []
    if _company_ir_url_looks_relevant(normalized):
        candidates.append(normalized)
    root = urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))
    path_base = (
        urlunparse((parsed.scheme, parsed.netloc, f"{parsed.path.strip('/')}/", "", "", ""))
        if parsed.path.strip("/")
        else root
    )
    for raw_path in candidate_paths:
        path = raw_path.strip().strip("/")
        if not path:
            continue
        for base in (root, path_base):
            url = urljoin(base, path)
            if url not in candidates:
                candidates.append(url)
    return candidates


def _company_ir_url_looks_relevant(url: str) -> bool:
    path = urlparse(url).path.casefold()
    return any(token in path for token in ("ir", "investor"))


def _company_ir_page_is_relevant(html_text: str) -> bool:
    text = _clean_html_text(html_text).casefold()
    if not text:
        return False
    keywords = (
        "investor relations",
        "investors",
        "ir library",
        "financial results",
        "annual report",
        "integrated report",
        "株主",
        "投資家",
        "決算",
        "有価証券報告書",
        "統合報告書",
        "ir情報",
    )
    return any(keyword.casefold() in text for keyword in keywords)


def _company_ir_site_payload(
    request: ExternalResearchFetchRequest,
    html_text: str,
    *,
    source_url: str,
    fetched_at: datetime,
) -> ExternalResearchSourcePayload:
    symbol = _normalize_symbol(request.symbol)
    company_name = request.company_name or symbol
    page_text = _clean_html_text(html_text)
    content = "\n".join(
        [
            f"title: {company_name} official IR site",
            f"url: {source_url}",
            "source: company official IR site",
            f"company: {company_name}",
            "",
            "IR page summary:",
            _excerpt(page_text, max_chars=720),
            "",
            "Data Quality Notes:",
            "This adapter records a company official IR site page discovered from official website metadata.",
            "Use the page as a starting point for official documents; confirm document dates and PDF details before using the information in an investment decision.",
        ]
    )
    return ExternalResearchSourcePayload(
        symbol=symbol,
        title=f"{company_name} 公式IRサイト",
        content=content,
        source_type="company_ir",
        source_url=source_url,
        provider=CompanyIRSiteResearchAdapter.provider,
        company_name=company_name,
        published_at=None,
        fetched_at=fetched_at,
        reliability=Decimal("0.82"),
    )


def _external_text_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value:.6g}"
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def _external_profile_field_value(key: str, value: object, *, currency: str) -> str:
    if key in {"holdings", "topHoldings"}:
        return _external_profile_holdings_text(value)
    numeric_value = _external_decimal_value(value)
    if numeric_value is None:
        return _external_text_value(value)
    if key in {
        "marketCap",
        "enterpriseValue",
        "totalRevenue",
        "revenue",
        "operatingIncome",
        "netIncomeToCommon",
        "netIncome",
        "netAssets",
        "totalAssets",
    }:
        return _format_external_money(numeric_value, currency=currency)
    if key == "fullTimeEmployees":
        return f"{_format_external_decimal(numeric_value, thousands=True)} 人"
    if key in {"trailingEps", "forwardEps", "navPrice", "regularMarketPrice"}:
        return _format_external_per_share(numeric_value, currency=currency)
    if key in {"trailingPE", "forwardPE", "priceToBook"}:
        return f"{_format_external_decimal(numeric_value)}倍"
    if key in {
        "dividendYield",
        "yield",
        "trailingAnnualDividendYield",
        "expenseRatio",
        "annualReportExpenseRatio",
    }:
        return _external_profile_percentage_text(numeric_value, ratio_threshold=Decimal("0.2"))
    if key in {"returnOnEquity", "payoutRatio"}:
        return _external_profile_percentage_text(numeric_value, ratio_threshold=Decimal("1"))
    return _format_external_decimal(numeric_value)


def _external_profile_percentage_text(
    numeric_value: Decimal,
    *,
    ratio_threshold: Decimal,
) -> str:
    percentage = (
        numeric_value * Decimal("100") if abs(numeric_value) <= ratio_threshold else numeric_value
    )
    return f"{_format_external_decimal(percentage)}%"


def _external_profile_holdings_text(value: object) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        iterable: Iterable[object] = value.values()
    elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        iterable = value
    else:
        return _external_text_value(value)
    holdings: list[str] = []
    for item in iterable:
        if isinstance(item, Mapping):
            name = _external_text_value(
                item.get("symbol")
                or item.get("holdingName")
                or item.get("name")
                or item.get("shortName")
            )
        else:
            name = _external_text_value(item)
        if name:
            holdings.append(name)
    return ", ".join(_unique_text(holdings)[:12])


def _external_decimal_value(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, int | float):
        parsed = Decimal(str(value))
        return parsed if parsed.is_finite() else None
    text = str(value).replace(",", "").strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() else None


def _format_external_decimal(
    value: Decimal,
    *,
    thousands: bool = False,
    decimal_places: int = 2,
) -> str:
    if value == value.to_integral_value():
        return f"{int(value):,}" if thousands else str(int(value))
    template = f"{{:,.{decimal_places}f}}" if thousands else f"{{:.{decimal_places}f}}"
    return template.format(float(value)).rstrip("0").rstrip(".")


def _format_external_money(value: Decimal, *, currency: str) -> str:
    cleaned_currency = currency.strip().upper()
    if cleaned_currency == "JPY":
        abs_value = abs(value)
        if abs_value >= Decimal("1000000000000"):
            return f"{_format_external_decimal(value / Decimal('1000000000000'))}兆円"
        if abs_value >= Decimal("100000000"):
            return f"{_format_external_decimal(value / Decimal('100000000'), thousands=True)}億円"
        if abs_value >= Decimal("10000"):
            return f"{_format_external_decimal(value / Decimal('10000'), thousands=True)}万円"
        return f"{_format_external_decimal(value)}円"
    abs_value = abs(value)
    for divisor, suffix in (
        (Decimal("1000000000000"), "T"),
        (Decimal("1000000000"), "B"),
        (Decimal("1000000"), "M"),
    ):
        if abs_value >= divisor:
            formatted = _format_external_decimal(value / divisor)
            return f"{formatted}{suffix} {cleaned_currency}".strip()
    formatted = _format_external_decimal(value, thousands=True)
    return f"{formatted} {cleaned_currency}".strip()


def _format_external_per_share(value: Decimal, *, currency: str) -> str:
    cleaned_currency = currency.strip().upper()
    if cleaned_currency == "JPY":
        return f"{_format_external_decimal(value)}円"
    formatted = _format_external_decimal(value)
    return f"{formatted} {cleaned_currency}".strip()


def _date_from_epoch(value: object) -> date | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC).date()
    return None
