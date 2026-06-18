from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Literal, Protocol, Sequence, TypeVar, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

import yaml  # type: ignore[import-untyped]
from pydantic import Field, ValidationError

from backend.core.config import ExternalFetchPerformanceConfig, resolve_performance_profile
from backend.core.data_contracts import DataQuality, StrictBaseModel
from backend.core.errors import AppError, ProviderUnavailableError, ValidationAppError
from backend.research.source_trace import (
    ResearchSourceTrace,
    research_profile_source_key_for_provider,
    research_source_trace_from_result,
)

DEFAULT_EXTERNAL_RESEARCH_TIMEOUT_SECONDS = 10.0

_T = TypeVar("_T")

ResearchSourceType = Literal[
    "annual_report",
    "earnings_report",
    "earnings_presentation",
    "medium_term_plan",
    "integrated_report",
    "company_ir",
    "tdnet",
    "news",
    "provider_profile",
    "user_note",
]
ResearchLanguage = Literal["ja", "en", "unknown"]
ResearchTopicCategory = Literal[
    "growth",
    "shareholder_return",
    "financial_safety",
    "business_risk",
    "confirmation_gap",
]
ResearchRetrievalBackend = Literal["keyword", "vector", "hybrid"]
StockNewsInvestmentViewpoint = Literal[
    "earnings",
    "growth",
    "shareholder_return",
    "risk",
    "macro",
    "other",
]
StockNewsSentiment = Literal["positive", "negative", "neutral", "mixed", "unknown"]
StockNewsFreshnessStatus = Literal["latest", "recent", "stale", "unknown"]
ResearchSourceConfidence = Literal["high", "medium", "low", "unknown"]
ResearchEvidenceLevel = Literal["high", "medium", "low", "missing"]
SecurityResearchType = Literal[
    "domestic_stock",
    "foreign_stock",
    "etf",
    "fund",
    "unknown",
]
ResearchEvidenceKind = Literal[
    "company_profile",
    "business_description",
    "financial_metric",
    "ir_document",
    "tdnet_disclosure",
    "news",
    "market_data",
    "unknown",
]
ResearchEvidenceReliability = Literal[
    "official",
    "semi_official",
    "market_provider",
    "news",
    "unknown",
]
InformationStatus = Literal[
    "found",
    "missing",
    "unparsed",
    "unverified",
    "not_applicable",
]
IRDocumentType = Literal[
    "earnings_summary",
    "earnings_presentation",
    "annual_report",
    "timely_disclosure",
    "medium_term_plan",
    "shareholder_return",
    "forecast_revision",
    "other",
]
NewsImpactHint = Literal[
    "business",
    "financial",
    "market",
    "governance",
    "product",
    "ir",
    "unknown",
]
LatestTopicType = Literal[
    "news",
    "tdnet",
    "ir_disclosure",
    "earnings",
    "forecast_revision",
    "shareholder_return",
    "business_reorganization",
    "product",
    "governance",
    "unknown",
]
InvestmentSignal = Literal[
    "positive",
    "negative",
    "neutral",
    "mixed",
    "unknown",
]
InvestmentActionHint = Literal[
    "watch",
    "review",
    "wait_for_confirmation",
    "check_official_materials",
    "insufficient_evidence",
]
InvestmentViewStatus = Literal[
    "追加確認が必要",
    "監視向き",
    "材料混在",
    "判断材料不足",
    "公式資料確認待ち",
    "ニュース先行",
    "定量指標不足",
]
InvestmentQuestionCategory = Literal[
    "business_model",
    "financial_trend",
    "profitability",
    "forecast",
    "growth_driver",
    "risk",
    "shareholder_return",
    "valuation",
    "recent_news_impact",
    "key_takeaway",
]
InvestmentQuestionEvidenceLevel = ResearchEvidenceLevel
ResearchMissingItemCategory = Literal[
    "official_source",
    "financial_metric",
    "source_freshness",
    "news",
    "other",
]
ResearchMetricKey = Literal[
    "revenue",
    "operating_income",
    "net_income",
    "eps",
    "dividend",
    "per",
    "pbr",
    "roe",
    "market_cap",
]

RESEARCH_SCHEMA_VERSION = "research-evidence-v1"
DEFAULT_MAX_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 180
DEFAULT_RESEARCH_EMBEDDING_DIMENSIONS = 32
DEFAULT_RESEARCH_EMBEDDING_MODEL = "local-hash-v1"
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
DEFAULT_RESEARCH_QUERY_TERMS: dict[ResearchTopicCategory, tuple[str, ...]] = {
    "growth": (
        "growth strategy",
        "market expansion",
        "overseas expansion",
        "new business",
        "medium-term plan",
        "investment plan",
        "revenue expansion",
        "成長戦略",
        "海外展開",
        "新規事業",
        "中期経営計画",
        "投資計画",
        "収益拡大",
        "事業拡大",
    ),
    "shareholder_return": (
        "shareholder return",
        "dividend",
        "dividend policy",
        "payout ratio",
        "buyback",
        "DOE",
        "株主還元",
        "配当",
        "増配",
        "自社株買い",
        "配当性向",
        "利益還元",
    ),
    "financial_safety": (
        "financial safety",
        "equity ratio",
        "cash",
        "cash equivalents",
        "interest-bearing debt",
        "credit rating",
        "liquidity",
        "財務安全性",
        "自己資本比率",
        "キャッシュ",
        "現金同等物",
        "有利子負債",
        "格付け",
        "財務余力",
    ),
    "business_risk": (
        "business risk",
        "foreign exchange",
        "raw material",
        "regulation",
        "lawsuit",
        "geopolitical",
        "supply chain",
        "dependency",
        "事業リスク",
        "為替",
        "原材料",
        "規制",
        "訴訟",
        "地政学",
        "サプライチェーン",
        "依存度",
    ),
    "confirmation_gap": (
        "missing evidence",
        "confirmation gap",
        "stale document",
        "official IR not confirmed",
        "additional confirmation",
        "根拠不足",
        "確認不足",
        "資料不足",
        "古い資料",
        "公式IR未確認",
        "追加確認",
    ),
}


class ResearchDocumentError(AppError):
    """Local research document registration failed."""

    code = "RESEARCH-1001"


def _research_fetch_with_retry(
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
            if retry_attempts >= retry_count or not _is_retryable_research_fetch_error(exc):
                details: dict[str, object] = {
                    "provider": provider,
                    "retry_attempts": retry_attempts,
                    "error_type": type(exc).__name__,
                    "timeout": _is_timeout_research_fetch_error(exc),
                }
                status_code = _research_fetch_http_status(exc)
                if status_code is not None:
                    details["status_code"] = status_code
                if url:
                    details["url"] = url
                raise ResearchDocumentError(error_message, details=details) from exc
            retry_attempts += 1
            if retry_backoff_sec > 0:
                time.sleep(retry_backoff_sec * retry_attempts)


def _is_retryable_research_fetch_error(exc: Exception) -> bool:
    status_code = _research_fetch_http_status(exc)
    if status_code is not None:
        return 500 <= status_code <= 599
    if _is_timeout_research_fetch_error(exc):
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


def _is_timeout_research_fetch_error(exc: Exception) -> bool:
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


def _research_fetch_http_status(exc: Exception) -> int | None:
    if isinstance(exc, HTTPError):
        return int(exc.code)
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    code = getattr(exc, "code", None)
    return int(code) if isinstance(code, int) else None


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


class ResearchParseError(AppError):
    """Local research document text could not be parsed into chunks."""

    code = "RESEARCH-1002"


class ResearchSearchError(AppError):
    """Research retrieval could not be executed."""

    code = "RESEARCH-1003"


class ResearchDocumentRegisterRequest(StrictBaseModel):
    """Metadata required to register a local research document."""

    symbol: str = Field(min_length=1)
    title: str = Field(min_length=1)
    local_path: str = Field(min_length=1)
    source_type: ResearchSourceType = "user_note"
    company_name: str | None = None
    published_at: date | None = None
    language: ResearchLanguage = "unknown"
    reliability: Decimal = Field(default=Decimal("0.70"), ge=0, le=1)


class ResearchDocument(StrictBaseModel):
    """Registered local document metadata."""

    schema_version: str = RESEARCH_SCHEMA_VERSION
    document_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: ResearchSourceType
    company_name: str | None = None
    published_at: date | None = None
    collected_at: datetime
    local_path: str
    language: ResearchLanguage = "unknown"
    provider: str = "local"
    reliability: Decimal = Field(ge=0, le=1)
    document_hash: str = Field(min_length=1)


class ResearchChunk(StrictBaseModel):
    """Searchable text chunk derived from a registered research document."""

    schema_version: str = RESEARCH_SCHEMA_VERSION
    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: ResearchSourceType
    published_at: date | None = None
    section_title: str | None = None
    text: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    char_count: int = Field(ge=1)
    metadata: dict[str, str] = Field(default_factory=dict)


class ResearchIndexSummary(StrictBaseModel):
    """Result of rebuilding local research chunks."""

    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    symbols: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchVectorIndexSummary(StrictBaseModel):
    """Result of rebuilding an optional local research vector index."""

    schema_version: str = "research-vector-index-v1"
    embedding_model: str = Field(min_length=1)
    dimensions: int = Field(ge=2)
    chunk_count: int = Field(ge=0)
    embedded_count: int = Field(ge=0)
    symbols: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResearchSearchRequest(StrictBaseModel):
    """Keyword research search request."""

    symbol: str = Field(min_length=1)
    query: str = ""
    top_k: int = Field(default=8, ge=1, le=50)
    source_types: list[ResearchSourceType] = Field(default_factory=list)
    as_of: date | None = None
    query_category: ResearchTopicCategory | None = None
    expanded_terms: list[str] = Field(default_factory=list)
    query_vector: list[float] = Field(default_factory=list)


class ResearchQueryExpansionResult(StrictBaseModel):
    """Deterministic expanded query terms for a research topic."""

    query: str
    category: ResearchTopicCategory | None = None
    expanded_terms: list[str] = Field(default_factory=list)


class ResearchEvidence(StrictBaseModel):
    """One retrieved evidence chunk with traceable source metadata."""

    symbol: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: ResearchSourceType
    published_at: date | None = None
    section_title: str | None = None
    excerpt: str = Field(min_length=1)
    relevance_score: Decimal = Field(ge=0, le=1)
    reliability: Decimal = Field(ge=0, le=1)


class ResearchSummaryPoint(StrictBaseModel):
    """Human-facing summary row backed by retrieved evidence."""

    category: ResearchTopicCategory
    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: list[ResearchEvidence] = Field(default_factory=list)


class ResearchExtractedClaim(StrictBaseModel):
    """Structured Phase 21 research claim that stays tied to source evidence."""

    schema_version: str = "research-extraction-v1"
    symbol: str = Field(min_length=1)
    category: ResearchTopicCategory
    claim: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    supporting_evidence: list[ResearchEvidence] = Field(default_factory=list)
    confidence: Decimal = Field(ge=0, le=1)
    missing_information: list[str] = Field(default_factory=list)
    caution_note: str | None = None


class ResearchGroundedAnswer(StrictBaseModel):
    """Template-generated answer built only from extracted claims and evidence."""

    schema_version: str = "research-grounded-answer-v1"
    symbol: str = Field(min_length=1)
    provider: Literal["template"] = "template"
    answer: str = Field(min_length=1)
    referenced_evidence: list[ResearchEvidence] = Field(default_factory=list)
    claim_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class ResearchRetrievalQuality(StrictBaseModel):
    """Phase 21 retrieval transparency for UI and Decision Report display."""

    schema_version: str = "research-retrieval-quality-v1"
    backend: ResearchRetrievalBackend = "keyword"
    query: str = Field(min_length=1)
    expanded_terms: list[str] = Field(default_factory=list)
    candidate_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class ResearchEmbedding(StrictBaseModel):
    """Optional embedding payload for future local vector retrieval."""

    schema_version: str = "research-embedding-v1"
    chunk_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    embedding_model: str = Field(min_length=1)
    vector: list[float] = Field(default_factory=list)
    created_at: datetime
    text_hash: str = Field(min_length=1)


class ResearchRetrievalCandidate(StrictBaseModel):
    """Intermediate row carrying keyword, vector, and hybrid retrieval scores."""

    symbol: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: ResearchSourceType
    published_at: date | None = None
    section_title: str | None = None
    excerpt: str = Field(min_length=1)
    keyword_score: Decimal | None = Field(default=None, ge=0, le=1)
    vector_score: Decimal | None = Field(default=None, ge=0, le=1)
    freshness_score: Decimal | None = Field(default=None, ge=0, le=1)
    reliability: Decimal = Field(ge=0, le=1)
    final_relevance_score: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    retrieval_backend: ResearchRetrievalBackend = "keyword"


class ResearchHybridScoreWeights(StrictBaseModel):
    """Deterministic score weights for optional hybrid retrieval."""

    keyword_weight: Decimal = Field(default=Decimal("0.40"), ge=0, le=1)
    vector_weight: Decimal = Field(default=Decimal("0.35"), ge=0, le=1)
    freshness_weight: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    reliability_weight: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    source_type_weight: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)


class ResearchDataQuality(StrictBaseModel):
    """Availability and freshness of local research evidence."""

    status: DataQuality
    latest_document_date: date | None = None
    document_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class CompanyResearchRequest(StrictBaseModel):
    """Build a deterministic company research report for one symbol."""

    symbol: str = Field(min_length=1)
    as_of: date | None = None
    top_k_per_topic: int = Field(default=3, ge=1, le=10)


class CompanyResearchReport(StrictBaseModel):
    """Deterministic Phase 20 company research summary."""

    schema_version: str = RESEARCH_SCHEMA_VERSION
    symbol: str = Field(min_length=1)
    as_of: date
    summary: str = Field(min_length=1)
    points: list[ResearchSummaryPoint]
    extracted_claims: list[ResearchExtractedClaim] = Field(default_factory=list)
    grounded_answer: ResearchGroundedAnswer | None = None
    evidence: list[ResearchEvidence]
    data_quality: ResearchDataQuality
    retrieval_quality: ResearchRetrievalQuality | None = None
    decision_support_note: str = "Research evidence is decision support only; not advice."


class ResearchScore(StrictBaseModel):
    """Optional evidence-backed Research Score for Phase 22 preparation."""

    schema_version: str = "research-score-v1"
    symbol: str = Field(min_length=1)
    as_of: date
    total_score: Decimal = Field(ge=0, le=100)
    growth_score: Decimal = Field(ge=0, le=100)
    profitability_score: Decimal = Field(ge=0, le=100)
    shareholder_return_score: Decimal = Field(ge=0, le=100)
    financial_safety_score: Decimal = Field(ge=0, le=100)
    business_risk_score: Decimal = Field(ge=0, le=100)
    disclosure_quality_score: Decimal = Field(ge=0, le=100)
    freshness_score: Decimal = Field(ge=0, le=100)
    evidence_count: int = Field(ge=0)
    confidence: Decimal = Field(ge=0, le=1)
    supporting_evidence: list[ResearchEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    decision_support_note: str = (
        "Research Score is an evidence-coverage signal for decision support; not advice."
    )


class StockNewsEvidence(StrictBaseModel):
    """Traceable news evidence for one selected symbol."""

    schema_version: str = "stock-news-evidence-v1"
    symbol: str = Field(min_length=1)
    company_name: str | None = None
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    source: str | None = None
    published_at: date | None = None
    summary: str = Field(min_length=1)
    investment_viewpoint: StockNewsInvestmentViewpoint = "other"
    sentiment_for_investment: StockNewsSentiment = "unknown"
    freshness_status: StockNewsFreshnessStatus = "unknown"


class StockNewsRequest(StrictBaseModel):
    """Build a deterministic news evidence view for one selected symbol."""

    symbol: str = Field(min_length=1)
    company_name: str | None = None
    related_keywords: list[str] = Field(default_factory=list)
    as_of: date | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class StockNewsReport(StrictBaseModel):
    """Deterministic Phase 21.5 selected-symbol news summary."""

    schema_version: str = "stock-news-report-v1"
    symbol: str = Field(min_length=1)
    company_name: str | None = None
    as_of: date
    news: list[StockNewsEvidence] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    decision_support_note: str = (
        "News evidence is decision support only; not advice and not a score input."
    )


class ExternalResearchFetchRequest(StrictBaseModel):
    """Explicit opt-in request for external research/news source adapters."""

    symbol: str = Field(min_length=1)
    company_name: str | None = None
    related_keywords: list[str] = Field(default_factory=list)
    provider: str = Field(min_length=1)
    as_of: date | None = None
    allow_network: bool = False


class ExternalResearchSourcePayload(StrictBaseModel):
    """Fetched external source payload before local cache/registration."""

    symbol: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_url: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    company_name: str | None = None
    published_at: date | None = None
    fetched_at: datetime
    reliability: Decimal = Field(default=Decimal("0.70"), ge=0, le=1)


class ExternalResearchFetchManifestEntry(StrictBaseModel):
    """Trace row for an explicitly fetched external source."""

    title: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_url: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    published_at: date | None = None
    fetched_at: datetime
    freshness_status: StockNewsFreshnessStatus = "unknown"
    document_id: str = Field(min_length=1)
    retention_policy: Literal["session", "archive"] = "session"
    content_summary: str = ""
    local_path: str | None = None
    document_hash: str | None = None


class ExternalResearchFetchResult(StrictBaseModel):
    """Result of opt-in external fetch registered for the current analysis session."""

    symbol: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    fetched_at: datetime
    entries: list[ExternalResearchFetchManifestEntry] = Field(default_factory=list)
    retention_policy: Literal["session", "archive"] = "session"
    manifest_path: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ResearchMetric(StrictBaseModel):
    """Display-only metric extracted from research evidence by local rules."""

    schema_version: str = "research-metric-v1"
    key: ResearchMetricKey
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_confidence: ResearchSourceConfidence = "unknown"


class ResearchBriefSourceCard(StrictBaseModel):
    """Readable source card for the local ResearchBrief UI layer."""

    title: str = Field(min_length=1)
    source_type: ResearchSourceType
    provider: str | None = None
    source_url: str | None = None
    published_at: date | None = None
    fetched_at: datetime | None = None
    freshness_status: StockNewsFreshnessStatus = "unknown"
    source_confidence: ResearchSourceConfidence = "unknown"
    note: str = ""


class ResearchBriefMaterial(StrictBaseModel):
    """Readable material candidate with source quality for the ResearchBrief UI."""

    schema_version: str = "research-brief-material-v1"
    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_confidence: ResearchSourceConfidence = "unknown"
    source_count: int = Field(ge=1)
    published_at: date | None = None


class ResearchFactItem(StrictBaseModel):
    """Source-backed fact extracted for the user-facing Research Summary."""

    schema_version: str = "research-fact-item-v1"
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_confidence: ResearchSourceConfidence = "unknown"
    published_at: date | None = None
    note: str = ""


class ResearchMissingItem(StrictBaseModel):
    """Missing fact that should be checked in official sources."""

    schema_version: str = "research-missing-item-v1"
    category: ResearchMissingItemCategory = "other"
    label: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    next_source_hint: str = Field(min_length=1)


class ResearchFactSummary(StrictBaseModel):
    """Structured user-facing facts that feed ResearchBrief/UI wording."""

    schema_version: str = "research-fact-summary-v1"
    symbol: str = Field(min_length=1)
    as_of: date
    business_overview: list[ResearchFactItem] = Field(default_factory=list)
    business_segments: list[ResearchFactItem] = Field(default_factory=list)
    business_regions: list[ResearchFactItem] = Field(default_factory=list)
    revenue_drivers: list[ResearchFactItem] = Field(default_factory=list)
    financial_snapshot: list[ResearchFactItem] = Field(default_factory=list)
    earnings_outlook: list[ResearchFactItem] = Field(default_factory=list)
    shareholder_return_policy: list[ResearchFactItem] = Field(default_factory=list)
    recent_events: list[ResearchFactItem] = Field(default_factory=list)
    positive_materials: list[ResearchFactItem] = Field(default_factory=list)
    caution_materials: list[ResearchFactItem] = Field(default_factory=list)
    missing_items: list[ResearchMissingItem] = Field(default_factory=list)
    decision_support_note: str = (
        "ResearchFactSummary contains source-backed facts for decision support; not advice."
    )


class ResearchBrief(StrictBaseModel):
    """Local rule-based research memo for display; it does not change scores."""

    schema_version: str = "research-brief-v1"
    symbol: str = Field(min_length=1)
    as_of: date
    memo: str = Field(min_length=1)
    metrics: list[ResearchMetric] = Field(default_factory=list)
    missing_metrics: list[str] = Field(default_factory=list)
    business_overview: str = Field(min_length=1)
    positive_candidates: list[str] = Field(default_factory=list)
    caution_candidates: list[str] = Field(default_factory=list)
    positive_materials: list[ResearchBriefMaterial] = Field(default_factory=list)
    caution_materials: list[ResearchBriefMaterial] = Field(default_factory=list)
    confirmation_gaps: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    source_cards: list[ResearchBriefSourceCard] = Field(default_factory=list)
    fact_summary: ResearchFactSummary | None = None
    decision_support_note: str = (
        "ResearchBrief is a local evidence memo for decision support; not advice."
    )


class CompanyResearchEvidence(StrictBaseModel):
    """Normalized source row before company-understanding summary mapping."""

    kind: ResearchEvidenceKind
    title: str = Field(min_length=1)
    body: str = ""
    source_type: str = ""
    source_title: str = ""
    source_url: str | None = None
    reliability: ResearchEvidenceReliability = "unknown"
    information_status: InformationStatus = "found"
    published_at: date | None = None
    extracted_keywords: list[str] = Field(default_factory=list)


class CompanyBusinessProfile(StrictBaseModel):
    """Structured business profile extracted mainly from profile / official sources."""

    company_name: str = ""
    symbol: str = ""
    industry: str | None = None
    sector: str | None = None
    business_summary: str = ""
    main_businesses: list[str] = Field(default_factory=list)
    supporting_businesses: list[str] = Field(default_factory=list)
    products_services: list[str] = Field(default_factory=list)
    products_services_status: InformationStatus = "missing"
    regions: list[str] = Field(default_factory=list)
    customer_segments: list[str] = Field(default_factory=list)
    information_status: InformationStatus = "missing"
    evidence_level: ResearchEvidenceLevel = "missing"
    source_titles: list[str] = Field(default_factory=list)


class CompanyOverviewSummary(StrictBaseModel):
    """Company-understanding overview for the Research report UI."""

    company_name: str = ""
    symbol: str = Field(min_length=1)
    business_profile: CompanyBusinessProfile | None = None
    industry: str | None = None
    sector: str | None = None
    business_overview: str = ""
    main_businesses: list[str] = Field(default_factory=list)
    business_segments: list[str] = Field(default_factory=list)
    supporting_businesses: list[str] = Field(default_factory=list)
    products_services: list[str] = Field(default_factory=list)
    products_services_status: InformationStatus = "missing"
    regions: list[str] = Field(default_factory=list)
    customer_segments: list[str] = Field(default_factory=list)
    scale_summary: str = ""
    recent_focus: str = ""
    information_status: InformationStatus = "missing"
    evidence_level: ResearchEvidenceLevel = "missing"
    source_titles: list[str] = Field(default_factory=list)


class QuantitativeSummary(StrictBaseModel):
    """Major quantitative fields available from Research evidence."""

    revenue: str | None = None
    operating_profit: str | None = None
    net_income: str | None = None
    eps: str | None = None
    per: str | None = None
    pbr: str | None = None
    roe: str | None = None
    dividend_yield: str | None = None
    market_cap: str | None = None
    enterprise_value: str | None = None
    employee_count: str | None = None
    summary: str = ""
    missing_items: list[str] = Field(default_factory=list)
    item_statuses: dict[str, InformationStatus] = Field(default_factory=dict)
    information_status: InformationStatus = "missing"
    evidence_level: ResearchEvidenceLevel = "missing"
    source_titles: list[str] = Field(default_factory=list)


class IRSummaryItem(StrictBaseModel):
    """Availability and short summary for one IR / disclosure document type."""

    document_type: str = Field(min_length=1)
    ir_document_type: IRDocumentType = "other"
    title: str = Field(min_length=1)
    availability: Literal["found", "missing", "unknown"]
    information_status: InformationStatus = "missing"
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    source_title: str | None = None
    source_url: str | None = None
    evidence_level: ResearchEvidenceLevel = "missing"

    @property
    def status(self) -> InformationStatus:
        return self.information_status


class LatestTopicItem(StrictBaseModel):
    """Readable recent topic / disclosure row for the company research report."""

    topic_type: LatestTopicType = "news"
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    published_at: date | None = None
    source_title: str = ""
    source_url: str | None = None
    impact_hint: NewsImpactHint = "unknown"
    official_confirmation_required: bool = True
    information_status: InformationStatus = "unverified"
    evidence_level: ResearchEvidenceLevel = "low"

    @property
    def status(self) -> InformationStatus:
        return self.information_status


class NewsSummaryItem(LatestTopicItem):
    """Backward-compatible name for latest news / disclosure rows."""


class ETFResearchSummary(StrictBaseModel):
    """ETF / fund-understanding report assembled from Research RAG outputs."""

    schema_version: str = "etf-research-summary-v1"
    symbol: str = Field(min_length=1)
    fund_name: str = ""
    provider_name: str | None = None
    fund_overview: str = ""
    investment_target: str = ""
    asset_class: str | None = None
    region_focus: str | None = None
    sector_focus: str | None = None
    expense_ratio: str | None = None
    dividend_yield: str | None = None
    aum: str | None = None
    nav: str | None = None
    per: str | None = None
    pbr: str | None = None
    top_holdings: list[str] = Field(default_factory=list)
    benchmark_index: str | None = None
    risk_notes: list[str] = Field(default_factory=list)
    news_items: list[NewsSummaryItem] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    evidence_level: ResearchEvidenceLevel = "missing"


class CompanyResearchSummary(StrictBaseModel):
    """Company-understanding report assembled from Research RAG outputs."""

    schema_version: str = "company-research-summary-v1"
    symbol: str = Field(min_length=1)
    overview: CompanyOverviewSummary
    quantitative: QuantitativeSummary
    ir_items: list[IRSummaryItem] = Field(default_factory=list)
    news_items: list[NewsSummaryItem] = Field(default_factory=list)
    ai_reading_notes: list[str] = Field(default_factory=list)
    missing_critical_items: list[str] = Field(default_factory=list)
    normalized_evidence: list[CompanyResearchEvidence] = Field(default_factory=list)


class InvestmentInsightItem(StrictBaseModel):
    """Source-backed point for the UI-only InvestmentInsight layer."""

    label: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    signal: InvestmentSignal
    source_title: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_confidence: ResearchSourceConfidence = "unknown"
    published_at: date | None = None
    reason: str = ""


class InvestmentInsight(StrictBaseModel):
    """UI-only investment review memo; it never changes scores or ranking order."""

    schema_version: str = "investment-insight-v1"
    symbol: str = Field(min_length=1)
    as_of: date
    headline: str = Field(min_length=1)
    short_summary: str = Field(min_length=1)
    status_label: InvestmentViewStatus = "判断材料不足"
    confidence_label: str = "低"
    primary_action_label: str = "資料追加が必要"
    positive_points: list[InvestmentInsightItem] = Field(default_factory=list)
    negative_points: list[InvestmentInsightItem] = Field(default_factory=list)
    neutral_points: list[InvestmentInsightItem] = Field(default_factory=list)
    confirmation_gaps: list[str] = Field(default_factory=list)
    action_hints: list[InvestmentActionHint] = Field(default_factory=list)
    confidence: ResearchSourceConfidence = "unknown"
    decision_support_note: str = (
        "InvestmentInsight is for decision support only; not a buy/sell recommendation."
    )


class InvestmentQuestionAnswer(StrictBaseModel):
    """Answer to a fixed investment-review question, backed by available sources."""

    category: InvestmentQuestionCategory
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    evidence_level: InvestmentQuestionEvidenceLevel = "missing"
    source_titles: list[str] = Field(default_factory=list)
    missing_reason: str = ""


class InvestmentQuestionSummary(StrictBaseModel):
    """Fixed question set that turns RAG facts into investor-facing review points."""

    schema_version: str = "investment-question-summary-v1"
    symbol: str = Field(min_length=1)
    answers: list[InvestmentQuestionAnswer] = Field(default_factory=list)
    top_takeaway: str = ""
    missing_critical_items: list[str] = Field(default_factory=list)


class ResearchPageViewModel(StrictBaseModel):
    """Display-oriented summary bundle selected by security type."""

    schema_version: str = "research-page-view-model-v1"
    symbol: str = Field(min_length=1)
    security_type: SecurityResearchType = "unknown"
    company_summary: CompanyResearchSummary | None = None
    etf_summary: ETFResearchSummary | None = None
    question_summary: InvestmentQuestionSummary | None = None


class ExternalResearchSourceAdapter(Protocol):
    """Adapter protocol for opt-in external research/news fetches."""

    provider: str
    requires_network: bool

    def fetch_sources(
        self, request: ExternalResearchFetchRequest
    ) -> list[ExternalResearchSourcePayload]: ...


class ExternalStockNewsAdapter(Protocol):
    """Adapter protocol for selected-symbol external news fetches."""

    provider: str
    requires_network: bool

    def fetch_news(self, request: StockNewsRequest) -> list[StockNewsEvidence]: ...


class ResearchInMemoryStore:
    """Simple local store used by Phase 20 services and tests."""

    def __init__(self) -> None:
        self.documents: dict[str, ResearchDocument] = {}
        self.raw_text_by_document_id: dict[str, str] = {}
        self.chunks_by_document_id: dict[str, list[ResearchChunk]] = {}

    def upsert_document(self, document: ResearchDocument, text: str) -> ResearchDocument:
        existing = self.document_by_hash(document.document_hash)
        if existing is not None:
            self.raw_text_by_document_id[existing.document_id] = text
            return existing
        self.documents[document.document_id] = document
        self.raw_text_by_document_id[document.document_id] = text
        return document

    def document_by_hash(self, document_hash: str) -> ResearchDocument | None:
        return next(
            (
                document
                for document in self.documents.values()
                if document.document_hash == document_hash
            ),
            None,
        )

    def list_documents(self, symbol: str | None = None) -> list[ResearchDocument]:
        documents = list(self.documents.values())
        if symbol:
            normalized = _normalize_symbol(symbol)
            documents = [doc for doc in documents if _normalize_symbol(doc.symbol) == normalized]
        return sorted(
            documents,
            key=lambda doc: (doc.symbol, doc.published_at or date.min, doc.title),
        )

    def replace_chunks(self, document_id: str, chunks: list[ResearchChunk]) -> None:
        self.chunks_by_document_id[document_id] = chunks

    def all_chunks(self, symbol: str | None = None) -> list[ResearchChunk]:
        chunks = [chunk for group in self.chunks_by_document_id.values() for chunk in group]
        if symbol:
            normalized = _normalize_symbol(symbol)
            chunks = [chunk for chunk in chunks if _normalize_symbol(chunk.symbol) == normalized]
        return sorted(
            chunks,
            key=lambda chunk: (chunk.symbol, chunk.document_id, chunk.chunk_index),
        )


class ResearchIngestionService:
    """Register local research documents without network access."""

    def __init__(
        self,
        store: ResearchInMemoryStore,
        *,
        document_dirs: Sequence[Path] | None = None,
    ) -> None:
        self.store = store
        self.document_dirs = [directory.resolve() for directory in document_dirs or []]

    def register_document(self, request: ResearchDocumentRegisterRequest) -> ResearchDocument:
        path = Path(request.local_path).expanduser().resolve()
        if self.document_dirs and not _is_allowed_path(path, self.document_dirs):
            raise ResearchDocumentError(
                "Research document path is outside configured document directories.",
                details={
                    "local_path": str(path),
                    "document_dirs": [str(p) for p in self.document_dirs],
                },
            )
        if not path.exists() or not path.is_file():
            raise ResearchDocumentError(
                "Research document file does not exist.",
                details={"local_path": str(path)},
            )

        try:
            content = path.read_bytes()
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ResearchDocumentError(
                "Research document must be UTF-8 text for the Phase 20 MVP.",
                details={"local_path": str(path)},
            ) from exc

        stripped_text = text.strip()
        if not stripped_text:
            raise ResearchDocumentError(
                "Research document text is empty.",
                details={"local_path": str(path)},
            )

        document_hash = hashlib.sha256(content).hexdigest()
        document_id = _stable_id("research-doc", request.symbol, document_hash[:16])
        document = ResearchDocument(
            document_id=document_id,
            symbol=_normalize_symbol(request.symbol),
            title=request.title.strip(),
            source_type=request.source_type,
            company_name=request.company_name.strip() if request.company_name else None,
            published_at=request.published_at,
            collected_at=datetime.now(UTC),
            local_path=str(path),
            language=request.language,
            reliability=request.reliability,
            document_hash=document_hash,
        )
        return self.store.upsert_document(document, stripped_text)

    def register_text_document(
        self,
        *,
        symbol: str,
        title: str,
        text: str,
        source_type: ResearchSourceType,
        source_url: str,
        provider: str,
        company_name: str | None = None,
        published_at: date | None = None,
        language: ResearchLanguage = "unknown",
        reliability: Decimal = Decimal("0.70"),
    ) -> ResearchDocument:
        """Register fetched text in memory without creating a local source file."""

        stripped_text = text.strip()
        if not stripped_text:
            raise ResearchDocumentError(
                "Research document text is empty.",
                details={"symbol": symbol, "title": title, "provider": provider},
            )
        document_hash = hashlib.sha256(stripped_text.encode("utf-8")).hexdigest()
        document_id = _stable_id("research-doc", symbol, provider, source_url, document_hash[:16])
        document = ResearchDocument(
            document_id=document_id,
            symbol=_normalize_symbol(symbol),
            title=title.strip(),
            source_type=source_type,
            company_name=company_name.strip() if company_name else None,
            published_at=published_at,
            collected_at=datetime.now(UTC),
            local_path=(
                f"external://{_safe_cache_fragment(provider)}/"
                f"{_safe_cache_fragment(_normalize_symbol(symbol))}/"
                f"{document_hash[:16]}"
            ),
            language=language,
            provider=provider.strip() or "external",
            reliability=reliability,
            document_hash=document_hash,
        )
        return self.store.upsert_document(document, stripped_text)

    def list_documents(self, symbol: str | None = None) -> list[ResearchDocument]:
        return self.store.list_documents(symbol)


class ResearchIndexService:
    """Build deterministic text chunks from registered local documents."""

    def __init__(
        self,
        store: ResearchInMemoryStore,
        *,
        max_chars: int = DEFAULT_MAX_CHARS,
        overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    ) -> None:
        if overlap_chars >= max_chars:
            raise ValidationAppError("Research chunk overlap must be smaller than max chars.")
        self.store = store
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def build_chunks(self, document_id: str) -> list[ResearchChunk]:
        document = self.store.documents.get(document_id)
        text = self.store.raw_text_by_document_id.get(document_id)
        if document is None or text is None:
            raise ResearchParseError(
                "Research document is not registered.",
                details={"document_id": document_id},
            )
        chunks = _chunk_document_text(document, text, max_chars=self.max_chars)
        self.store.replace_chunks(document_id, chunks)
        return chunks

    def rebuild_index(self, symbol: str | None = None) -> ResearchIndexSummary:
        documents = self.store.list_documents(symbol)
        warnings: list[str] = []
        chunk_count = 0
        for document in documents:
            try:
                chunk_count += len(self.build_chunks(document.document_id))
            except AppError as exc:
                warnings.append(f"{document.document_id}: {exc.message}")
        return ResearchIndexSummary(
            document_count=len(documents),
            chunk_count=chunk_count,
            symbols=sorted({_normalize_symbol(document.symbol) for document in documents}),
            warnings=warnings,
        )


class ResearchQueryExpansionService:
    """Expand research queries with deterministic topic dictionaries."""

    def __init__(
        self,
        terms_by_category: Mapping[ResearchTopicCategory, Sequence[str]] | None = None,
    ) -> None:
        configured = terms_by_category or DEFAULT_RESEARCH_QUERY_TERMS
        self.terms_by_category = {
            category: tuple(_normalize_query_terms(terms)) for category, terms in configured.items()
        }

    @classmethod
    def from_yaml(cls, path: Path) -> ResearchQueryExpansionService:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        if not isinstance(data, dict):
            raise ResearchSearchError(
                "Research query expansion config must be a mapping.",
                details={"path": str(path)},
            )
        terms_by_category: dict[ResearchTopicCategory, list[str]] = {}
        for key, value in data.items():
            if key not in DEFAULT_RESEARCH_QUERY_TERMS:
                raise ResearchSearchError(
                    "Research query expansion config has unknown category.",
                    details={"path": str(path), "category": str(key)},
                )
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ResearchSearchError(
                    "Research query expansion terms must be a list of strings.",
                    details={"path": str(path), "category": str(key)},
                )
            terms_by_category[cast(ResearchTopicCategory, key)] = value
        return cls(terms_by_category)

    def expand_query(
        self,
        query: str,
        *,
        category: ResearchTopicCategory | None = None,
    ) -> ResearchQueryExpansionResult:
        terms = list(_query_terms(query))
        if category is not None:
            terms.extend(self.terms_by_category.get(category, ()))
        return ResearchQueryExpansionResult(
            query=query,
            category=category,
            expanded_terms=_normalize_query_terms(terms),
        )


class ResearchEvidenceReranker:
    """Deterministically rerank evidence while preserving ResearchEvidence output."""

    def rerank(
        self,
        evidence: list[ResearchEvidence],
        *,
        as_of: date | None = None,
    ) -> list[ResearchEvidence]:
        effective_as_of = as_of or date.today()
        deduped = _dedupe_evidence(evidence)
        return sorted(
            deduped,
            key=lambda row: (
                -_evidence_rerank_score(row, as_of=effective_as_of),
                -row.relevance_score,
                -row.reliability,
                -_source_type_priority(row.source_type),
                -(row.published_at or date.min).toordinal(),
                row.document_id,
                row.chunk_id,
            ),
        )


class ResearchHybridScorer:
    """Score optional hybrid retrieval candidates without changing keyword retrieval."""

    def __init__(self, weights: ResearchHybridScoreWeights | None = None) -> None:
        self.weights = weights or ResearchHybridScoreWeights()

    def score(
        self,
        candidate: ResearchRetrievalCandidate,
        *,
        as_of: date | None = None,
    ) -> ResearchRetrievalCandidate:
        effective_as_of = as_of or date.today()
        freshness_score = candidate.freshness_score or _freshness_factor(
            candidate.published_at,
            as_of=effective_as_of,
        )
        source_type_score = Decimal(str(_source_type_priority(candidate.source_type)))
        score = (
            ((candidate.keyword_score or Decimal("0")) * self.weights.keyword_weight)
            + ((candidate.vector_score or Decimal("0")) * self.weights.vector_weight)
            + (freshness_score * self.weights.freshness_weight)
            + (candidate.reliability * self.weights.reliability_weight)
            + (source_type_score * self.weights.source_type_weight)
        )
        return candidate.model_copy(
            update={
                "freshness_score": freshness_score,
                "final_relevance_score": min(Decimal("1"), score).quantize(Decimal("0.0001")),
                "retrieval_backend": "hybrid",
            }
        )


class ResearchDisabledVectorStore:
    """Explicit disabled vector store used as the default optional-vector fallback."""

    disabled_warning = (
        "Vector retrieval is disabled; keyword retrieval remains the deterministic default."
    )

    def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]:
        return []

    def retrieval_quality(
        self,
        request: ResearchSearchRequest,
        *,
        expanded_terms: Sequence[str] | None = None,
    ) -> ResearchRetrievalQuality:
        query = request.query or request.query_category or "vector search"
        return ResearchRetrievalQuality(
            backend="vector",
            query=query,
            expanded_terms=_normalize_query_terms(expanded_terms or request.expanded_terms),
            candidate_count=0,
            evidence_count=0,
            warnings=[self.disabled_warning],
        )


class ResearchInMemoryVectorStore:
    """Small deterministic local vector store for optional hybrid retrieval tests."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[ResearchRetrievalCandidate, ResearchEmbedding]] = {}

    def upsert(
        self,
        candidate: ResearchRetrievalCandidate,
        embedding: ResearchEmbedding,
    ) -> None:
        if candidate.chunk_id != embedding.chunk_id:
            raise ResearchSearchError(
                message="Research vector candidate and embedding chunk_id do not match.",
                details={
                    "candidate_chunk_id": candidate.chunk_id,
                    "embedding_chunk_id": embedding.chunk_id,
                },
            )
        self._entries[candidate.chunk_id] = (candidate, embedding)

    def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]:
        return _search_vector_entries(self._entries, request)

    def retrieval_quality(
        self,
        request: ResearchSearchRequest,
        *,
        expanded_terms: Sequence[str] | None = None,
    ) -> ResearchRetrievalQuality:
        candidates = self.search(request)
        return _build_vector_retrieval_quality(
            request,
            candidate_count=len(candidates),
            entry_count=len(self._entries),
            expanded_terms=expanded_terms,
        )


class ResearchFileVectorStore:
    """JSONL-backed local vector cache for optional deterministic vector retrieval."""

    def __init__(self, cache_path: str | Path) -> None:
        self.cache_path = Path(cache_path)
        self._entries = self._load_entries()

    def upsert(
        self,
        candidate: ResearchRetrievalCandidate,
        embedding: ResearchEmbedding,
    ) -> None:
        if candidate.chunk_id != embedding.chunk_id:
            raise ResearchSearchError(
                message="Research vector candidate and embedding chunk_id do not match.",
                details={
                    "candidate_chunk_id": candidate.chunk_id,
                    "embedding_chunk_id": embedding.chunk_id,
                    "cache_path": str(self.cache_path),
                },
            )
        self._entries[candidate.chunk_id] = (candidate, embedding)
        self._write_entries()

    def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]:
        return _search_vector_entries(self._entries, request)

    def retrieval_quality(
        self,
        request: ResearchSearchRequest,
        *,
        expanded_terms: Sequence[str] | None = None,
    ) -> ResearchRetrievalQuality:
        candidates = self.search(request)
        return _build_vector_retrieval_quality(
            request,
            candidate_count=len(candidates),
            entry_count=len(self._entries),
            expanded_terms=expanded_terms,
            empty_cache_warning="Vector cache is empty; no file-backed candidates are available.",
        )

    def _load_entries(
        self,
    ) -> dict[str, tuple[ResearchRetrievalCandidate, ResearchEmbedding]]:
        if not self.cache_path.exists():
            return {}
        entries: dict[str, tuple[ResearchRetrievalCandidate, ResearchEmbedding]] = {}
        try:
            for line_number, line in enumerate(
                self.cache_path.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not line.strip():
                    continue
                payload: Any = json.loads(line)
                if not isinstance(payload, Mapping):
                    raise ValueError(f"cache line {line_number} is not a JSON object")
                candidate = ResearchRetrievalCandidate.model_validate(payload.get("candidate"))
                embedding = ResearchEmbedding.model_validate(payload.get("embedding"))
                if candidate.chunk_id != embedding.chunk_id:
                    raise ValueError(
                        "candidate and embedding chunk_id mismatch "
                        f"on line {line_number}: "
                        f"{candidate.chunk_id} != {embedding.chunk_id}"
                    )
                entries[candidate.chunk_id] = (candidate, embedding)
        except (OSError, TypeError, ValueError, ValidationError) as exc:
            raise ResearchSearchError(
                message="Research vector cache could not be loaded.",
                details={"cache_path": str(self.cache_path), "error": str(exc)},
            ) from exc
        return entries

    def _write_entries(self) -> None:
        rows = [
            json.dumps(
                {
                    "candidate": candidate.model_dump(mode="json"),
                    "embedding": embedding.model_dump(mode="json"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            for _, (candidate, embedding) in sorted(self._entries.items())
        ]
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.cache_path.with_name(f".{self.cache_path.name}.tmp")
            tmp_path.write_text(
                "\n".join(rows) + ("\n" if rows else ""),
                encoding="utf-8",
            )
            tmp_path.replace(self.cache_path)
        except OSError as exc:
            raise ResearchSearchError(
                message="Research vector cache could not be written.",
                details={"cache_path": str(self.cache_path), "error": str(exc)},
            ) from exc


class ResearchVectorStore(Protocol):
    """Protocol for optional local vector stores."""

    def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]: ...

    def retrieval_quality(
        self,
        request: ResearchSearchRequest,
        *,
        expanded_terms: Sequence[str] | None = None,
    ) -> ResearchRetrievalQuality: ...


class ResearchWritableVectorStore(ResearchVectorStore, Protocol):
    """Protocol for optional vector stores that accept locally generated embeddings."""

    def upsert(
        self,
        candidate: ResearchRetrievalCandidate,
        embedding: ResearchEmbedding,
    ) -> None: ...


class ResearchEmbeddingService:
    """Generate deterministic local embeddings for optional vector retrieval."""

    def __init__(
        self,
        *,
        embedding_model: str = DEFAULT_RESEARCH_EMBEDDING_MODEL,
        dimensions: int = DEFAULT_RESEARCH_EMBEDDING_DIMENSIONS,
        created_at: datetime | None = None,
    ) -> None:
        if dimensions < 2:
            raise ResearchSearchError(
                message="Research embedding dimensions must be at least 2.",
                details={"dimensions": dimensions},
            )
        self.embedding_model = embedding_model
        self.dimensions = dimensions
        self.created_at = created_at

    def embed_chunk(self, chunk: ResearchChunk) -> ResearchEmbedding:
        return ResearchEmbedding(
            chunk_id=chunk.chunk_id,
            symbol=_normalize_symbol(chunk.symbol),
            embedding_model=self.embedding_model,
            vector=_local_embedding_vector(chunk.text, dimensions=self.dimensions),
            created_at=self.created_at or datetime.now(UTC),
            text_hash=_text_hash(chunk.text),
        )

    def build_query_vector(
        self,
        query: str,
        *,
        expanded_terms: Sequence[str] | None = None,
    ) -> list[float]:
        parts = [query, *list(expanded_terms or [])]
        return _local_embedding_vector(" ".join(parts), dimensions=self.dimensions)

    def candidate_from_chunk(
        self,
        chunk: ResearchChunk,
        *,
        keyword_score: Decimal | None = None,
    ) -> ResearchRetrievalCandidate:
        return ResearchRetrievalCandidate(
            symbol=_normalize_symbol(chunk.symbol),
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            title=chunk.title,
            source_type=chunk.source_type,
            published_at=chunk.published_at,
            section_title=chunk.section_title,
            excerpt=_excerpt(chunk.text),
            keyword_score=keyword_score,
            reliability=_chunk_reliability(chunk),
            final_relevance_score=keyword_score or Decimal("0"),
            retrieval_backend="vector",
        )

    def upsert_chunk(
        self,
        chunk: ResearchChunk,
        vector_store: ResearchWritableVectorStore,
        *,
        keyword_score: Decimal | None = None,
    ) -> ResearchEmbedding:
        candidate = self.candidate_from_chunk(chunk, keyword_score=keyword_score)
        embedding = self.embed_chunk(chunk)
        vector_store.upsert(candidate, embedding)
        return embedding

    def upsert_chunks(
        self,
        chunks: Sequence[ResearchChunk],
        vector_store: ResearchWritableVectorStore,
    ) -> list[ResearchEmbedding]:
        return [self.upsert_chunk(chunk, vector_store) for chunk in chunks]


class ResearchVectorIndexService:
    """Build an optional local vector index from already chunked research documents."""

    def __init__(
        self,
        store: ResearchInMemoryStore,
        vector_store: ResearchWritableVectorStore,
        embedding_service: ResearchEmbeddingService | None = None,
    ) -> None:
        self.store = store
        self.vector_store = vector_store
        self.embedding_service = embedding_service or ResearchEmbeddingService()

    def rebuild_index(self, symbol: str | None = None) -> ResearchVectorIndexSummary:
        chunks = self.store.all_chunks(symbol)
        warnings: list[str] = []
        embedded_count = 0
        for chunk in chunks:
            try:
                self.embedding_service.upsert_chunk(chunk, self.vector_store)
                embedded_count += 1
            except AppError as exc:
                warnings.append(f"{chunk.chunk_id}: {exc.message}")
        if not chunks:
            warnings.append("No research chunks available; rebuild the text index first.")
        return ResearchVectorIndexSummary(
            embedding_model=self.embedding_service.embedding_model,
            dimensions=self.embedding_service.dimensions,
            chunk_count=len(chunks),
            embedded_count=embedded_count,
            symbols=sorted({_normalize_symbol(chunk.symbol) for chunk in chunks}),
            warnings=warnings,
        )


class HybridResearchRetrievalService:
    """Optional hybrid retrieval wrapper with deterministic keyword fallback."""

    def __init__(
        self,
        keyword_retrieval: ResearchRetrievalService,
        vector_store: ResearchVectorStore | None = None,
        scorer: ResearchHybridScorer | None = None,
        reranker: ResearchEvidenceReranker | None = None,
    ) -> None:
        self.keyword_retrieval = keyword_retrieval
        self.vector_store = vector_store or ResearchDisabledVectorStore()
        self.scorer = scorer or ResearchHybridScorer()
        self.reranker = reranker or ResearchEvidenceReranker()

    def search(self, request: ResearchSearchRequest) -> list[ResearchEvidence]:
        vector_candidates = self.vector_store.search(request)
        if not vector_candidates:
            return self.keyword_retrieval.search(request)

        as_of = request.as_of or date.today()
        scored = [self.scorer.score(candidate, as_of=as_of) for candidate in vector_candidates]
        evidence = [_evidence_from_candidate(candidate) for candidate in scored]
        return self.reranker.rerank(evidence, as_of=as_of)[: request.top_k]

    def retrieval_quality(self, request: ResearchSearchRequest) -> ResearchRetrievalQuality:
        vector_quality = self.vector_store.retrieval_quality(request)
        if vector_quality.candidate_count > 0:
            return vector_quality.model_copy(update={"backend": "hybrid"})
        keyword_evidence = self.keyword_retrieval.search(request)
        warnings = list(vector_quality.warnings)
        warnings.append("Hybrid retrieval fell back to keyword retrieval.")
        return ResearchRetrievalQuality(
            backend="hybrid",
            query=vector_quality.query,
            expanded_terms=vector_quality.expanded_terms,
            candidate_count=len(keyword_evidence),
            evidence_count=len(keyword_evidence),
            warnings=warnings,
        )


class ResearchRetrievalService:
    """Retrieve local research evidence with deterministic keyword scoring."""

    def __init__(
        self,
        store: ResearchInMemoryStore,
        reranker: ResearchEvidenceReranker | None = None,
    ) -> None:
        self.store = store
        self.reranker = reranker or ResearchEvidenceReranker()

    def search(self, request: ResearchSearchRequest) -> list[ResearchEvidence]:
        chunks = self.store.all_chunks(request.symbol)
        if request.source_types:
            source_types = set(request.source_types)
            chunks = [chunk for chunk in chunks if chunk.source_type in source_types]
        if not chunks:
            return []

        query_terms = _expanded_query_terms(request)
        as_of = request.as_of or date.today()
        scored = []
        for chunk in chunks:
            score = _chunk_relevance_score(chunk, query_terms, as_of=as_of)
            if score > Decimal("0"):
                scored.append((score, chunk))
        evidence = [_evidence_from_chunk(chunk, relevance_score=score) for score, chunk in scored]
        return self.reranker.rerank(evidence, as_of=as_of)[: request.top_k]


class ResearchGroundedAnswerService:
    """Build safe template answers without external LLM calls."""

    def generate(
        self,
        *,
        symbol: str,
        claims: list[ResearchExtractedClaim],
        data_quality: ResearchDataQuality,
    ) -> ResearchGroundedAnswer:
        normalized_symbol = _normalize_symbol(symbol)
        supported_claims = [
            claim
            for claim in claims
            if claim.category != "confirmation_gap" and claim.supporting_evidence
        ]
        gap_claims = [
            claim
            for claim in claims
            if claim.category == "confirmation_gap" or claim.missing_information
        ]
        referenced_evidence = _dedupe_evidence(
            [evidence for claim in supported_claims for evidence in claim.supporting_evidence]
        )

        sentences: list[str] = []
        if supported_claims:
            labels = _category_labels([claim.category for claim in supported_claims])
            sentences.append(
                f"登録済み資料から確認できる範囲では、{labels}に関する根拠が確認できます。"
            )
            sentences.append(_evidence_reference_sentence(referenced_evidence))
        else:
            sentences.append(
                "登録済み資料から確認できる範囲では、投資判断に関係する十分な根拠はまだ確認できません。"
            )

        if gap_claims:
            missing = _category_labels(
                [claim.category for claim in gap_claims if claim.category != "confirmation_gap"]
            )
            if missing:
                sentences.append(f"一方で、{missing}は根拠が不足しており、追加確認が必要です。")
            else:
                sentences.append("一方で、資料不足や根拠不足の注意点があり、追加確認が必要です。")

        sentences.append("これは売買推奨ではなく、登録資料に基づく判断材料の整理です。")
        warnings = list(data_quality.warnings)
        warnings.extend(
            missing
            for claim in gap_claims
            for missing in claim.missing_information
            if missing not in warnings
        )
        return ResearchGroundedAnswer(
            symbol=normalized_symbol,
            answer="".join(sentences),
            referenced_evidence=referenced_evidence,
            claim_count=len(supported_claims),
            evidence_count=len(referenced_evidence),
            warnings=warnings,
        )


class ResearchAnalysisService:
    """Create a deterministic evidence-backed company research summary."""

    def __init__(
        self,
        ingestion: ResearchIngestionService,
        retrieval: ResearchRetrievalService,
        query_expansion: ResearchQueryExpansionService | None = None,
        grounded_answer: ResearchGroundedAnswerService | None = None,
        reranker: ResearchEvidenceReranker | None = None,
    ) -> None:
        self.ingestion = ingestion
        self.retrieval = retrieval
        self.query_expansion = query_expansion or ResearchQueryExpansionService()
        self.grounded_answer = grounded_answer or ResearchGroundedAnswerService()
        self.reranker = reranker or ResearchEvidenceReranker()

    def analyze_company(self, request: CompanyResearchRequest) -> CompanyResearchReport:
        as_of = request.as_of or date.today()
        topics = [
            (
                "growth",
                "成長材料",
                "growth strategy revenue sales market expansion new business",
            ),
            (
                "shareholder_return",
                "株主還元",
                "dividend payout buyback shareholder return",
            ),
            (
                "financial_safety",
                "財務安全性",
                "cash debt equity capital liquidity balance sheet",
            ),
            (
                "business_risk",
                "事業リスク",
                "risk competition regulation lawsuit supply demand",
            ),
        ]
        points: list[ResearchSummaryPoint] = []
        extracted_claims: list[ResearchExtractedClaim] = []
        all_evidence: list[ResearchEvidence] = []
        expanded_terms_by_topic: list[str] = []
        topic_queries: list[str] = []
        for category, label, query in topics:
            topic_category = cast(ResearchTopicCategory, category)
            expanded = self.query_expansion.expand_query(query, category=topic_category)
            expanded_terms_by_topic.extend(expanded.expanded_terms)
            topic_queries.append(f"{topic_category}:{query}")
            evidence = self.retrieval.search(
                ResearchSearchRequest(
                    symbol=request.symbol,
                    query=query,
                    top_k=request.top_k_per_topic,
                    as_of=as_of,
                    query_category=topic_category,
                    expanded_terms=expanded.expanded_terms,
                )
            )
            all_evidence.extend(evidence)
            extracted_claims.append(
                _extracted_claim(
                    symbol=request.symbol,
                    category=topic_category,
                    label=label,
                    evidence=evidence,
                )
            )
            points.append(
                ResearchSummaryPoint(
                    category=topic_category,
                    label=label,
                    summary=_topic_summary(label, evidence),
                    evidence=evidence,
                )
            )

        unique_evidence = self.reranker.rerank(all_evidence, as_of=as_of)
        documents = self.ingestion.list_documents(request.symbol)
        data_quality = _research_data_quality(documents, unique_evidence, as_of=as_of)
        retrieval_quality = _retrieval_quality(
            queries=topic_queries,
            expanded_terms=expanded_terms_by_topic,
            candidate_count=len(all_evidence),
            evidence_count=len(unique_evidence),
            data_quality=data_quality,
        )
        if data_quality.status != "OK":
            extracted_claims.append(
                ResearchExtractedClaim(
                    symbol=_normalize_symbol(request.symbol),
                    category="confirmation_gap",
                    claim="Research資料の確認不足があります。",
                    summary="登録資料、根拠数、鮮度、信頼度のいずれかに注意が必要です。",
                    supporting_evidence=[],
                    confidence=Decimal("0"),
                    missing_information=data_quality.warnings,
                    caution_note="根拠不足は投資対象の良し悪しではなく、追加確認が必要な状態として扱います。",
                )
            )
            points.append(
                ResearchSummaryPoint(
                    category="confirmation_gap",
                    label="確認不足",
                    summary="登録資料または検索できた根拠が少ないため、資料面の確認は控えめに扱います。",
                    evidence=[],
                )
            )

        grounded_answer = self.grounded_answer.generate(
            symbol=request.symbol,
            claims=extracted_claims,
            data_quality=data_quality,
        )
        return CompanyResearchReport(
            symbol=_normalize_symbol(request.symbol),
            as_of=as_of,
            summary=_company_summary(unique_evidence, data_quality),
            points=points,
            extracted_claims=extracted_claims,
            grounded_answer=grounded_answer,
            evidence=unique_evidence,
            data_quality=data_quality,
            retrieval_quality=retrieval_quality,
        )


class ResearchScoreService:
    """Score Research RAG evidence coverage without changing Investment Score."""

    def score_report(self, report: CompanyResearchReport) -> ResearchScore:
        as_of = report.as_of
        growth_score = _score_report_category(report, "growth", as_of=as_of)
        shareholder_return_score = _score_report_category(report, "shareholder_return", as_of=as_of)
        financial_safety_score = _score_report_category(report, "financial_safety", as_of=as_of)
        business_risk_score = _score_report_category(report, "business_risk", as_of=as_of)
        profitability_score = _score_research_terms(
            report.evidence,
            (
                "profit",
                "profitability",
                "margin",
                "operating income",
                "roe",
                "価格転嫁",
                "利益率",
                "営業利益",
                "収益性",
            ),
            as_of=as_of,
        )
        disclosure_quality_score = _score_disclosure_quality(report, as_of=as_of)
        freshness_score = _score_research_freshness(report, as_of=as_of)
        component_scores = [
            growth_score,
            profitability_score,
            shareholder_return_score,
            financial_safety_score,
            business_risk_score,
            disclosure_quality_score,
            freshness_score,
        ]
        warnings = _research_score_warnings(report, component_scores)
        confidence = _research_score_confidence(report)
        total_score = _score_100(
            sum(component_scores, Decimal("0")) / Decimal(len(component_scores))
        )
        return ResearchScore(
            symbol=report.symbol,
            as_of=as_of,
            total_score=total_score,
            growth_score=growth_score,
            profitability_score=profitability_score,
            shareholder_return_score=shareholder_return_score,
            financial_safety_score=financial_safety_score,
            business_risk_score=business_risk_score,
            disclosure_quality_score=disclosure_quality_score,
            freshness_score=freshness_score,
            evidence_count=len(report.evidence),
            confidence=confidence,
            supporting_evidence=report.evidence,
            warnings=warnings,
            summary=_research_score_summary(
                report,
                total_score=total_score,
                confidence=confidence,
            ),
        )


class ResearchBriefBuilder:
    """Build a readable local Research memo without external LLM calls."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
    ) -> ResearchBrief:
        metrics = _research_brief_metrics(report.evidence)
        missing_metrics = _research_brief_missing_metric_labels(metrics)
        positive_materials = _research_brief_positive_materials(report, news_report)
        caution_materials = _research_brief_caution_materials(report, news_report)
        positive_candidates = [material.summary for material in positive_materials]
        caution_candidates = [material.summary for material in caution_materials]
        confirmation_gaps = _research_brief_confirmation_gaps(
            report,
            missing_metrics,
            news_report=news_report,
        )
        next_actions = _research_brief_next_actions(
            report,
            missing_metrics,
            external_research_result=external_research_result,
        )
        source_cards = _research_brief_source_cards(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        fact_summary = _research_fact_summary(
            report,
            metrics=metrics,
            positive_materials=positive_materials,
            caution_materials=caution_materials,
            missing_metrics=missing_metrics,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        return ResearchBrief(
            symbol=report.symbol,
            as_of=report.as_of,
            memo=_research_brief_memo(
                report,
                metrics,
                source_cards,
                fact_summary=fact_summary,
            ),
            metrics=metrics,
            missing_metrics=missing_metrics,
            business_overview=_research_brief_business_overview(
                report,
                fact_summary=fact_summary,
            ),
            positive_candidates=positive_candidates,
            caution_candidates=caution_candidates,
            positive_materials=positive_materials,
            caution_materials=caution_materials,
            confirmation_gaps=confirmation_gaps,
            next_actions=next_actions,
            source_cards=source_cards,
            fact_summary=fact_summary,
        )


class SecurityResearchTypeDetector:
    """Detect the research display type from provider metadata and symbol shape."""

    def detect(
        self,
        report: CompanyResearchReport,
        *,
        external_research_result: ExternalResearchFetchResult | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> SecurityResearchType:
        symbol = report.symbol.strip()
        text = _security_research_detection_text(
            report,
            external_research_result=external_research_result,
            metadata=metadata,
        )
        quote_type = _security_research_metadata_value(text, "quoteType", "Quote Type")
        explicit_type = _security_research_metadata_value(
            text,
            "security_type",
            "Security Type",
            "product_type",
            "Product Type",
            "asset_category",
            "Asset Category",
        )
        combined_type = f"{quote_type} {explicit_type}".lower()
        if any(keyword in combined_type for keyword in ("etf", "exchange traded fund")):
            return "etf"
        if any(keyword in combined_type for keyword in ("fund", "mutual fund", "investment trust")):
            return "fund"

        exchange = _security_research_metadata_value(
            text, "exchange", "Exchange", "market", "Market"
        )
        if "equity" in combined_type or not combined_type.strip():
            if symbol.upper().endswith(".T") or _security_research_exchange_is_domestic(exchange):
                return "domestic_stock"
            if _security_research_exchange_is_foreign(exchange):
                return "foreign_stock"
            if re.fullmatch(r"[A-Z]{1,5}(?:[-.][A-Z])?", symbol.upper()):
                return "foreign_stock"
        return "unknown"


class ETFResearchSummaryBuilder:
    """Build an ETF / fund-understanding report without treating it as a company."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
    ) -> ETFResearchSummary:
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        normalized_evidence = _company_research_normalized_evidence(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        text = _etf_research_source_text(report, external_research_result=external_research_result)
        fund_name = (
            _security_research_metadata_value(
                text,
                "longName",
                "Company Name",
                "Fund Name",
                "Name",
                "shortName",
            )
            or report.symbol
        )
        provider_name = _security_research_metadata_value(
            text,
            "fundFamily",
            "Fund Family",
            "provider",
            "Provider",
            "issuer",
            "Issuer",
        )
        investment_target = _etf_research_investment_target(text)
        asset_class = _etf_research_asset_class(text)
        region_focus = _etf_research_region_focus(text)
        sector_focus = _etf_research_sector_focus(text)
        top_holdings = _etf_research_top_holdings(text)
        benchmark_index = _etf_research_benchmark_index(text)
        expense_ratio = _etf_research_metric_value(
            "expense_ratio",
            text,
            (
                r"annual report expense ratio",
                r"annualReportExpenseRatio",
                r"expense ratio",
                r"expenseRatio",
                r"net expense ratio",
                r"経費率",
            ),
        )
        dividend_yield = _etf_research_metric_value(
            "dividend_yield",
            text,
            (
                r"trailing annual dividend yield",
                r"trailingAnnualDividendYield",
                r"dividend yield",
                r"dividendYield",
                r"\byield\b",
                r"分配金利回り",
                r"配当利回り",
            ),
        )
        aum = _etf_research_metric_value(
            "aum",
            text,
            (
                r"net assets",
                r"netAssets",
                r"total assets",
                r"totalAssets",
                r"AUM",
                r"純資産総額",
            ),
        )
        nav = _etf_research_metric_value(
            "nav",
            text,
            (
                r"NAV",
                r"nav price",
                r"navPrice",
                r"regular market price",
                r"regularMarketPrice",
                r"market price",
                r"基準価額",
            ),
        )
        per = _etf_research_metric_value(
            "per",
            text,
            (r"PER", r"trailing PE", r"forward PE", r"trailingPE", r"forwardPE"),
        )
        pbr = _etf_research_metric_value(
            "pbr",
            text,
            (r"PBR", r"price[- ]to[- ]book", r"priceToBook"),
        )
        if asset_class and asset_class != "株式":
            per = None
            pbr = None
        source_titles = _unique_text(
            [
                *[row.title for row in report.evidence if row.source_type == "provider_profile"],
                *[
                    entry.title
                    for entry in (
                        external_research_result.entries if external_research_result else []
                    )
                    if entry.source_type in {"provider_profile", "news", "tdnet"}
                ],
            ]
        )[:5]
        missing_items = _etf_research_missing_items(
            expense_ratio=expense_ratio,
            dividend_yield=dividend_yield,
            aum=aum,
            nav=nav,
            top_holdings=top_holdings,
            benchmark_index=benchmark_index,
        )
        news_items = _company_research_news_items(
            prepared_brief,
            normalized_evidence=normalized_evidence,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        return ETFResearchSummary(
            symbol=report.symbol,
            fund_name=fund_name,
            provider_name=provider_name or None,
            fund_overview=_etf_research_fund_overview(
                fund_name=fund_name,
                investment_target=investment_target,
                asset_class=asset_class,
                region_focus=region_focus,
                benchmark_index=benchmark_index,
            ),
            investment_target=investment_target,
            asset_class=asset_class,
            region_focus=region_focus,
            sector_focus=sector_focus,
            expense_ratio=expense_ratio,
            dividend_yield=dividend_yield,
            aum=aum,
            nav=nav,
            per=per,
            pbr=pbr,
            top_holdings=top_holdings,
            benchmark_index=benchmark_index,
            risk_notes=_etf_research_risk_notes(
                top_holdings=top_holdings,
                benchmark_index=benchmark_index,
                region_focus=region_focus,
                asset_class=asset_class,
                expense_ratio=expense_ratio,
                aum=aum,
                nav=nav,
            ),
            news_items=news_items,
            source_titles=source_titles,
            missing_items=missing_items,
            evidence_level=_company_research_evidence_level_from_source_types(
                [row.source_type for row in report.evidence]
            ),
        )


class CompanyResearchSummaryBuilder:
    """Build a company-understanding report from existing Research RAG outputs."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
        insight: InvestmentInsight | None = None,
    ) -> CompanyResearchSummary:
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        prepared_insight = insight or InvestmentInsightBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
            brief=prepared_brief,
        )
        normalized_evidence = _company_research_normalized_evidence(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        overview = _company_research_overview_summary(
            report,
            prepared_brief,
            normalized_evidence=normalized_evidence,
            news_report=news_report,
        )
        quantitative = _company_research_quantitative_summary(
            prepared_brief,
            normalized_evidence=normalized_evidence,
        )
        ir_items = _company_research_ir_items(
            report,
            prepared_brief,
            normalized_evidence=normalized_evidence,
            external_research_result=external_research_result,
        )
        news_items = _company_research_news_items(
            prepared_brief,
            normalized_evidence=normalized_evidence,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        ai_notes = _company_research_ai_reading_notes(
            prepared_brief,
            prepared_insight,
            quantitative=quantitative,
            ir_items=ir_items,
            news_items=news_items,
        )
        return CompanyResearchSummary(
            symbol=report.symbol,
            overview=overview,
            quantitative=quantitative,
            ir_items=ir_items,
            news_items=news_items,
            ai_reading_notes=ai_notes,
            missing_critical_items=_company_research_missing_critical_items(
                overview,
                quantitative,
                ir_items,
                news_items,
            ),
            normalized_evidence=normalized_evidence,
        )


class InvestmentInsightBuilder:
    """Build a source-backed investment review memo without external LLM calls."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
    ) -> InvestmentInsight:
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        positive_points = _investment_insight_positive_points(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        negative_points = _investment_insight_negative_points(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        neutral_points = _investment_insight_neutral_points(
            report,
            prepared_brief,
            external_research_result=external_research_result,
        )
        confirmation_gaps = _investment_insight_confirmation_gaps(
            report,
            prepared_brief,
            news_report=news_report,
        )
        action_hints = _investment_insight_action_hints(
            report,
            prepared_brief,
            positive_points=positive_points,
            negative_points=negative_points,
            confirmation_gaps=confirmation_gaps,
            news_report=news_report,
        )
        confidence = _investment_insight_confidence(
            report,
            prepared_brief,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        status_label = _investment_insight_status_label(
            report,
            prepared_brief,
            positive_points=positive_points,
            negative_points=negative_points,
            news_report=news_report,
        )
        confidence_label = _investment_insight_confidence_label(status_label, confidence)
        primary_action_label = _investment_insight_primary_action_label(status_label)
        display_positive_points = positive_points[:3]
        display_negative_points = negative_points[:3]
        display_confirmation_gaps = confirmation_gaps[:3]
        return InvestmentInsight(
            symbol=report.symbol,
            as_of=report.as_of,
            headline=_investment_insight_headline(
                positive_points=positive_points,
                negative_points=negative_points,
                neutral_points=neutral_points,
                confirmation_gaps=confirmation_gaps,
            ),
            short_summary=_investment_insight_short_summary(
                report,
                prepared_brief,
                positive_points=positive_points,
                negative_points=negative_points,
                neutral_points=neutral_points,
                confirmation_gaps=confirmation_gaps,
                action_hints=action_hints,
                confidence=confidence,
                status_label=status_label,
            ),
            status_label=status_label,
            confidence_label=confidence_label,
            primary_action_label=primary_action_label,
            positive_points=display_positive_points,
            negative_points=display_negative_points,
            neutral_points=neutral_points,
            confirmation_gaps=display_confirmation_gaps,
            action_hints=action_hints,
            confidence=confidence,
        )


class InvestmentQuestionSummaryBuilder:
    """Build fixed investor questions from source-backed Research facts."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
        insight: InvestmentInsight | None = None,
    ) -> InvestmentQuestionSummary:
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        prepared_insight = insight or InvestmentInsightBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
            brief=prepared_brief,
        )
        answers = [
            _investment_question_answer(
                category,
                report,
                prepared_brief,
                prepared_insight,
                news_report=news_report,
                external_research_result=external_research_result,
            )
            for category, _ in _INVESTMENT_QUESTION_SPECS
        ]
        top_takeaway = next(
            (
                answer.answer
                for answer in answers
                if answer.category == "key_takeaway" and answer.answer.strip()
            ),
            "",
        )
        return InvestmentQuestionSummary(
            symbol=report.symbol,
            answers=answers,
            top_takeaway=top_takeaway,
            missing_critical_items=_investment_question_missing_critical_items(
                prepared_brief,
                answers,
            ),
        )


class ResearchPageViewModelBuilder:
    """Build the top-level Research page model for company, foreign stock, or ETF views."""

    def build(
        self,
        report: CompanyResearchReport,
        *,
        news_report: StockNewsReport | None = None,
        external_research_result: ExternalResearchFetchResult | None = None,
        brief: ResearchBrief | None = None,
        insight: InvestmentInsight | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ResearchPageViewModel:
        prepared_brief = brief or ResearchBriefBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        )
        prepared_insight = insight or InvestmentInsightBuilder().build(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
            brief=prepared_brief,
        )
        security_type = SecurityResearchTypeDetector().detect(
            report,
            external_research_result=external_research_result,
            metadata=metadata,
        )
        if security_type in {"etf", "fund"}:
            return ResearchPageViewModel(
                symbol=report.symbol,
                security_type=security_type,
                etf_summary=ETFResearchSummaryBuilder().build(
                    report,
                    news_report=news_report,
                    external_research_result=external_research_result,
                    brief=prepared_brief,
                ),
            )
        return ResearchPageViewModel(
            symbol=report.symbol,
            security_type=security_type,
            company_summary=CompanyResearchSummaryBuilder().build(
                report,
                news_report=news_report,
                external_research_result=external_research_result,
                brief=prepared_brief,
                insight=prepared_insight,
            ),
            question_summary=InvestmentQuestionSummaryBuilder().build(
                report,
                news_report=news_report,
                external_research_result=external_research_result,
                brief=prepared_brief,
                insight=prepared_insight,
            ),
        )


class StockNewsAnalysisService:
    """Create a deterministic selected-symbol news summary from local news documents."""

    def __init__(self, ingestion: ResearchIngestionService) -> None:
        self.ingestion = ingestion

    def analyze_symbol_news(self, request: StockNewsRequest) -> StockNewsReport:
        as_of = request.as_of or date.today()
        normalized_symbol = _normalize_symbol(request.symbol)
        keywords = _stock_news_keywords(request)
        candidates = [
            document
            for document in self.ingestion.list_documents()
            if document.source_type == "news"
        ]

        news: list[StockNewsEvidence] = []
        warnings: list[str] = []
        for document in candidates:
            text = self.ingestion.store.raw_text_by_document_id.get(document.document_id, "")
            if not _stock_news_matches(document, text, normalized_symbol, keywords):
                continue
            url = _stock_news_url(text)
            if not url:
                warnings.append(
                    f"{document.title}: source URL がないためニュース根拠から除外しました。"
                )
                continue
            news.append(_stock_news_evidence(document, text, url=url, as_of=as_of))

        news = sorted(
            news,
            key=lambda row: (
                _stock_news_freshness_rank(row.freshness_status),
                -(row.published_at or date.min).toordinal(),
                row.title,
            ),
        )[: request.top_k]
        if not news:
            warnings.append(
                "URL付きのニュース根拠が見つかりませんでした。必要な場合は source_type=news の資料に URL を含めて登録してください。"
            )
        return StockNewsReport(
            symbol=normalized_symbol,
            company_name=request.company_name.strip() if request.company_name else None,
            as_of=as_of,
            news=news,
            warnings=warnings,
        )


class ExternalStockNewsFetchService:
    """Fetch selected-symbol external news through a news adapter."""

    def __init__(self, adapter: ExternalStockNewsAdapter) -> None:
        self.adapter = adapter

    def fetch_news(
        self,
        request: StockNewsRequest,
        *,
        allow_network: bool = False,
    ) -> StockNewsReport:
        if self.adapter.requires_network and not allow_network:
            raise ResearchDocumentError(
                "External stock news fetch requires explicit network opt-in.",
                details={"provider": self.adapter.provider, "symbol": request.symbol},
            )

        as_of = request.as_of or date.today()
        normalized_symbol = _normalize_symbol(request.symbol)
        news, warnings = _normalize_external_stock_news(
            self.adapter.fetch_news(request),
            request=request,
            as_of=as_of,
        )
        if not news:
            warnings.append(
                "URL付きの外部ニュースが見つかりませんでした。ニュース本文ではなく、URL付きの出典を確認してください。"
            )
        return StockNewsReport(
            symbol=normalized_symbol,
            company_name=request.company_name.strip() if request.company_name else None,
            as_of=as_of,
            news=news[: request.top_k],
            warnings=warnings,
        )


class ExternalResearchStockNewsAdapter:
    """Adapt source_type=news research payloads into StockNewsEvidence rows."""

    def __init__(self, source_adapter: ExternalResearchSourceAdapter) -> None:
        self.source_adapter = source_adapter
        self.provider = source_adapter.provider
        self.requires_network = source_adapter.requires_network

    def fetch_news(self, request: StockNewsRequest) -> list[StockNewsEvidence]:
        as_of = request.as_of or date.today()
        payloads = self.source_adapter.fetch_sources(
            ExternalResearchFetchRequest(
                symbol=request.symbol,
                company_name=request.company_name,
                related_keywords=request.related_keywords,
                provider=self.provider,
                as_of=as_of,
                allow_network=True,
            )
        )
        return _stock_news_evidence_from_external_payloads(
            payloads,
            request=request,
            as_of=as_of,
        )


class ExternalResearchFetchService:
    """Fetch external sources into the session-local Research RAG store."""

    def __init__(
        self,
        adapter: ExternalResearchSourceAdapter,
        ingestion: ResearchIngestionService,
        index: ResearchIndexService,
        *,
        cache_dir: Path | None = None,
        persist_payloads: bool = False,
    ) -> None:
        self.adapter = adapter
        self.ingestion = ingestion
        self.index = index
        self.cache_dir = cache_dir
        self.persist_payloads = persist_payloads

    def fetch_register_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> ExternalResearchFetchResult:
        if self.adapter.requires_network and not request.allow_network:
            raise ResearchDocumentError(
                "External research fetch requires explicit network opt-in.",
                details={"provider": self.adapter.provider, "symbol": request.symbol},
            )

        fetched_at = datetime.now(UTC)
        as_of = request.as_of or fetched_at.date()
        payloads = self.adapter.fetch_sources(request)
        entries: list[ExternalResearchFetchManifestEntry] = []
        warnings: list[str] = []
        if self.persist_payloads:
            if self.cache_dir is None:
                raise ResearchDocumentError(
                    "External research archive requires a cache directory.",
                    details={
                        "provider": self.adapter.provider,
                        "symbol": request.symbol,
                    },
                )
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        for payload in payloads:
            if not payload.source_url.strip():
                warnings.append(f"{payload.title}: source URL is missing; skipped.")
                continue
            markdown = _external_payload_markdown(payload)
            path: Path | None = None
            existing_document = (
                None
                if self.persist_payloads
                else _external_research_registered_document(self.ingestion, payload)
            )
            if existing_document is not None:
                document = existing_document
            elif self.persist_payloads:
                path = self._write_payload(payload)
                document = self.ingestion.register_document(
                    ResearchDocumentRegisterRequest(
                        symbol=payload.symbol,
                        title=payload.title,
                        local_path=str(path),
                        source_type=payload.source_type,
                        company_name=payload.company_name,
                        published_at=payload.published_at,
                        reliability=payload.reliability,
                    )
                )
            else:
                document = self.ingestion.register_text_document(
                    symbol=payload.symbol,
                    title=payload.title,
                    text=markdown,
                    source_type=payload.source_type,
                    source_url=payload.source_url,
                    provider=payload.provider,
                    company_name=payload.company_name,
                    published_at=payload.published_at,
                    reliability=payload.reliability,
                )
            if document.document_id not in self.index.store.chunks_by_document_id:
                self.index.build_chunks(document.document_id)
            freshness_status = _stock_news_freshness(document.published_at, as_of=as_of)
            if freshness_status == "stale":
                warnings.append(
                    f"{document.title}: 公開日が古いため、最新資料と合わせて確認してください。"
                )
            entries.append(
                ExternalResearchFetchManifestEntry(
                    title=document.title,
                    symbol=document.symbol,
                    source_type=document.source_type,
                    source_url=payload.source_url,
                    provider=payload.provider,
                    published_at=document.published_at,
                    fetched_at=payload.fetched_at,
                    freshness_status=freshness_status,
                    document_id=document.document_id,
                    retention_policy="archive" if self.persist_payloads else "session",
                    content_summary=_external_research_content_summary(payload),
                    local_path=str(path) if path is not None else None,
                    document_hash=(document.document_hash if self.persist_payloads else None),
                )
            )

        if not entries:
            warnings.append("External fetch returned no registerable URL-backed sources.")
        manifest_path: Path | None = None
        if self.persist_payloads:
            manifest_path = self._write_manifest(
                request=request,
                fetched_at=fetched_at,
                entries=entries,
                warnings=warnings,
            )
        return ExternalResearchFetchResult(
            symbol=_normalize_symbol(request.symbol),
            provider=self.adapter.provider,
            fetched_at=fetched_at,
            entries=entries,
            retention_policy="archive" if self.persist_payloads else "session",
            manifest_path=str(manifest_path) if manifest_path is not None else None,
            warnings=warnings,
        )

    def _write_payload(self, payload: ExternalResearchSourcePayload) -> Path:
        if self.cache_dir is None:
            raise ResearchDocumentError(
                "External research archive requires a cache directory.",
                details={"provider": self.adapter.provider, "symbol": payload.symbol},
            )
        markdown = _external_payload_markdown(payload)
        digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:12]
        path = self.cache_dir / (
            f"{_safe_cache_fragment(payload.symbol)}_"
            f"{payload.source_type}_{_safe_cache_fragment(payload.provider)}_"
            f"{payload.fetched_at:%Y%m%d%H%M%S}_{digest}.md"
        )
        path.write_text(markdown, encoding="utf-8")
        return path

    def _write_manifest(
        self,
        *,
        request: ExternalResearchFetchRequest,
        fetched_at: datetime,
        entries: list[ExternalResearchFetchManifestEntry],
        warnings: list[str],
    ) -> Path:
        if self.cache_dir is None:
            raise ResearchDocumentError(
                "External research archive requires a cache directory.",
                details={"provider": self.adapter.provider, "symbol": request.symbol},
            )
        manifest = {
            "schema_version": "external-research-fetch-manifest-v1",
            "symbol": _normalize_symbol(request.symbol),
            "provider": self.adapter.provider,
            "fetched_at": fetched_at.isoformat(),
            "allow_network": request.allow_network,
            "entry_count": len(entries),
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "warnings": warnings,
        }
        path = self.cache_dir / (
            f"{_safe_cache_fragment(request.symbol)}_"
            f"{_safe_cache_fragment(self.adapter.provider)}_"
            f"manifest_{fetched_at:%Y%m%d%H%M%S}.json"
        )
        path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path


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
        with ThreadPoolExecutor(max_workers=self._max_workers()) as executor:
            futures = {}
            for index, adapter in enumerate(self.adapters):
                adapter_request = request.model_copy(update={"provider": adapter.provider})
                future = executor.submit(self._fetch_adapter_with_trace, adapter, adapter_request)
                futures[future] = index
            for future in as_completed(futures):
                index = futures[future]
                adapter_payloads, trace = future.result()
                payloads_by_index[index] = adapter_payloads
                traces_by_index[index] = trace
        payloads: list[ExternalResearchSourcePayload] = []
        for index in range(len(self.adapters)):
            payloads.extend(payloads_by_index.get(index, []))
        self.last_source_traces = [
            traces_by_index[index]
            for index in range(len(self.adapters))
            if index in traces_by_index
        ]
        return payloads

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


def _external_research_registered_document(
    ingestion: ResearchIngestionService,
    payload: ExternalResearchSourcePayload,
) -> ResearchDocument | None:
    """Find an already registered session document for the same fetched source content."""

    source_url = payload.source_url.strip()
    if not source_url:
        return None
    digest_marker = f"- Content digest: {_external_payload_content_digest(payload)}"
    source_markers = (f"- Source URL: {source_url}", f"url: {source_url}")
    for document in ingestion.list_documents(payload.symbol):
        if document.provider != payload.provider or document.source_type != payload.source_type:
            continue
        text = ingestion.store.raw_text_by_document_id.get(document.document_id, "")
        if digest_marker in text and any(marker in text for marker in source_markers):
            return document
    return None


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


def _is_allowed_path(path: Path, allowed_dirs: Sequence[Path]) -> bool:
    return any(path == directory or directory in path.parents for directory in allowed_dirs)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _stable_id(prefix: str, *parts: str) -> str:
    normalized = "|".join(part.strip().lower() for part in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _safe_cache_fragment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._") or "source"


def _external_payload_markdown(payload: ExternalResearchSourcePayload) -> str:
    lines = [
        f"# {payload.title}",
        "",
        "## Source",
        "",
        f"- Provider: {payload.provider}",
        f"- Source URL: {payload.source_url}",
        f"- Symbol: {_normalize_symbol(payload.symbol)}",
        f"- Source type: {payload.source_type}",
        f"- Fetched at: {payload.fetched_at.isoformat()}",
        f"- Content digest: {_external_payload_content_digest(payload)}",
    ]
    if payload.published_at:
        lines.append(f"- Published at: {payload.published_at.isoformat()}")
    if payload.company_name:
        lines.append(f"- Company: {payload.company_name}")
    lines.extend(
        [
            "- Usage: Local Research RAG evidence only; not a buy/sell recommendation.",
            "",
            "## Content",
            "",
            f"source: {payload.provider}",
            f"url: {payload.source_url}",
            f"summary: {_excerpt(payload.content, max_chars=240)}",
            "",
            payload.content.strip(),
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _external_payload_content_digest(payload: ExternalResearchSourcePayload) -> str:
    stable_payload = {
        "symbol": _normalize_symbol(payload.symbol),
        "title": payload.title.strip(),
        "content": payload.content.strip(),
        "source_type": payload.source_type,
        "source_url": payload.source_url.strip(),
        "provider": payload.provider.strip(),
        "company_name": (payload.company_name or "").strip(),
        "published_at": (payload.published_at.isoformat() if payload.published_at else ""),
        "reliability": str(payload.reliability),
    }
    serialized = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _external_research_content_summary(payload: ExternalResearchSourcePayload) -> str:
    max_chars = 1800 if payload.source_type == "provider_profile" else 360
    return _excerpt(payload.content, max_chars=max_chars)


def _google_news_query(
    request: ExternalResearchFetchRequest,
    *,
    lookback_days: int,
) -> str:
    base_terms = _google_news_query_base_terms(request)
    if not base_terms:
        return ""
    base_query = " OR ".join(_google_news_quote_query_term(term) for term in base_terms[:3])
    if len(base_terms) > 1:
        base_query = f"({base_query})"
    investment_query = " OR ".join(GOOGLE_NEWS_INVESTMENT_QUERY_TERMS)
    return f"{base_query} ({investment_query}) when:{max(1, lookback_days)}d"


def _google_news_query_base_terms(request: ExternalResearchFetchRequest) -> list[str]:
    terms: list[str] = []
    if request.company_name:
        terms.append(request.company_name)
    terms.extend(request.related_keywords)
    symbol = _normalize_symbol(request.symbol)
    terms.append(symbol)
    if "." in symbol:
        terms.append(symbol.split(".", 1)[0])
    return _dedupe_non_empty_text(terms)


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


def _chunk_document_text(
    document: ResearchDocument,
    text: str,
    *,
    max_chars: int,
) -> list[ResearchChunk]:
    sections = _markdown_sections(text)
    chunks: list[ResearchChunk] = []
    for section_title, section_text in sections:
        for piece in _split_text(section_text, max_chars=max_chars):
            chunk_index = len(chunks)
            chunk_id = _stable_id(
                "research-chunk", document.document_id, str(chunk_index), piece[:80]
            )
            chunks.append(
                ResearchChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    symbol=document.symbol,
                    title=document.title,
                    source_type=document.source_type,
                    published_at=document.published_at,
                    section_title=section_title,
                    text=piece,
                    chunk_index=chunk_index,
                    char_count=len(piece),
                    metadata={
                        "document_hash": document.document_hash,
                        "reliability": str(document.reliability),
                    },
                )
            )
    if not chunks:
        raise ResearchParseError(
            "Research document did not produce any searchable chunks.",
            details={"document_id": document.document_id},
        )
    return chunks


def _markdown_sections(text: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    current_title: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            if title:
                if sections[-1][1]:
                    sections.append((title, []))
                else:
                    sections[-1] = (title, [])
                current_title = title
                continue
        sections[-1][1].append(line)
    return [
        (title if title is not None else current_title, "\n".join(lines).strip())
        for title, lines in sections
        if "\n".join(lines).strip()
    ]


def _split_text(text: str, *, max_chars: int) -> list[str]:
    paragraphs = [
        paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()
    ]
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                pieces.append(current.strip())
                current = ""
            pieces.extend(_split_long_text(paragraph, max_chars=max_chars))
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            pieces.append(current.strip())
            current = paragraph
    if current:
        pieces.append(current.strip())
    return pieces


def _split_long_text(text: str, *, max_chars: int) -> list[str]:
    return [text[index : index + max_chars].strip() for index in range(0, len(text), max_chars)]


def _query_terms(query: str) -> list[str]:
    normalized = query.lower()
    terms = re.findall(r"[a-z0-9_]+|[一-龥ぁ-んァ-ンー]{2,}", normalized)
    return sorted(set(terms))


def _expanded_query_terms(request: ResearchSearchRequest) -> list[str]:
    terms = list(_query_terms(request.query))
    if request.query_category is not None:
        terms.extend(DEFAULT_RESEARCH_QUERY_TERMS.get(request.query_category, ()))
    terms.extend(request.expanded_terms)
    return _normalize_query_terms(terms)


def _normalize_query_terms(terms: Sequence[str]) -> list[str]:
    normalized: set[str] = set()
    for term in terms:
        normalized.update(_query_terms(term))
    return sorted(normalized)


def _chunk_relevance_score(chunk: ResearchChunk, query_terms: list[str], *, as_of: date) -> Decimal:
    document = _score_text(f"{chunk.title} {chunk.section_title or ''}", query_terms)
    body = _score_text(chunk.text, query_terms)
    if not query_terms:
        body = Decimal("0.20")
    raw = min(Decimal("1"), (document * Decimal("0.25")) + (body * Decimal("0.75")))
    if raw == 0:
        return Decimal("0")
    freshness_bonus = Decimal("0.03") if chunk.published_at else Decimal("0")
    score = min(Decimal("1"), raw + freshness_bonus)
    return (score * _freshness_factor(chunk.published_at, as_of=as_of)).quantize(Decimal("0.0001"))


def _freshness_factor(published_at: date | None, *, as_of: date) -> Decimal:
    if published_at is None:
        return Decimal("0.85")
    age_days = (as_of - published_at).days
    if age_days < 0:
        return Decimal("1")
    if age_days <= 365:
        return Decimal("1")
    if age_days <= 730:
        return Decimal("0.90")
    if age_days <= 1095:
        return Decimal("0.75")
    return Decimal("0.60")


def _score_text(text: str, query_terms: list[str]) -> Decimal:
    if not query_terms:
        return Decimal("0")
    normalized = text.lower()
    hits = sum(1 for term in query_terms if term in normalized)
    if hits == 0:
        return Decimal("0")
    return Decimal(hits) / Decimal(len(query_terms))


def _evidence_from_chunk(chunk: ResearchChunk, *, relevance_score: Decimal) -> ResearchEvidence:
    return ResearchEvidence(
        symbol=chunk.symbol,
        document_id=chunk.document_id,
        chunk_id=chunk.chunk_id,
        title=chunk.title,
        source_type=chunk.source_type,
        published_at=chunk.published_at,
        section_title=chunk.section_title,
        excerpt=_excerpt(chunk.text),
        relevance_score=relevance_score,
        reliability=_chunk_reliability(chunk),
    )


def _chunk_reliability(chunk: ResearchChunk) -> Decimal:
    return (
        Decimal(chunk.metadata.get("reliability", "0.70"))
        if "reliability" in chunk.metadata
        else Decimal("0.70")
    )


def _evidence_from_candidate(candidate: ResearchRetrievalCandidate) -> ResearchEvidence:
    return ResearchEvidence(
        symbol=candidate.symbol,
        document_id=candidate.document_id,
        chunk_id=candidate.chunk_id,
        title=candidate.title,
        source_type=candidate.source_type,
        published_at=candidate.published_at,
        section_title=candidate.section_title,
        excerpt=candidate.excerpt,
        relevance_score=candidate.final_relevance_score,
        reliability=candidate.reliability,
    )


def _excerpt(text: str, *, max_chars: int = 220) -> str:
    single_line = re.sub(r"\s+", " ", text).strip()
    if len(single_line) <= max_chars:
        return single_line
    return f"{single_line[: max_chars - 3].rstrip()}..."


def _dedupe_evidence(evidence: list[ResearchEvidence]) -> list[ResearchEvidence]:
    deduped: dict[str, ResearchEvidence] = {}
    for row in evidence:
        existing = deduped.get(row.chunk_id)
        if existing is None or row.relevance_score > existing.relevance_score:
            deduped[row.chunk_id] = row
    return sorted(
        deduped.values(),
        key=lambda row: (
            -row.relevance_score,
            -(row.published_at or date.min).toordinal(),
            row.document_id,
            row.chunk_id,
        ),
    )


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _evidence_rerank_score(row: ResearchEvidence, *, as_of: date) -> Decimal:
    score = (
        (row.relevance_score * Decimal("0.55"))
        + (row.reliability * Decimal("0.25"))
        + (_freshness_factor(row.published_at, as_of=as_of) * Decimal("0.10"))
        + (Decimal(str(_source_type_priority(row.source_type))) * Decimal("0.10"))
    )
    return score.quantize(Decimal("0.0001"))


def _search_vector_entries(
    entries: Mapping[str, tuple[ResearchRetrievalCandidate, ResearchEmbedding]],
    request: ResearchSearchRequest,
) -> list[ResearchRetrievalCandidate]:
    if not request.query_vector:
        return []
    source_types = set(request.source_types)
    scored: list[ResearchRetrievalCandidate] = []
    for candidate, embedding in entries.values():
        if candidate.symbol != _normalize_symbol(request.symbol):
            continue
        if source_types and candidate.source_type not in source_types:
            continue
        vector_score = _cosine_similarity(request.query_vector, embedding.vector)
        if vector_score <= Decimal("0"):
            continue
        scored.append(
            candidate.model_copy(
                update={
                    "vector_score": vector_score,
                    "final_relevance_score": vector_score,
                    "retrieval_backend": "vector",
                }
            )
        )
    return sorted(
        scored,
        key=lambda row: (
            -(row.vector_score or Decimal("0")),
            -(row.published_at or date.min).toordinal(),
            row.document_id,
            row.chunk_id,
        ),
    )[: request.top_k]


def _build_vector_retrieval_quality(
    request: ResearchSearchRequest,
    *,
    candidate_count: int,
    entry_count: int,
    expanded_terms: Sequence[str] | None,
    empty_cache_warning: str | None = None,
) -> ResearchRetrievalQuality:
    warnings: list[str] = []
    if not request.query_vector:
        warnings.append("Vector query is empty; vector retrieval was skipped.")
    elif candidate_count == 0:
        if entry_count == 0 and empty_cache_warning:
            warnings.append(empty_cache_warning)
        warnings.append("Vector retrieval found no matching candidates.")
    query = request.query or request.query_category or "vector search"
    return ResearchRetrievalQuality(
        backend="vector",
        query=query,
        expanded_terms=_normalize_query_terms(expanded_terms or request.expanded_terms),
        candidate_count=candidate_count,
        evidence_count=candidate_count,
        warnings=warnings,
    )


def _local_embedding_vector(text: str, *, dimensions: int) -> list[float]:
    terms = _query_terms(text)
    if not terms:
        return []
    buckets = [0.0] * dimensions
    for term in terms:
        digest = hashlib.sha256(term.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], byteorder="big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        buckets[index] += sign
    norm = math.sqrt(sum(value * value for value in buckets))
    if norm == 0:
        return []
    return [round(value / norm, 6) for value in buckets]


def _cosine_similarity(query_vector: Sequence[float], candidate_vector: Sequence[float]) -> Decimal:
    if not query_vector or not candidate_vector or len(query_vector) != len(candidate_vector):
        return Decimal("0")
    query_norm = math.sqrt(sum(value * value for value in query_vector))
    candidate_norm = math.sqrt(sum(value * value for value in candidate_vector))
    if query_norm == 0 or candidate_norm == 0:
        return Decimal("0")
    dot = sum(left * right for left, right in zip(query_vector, candidate_vector, strict=True))
    score = max(0.0, min(1.0, dot / (query_norm * candidate_norm)))
    return Decimal(str(score)).quantize(Decimal("0.0001"))


def _source_type_priority(source_type: ResearchSourceType) -> float:
    priorities: dict[ResearchSourceType, float] = {
        "annual_report": 1.0,
        "earnings_report": 0.95,
        "earnings_presentation": 0.95,
        "medium_term_plan": 0.95,
        "integrated_report": 0.95,
        "company_ir": 0.88,
        "tdnet": 0.90,
        "provider_profile": 0.65,
        "user_note": 0.70,
        "news": 0.60,
    }
    return priorities[source_type]


def _category_labels(categories: Sequence[ResearchTopicCategory]) -> str:
    labels_by_category: dict[ResearchTopicCategory, str] = {
        "growth": "成長材料",
        "shareholder_return": "株主還元",
        "financial_safety": "財務安全性",
        "business_risk": "事業リスク",
        "confirmation_gap": "確認不足",
    }
    labels = []
    for category in categories:
        label = labels_by_category[category]
        if label not in labels:
            labels.append(label)
    return "、".join(labels)


def _evidence_reference_sentence(evidence: list[ResearchEvidence]) -> str:
    if not evidence:
        return "根拠資料はまだ紐づいていません。"
    lead = evidence[0]
    published = lead.published_at.isoformat() if lead.published_at else "日付未設定"
    return f"主な根拠は「{lead.title}」（{published}）など{len(evidence)}件です。"


def _retrieval_quality(
    *,
    queries: Sequence[str],
    expanded_terms: Sequence[str],
    candidate_count: int,
    evidence_count: int,
    data_quality: ResearchDataQuality,
) -> ResearchRetrievalQuality:
    warnings = list(data_quality.warnings)
    if evidence_count == 0 and "検索で根拠候補が見つかりませんでした。" not in warnings:
        warnings.append("検索で根拠候補が見つかりませんでした。")
    return ResearchRetrievalQuality(
        backend="keyword",
        query=" | ".join(queries),
        expanded_terms=_normalize_query_terms(expanded_terms),
        candidate_count=candidate_count,
        evidence_count=evidence_count,
        warnings=warnings,
    )


def _extracted_claim(
    *,
    symbol: str,
    category: ResearchTopicCategory,
    label: str,
    evidence: list[ResearchEvidence],
) -> ResearchExtractedClaim:
    normalized_symbol = _normalize_symbol(symbol)
    if not evidence:
        return ResearchExtractedClaim(
            symbol=normalized_symbol,
            category="confirmation_gap",
            claim=f"{label}の根拠は不足しています。",
            summary=f"{label}について、登録資料から十分な根拠を確認できませんでした。",
            supporting_evidence=[],
            confidence=Decimal("0"),
            missing_information=[f"{label}を確認できる資料または記述"],
            caution_note="根拠不足を低評価や売買判断として扱わず、追加確認の対象にします。",
        )
    lead = evidence[0]
    return ResearchExtractedClaim(
        symbol=normalized_symbol,
        category=category,
        claim=f"{label}に関する確認材料があります。",
        summary=f"{label}は「{lead.excerpt}」を主な根拠として整理します。",
        supporting_evidence=evidence,
        confidence=_claim_confidence(evidence),
        missing_information=[],
        caution_note="この抽出結果は登録資料から確認できる判断材料であり、売買推奨ではありません。",
    )


def _claim_confidence(evidence: list[ResearchEvidence]) -> Decimal:
    if not evidence:
        return Decimal("0")
    scores = [
        (row.relevance_score * Decimal("0.6")) + (row.reliability * Decimal("0.4"))
        for row in evidence
    ]
    return (sum(scores, Decimal("0")) / Decimal(len(scores))).quantize(Decimal("0.0001"))


def _score_report_category(
    report: CompanyResearchReport,
    category: ResearchTopicCategory,
    *,
    as_of: date,
) -> Decimal:
    evidence = [
        evidence
        for point in report.points
        if point.category == category
        for evidence in point.evidence
    ]
    return _score_evidence_strength(_dedupe_evidence(evidence), as_of=as_of)


def _score_research_terms(
    evidence: Sequence[ResearchEvidence],
    terms: Sequence[str],
    *,
    as_of: date,
) -> Decimal:
    query_terms = _normalize_query_terms(terms)
    matched = [
        row
        for row in evidence
        if (
            _score_text(f"{row.title} {row.section_title or ''} {row.excerpt}", query_terms)
            > Decimal("0")
        )
    ]
    return _score_evidence_strength(_dedupe_evidence(matched), as_of=as_of)


def _score_evidence_strength(evidence: list[ResearchEvidence], *, as_of: date) -> Decimal:
    if not evidence:
        return Decimal("0")
    scores = [
        (
            (row.relevance_score * Decimal("0.45"))
            + (row.reliability * Decimal("0.35"))
            + (_freshness_factor(row.published_at, as_of=as_of) * Decimal("0.20"))
        )
        * Decimal("100")
        for row in evidence
    ]
    return _score_100(sum(scores, Decimal("0")) / Decimal(len(scores)))


def _score_disclosure_quality(report: CompanyResearchReport, *, as_of: date) -> Decimal:
    if not report.evidence:
        return Decimal("0")
    evidence_count_score = min(Decimal("100"), Decimal(len(report.evidence)) * Decimal("20"))
    reliability_score = sum(
        (row.reliability * Decimal("100") for row in report.evidence), Decimal("0")
    ) / Decimal(len(report.evidence))
    source_score = sum(
        (
            Decimal(str(_source_type_priority(row.source_type))) * Decimal("100")
            for row in report.evidence
        ),
        Decimal("0"),
    ) / Decimal(len(report.evidence))
    status_factor = _data_quality_status_factor(report.data_quality.status)
    score = (
        (evidence_count_score * Decimal("0.35"))
        + (reliability_score * Decimal("0.35"))
        + (source_score * Decimal("0.30"))
    ) * status_factor
    return _score_100(score)


def _score_research_freshness(report: CompanyResearchReport, *, as_of: date) -> Decimal:
    if report.data_quality.latest_document_date is None:
        return Decimal("0")
    return _score_100(
        _freshness_factor(report.data_quality.latest_document_date, as_of=as_of) * Decimal("100")
    )


def _research_score_confidence(report: CompanyResearchReport) -> Decimal:
    if not report.evidence:
        return Decimal("0")
    average_reliability = sum((row.reliability for row in report.evidence), Decimal("0")) / Decimal(
        len(report.evidence)
    )
    coverage = min(Decimal("1"), Decimal(len(report.evidence)) / Decimal("6"))
    status_factor = _data_quality_status_factor(report.data_quality.status)
    confidence = (
        (average_reliability * Decimal("0.50"))
        + (coverage * Decimal("0.30"))
        + (status_factor * Decimal("0.20"))
    )
    return min(Decimal("1"), confidence).quantize(Decimal("0.0001"))


def _research_score_warnings(
    report: CompanyResearchReport,
    component_scores: Sequence[Decimal],
) -> list[str]:
    warnings = list(report.data_quality.warnings)
    if not report.evidence:
        warnings.append("Research Score は根拠不足のため参考表示に留めます。")
    if any(score == Decimal("0") for score in component_scores[:5]):
        warnings.append("一部のResearch観点は根拠が不足しており、推定で補完していません。")
    return list(dict.fromkeys(warnings))


def _research_score_summary(
    report: CompanyResearchReport,
    *,
    total_score: Decimal,
    confidence: Decimal,
) -> str:
    if not report.evidence:
        return (
            "Research Scoreは、登録資料から確認できる根拠が不足しているため、"
            "未確認状態として扱います。これは銘柄評価や売買判断ではありません。"
        )
    return (
        f"Research Score {total_score} は、登録資料の根拠数、鮮度、信頼度、"
        f"開示の確認しやすさを整理した補助スコアです。confidence={confidence}。"
        "売買推奨ではなく、追加確認の優先度を考えるための材料です。"
    )


_RESEARCH_BRIEF_METRIC_SPECS: tuple[
    tuple[ResearchMetricKey, str, tuple[str, ...]],
    ...,
] = (
    (
        "revenue",
        "売上高",
        (r"売上(?:高|収益)?", r"total revenue", r"totalRevenue", r"revenue", r"sales"),
    ),
    (
        "operating_income",
        "営業利益",
        (r"営業利益", r"operating income", r"operatingIncome"),
    ),
    (
        "net_income",
        "純利益",
        (
            r"純利益",
            r"当期利益",
            r"net income to common",
            r"netIncomeToCommon",
            r"netIncome",
            r"net income",
            r"net profit",
        ),
    ),
    (
        "eps",
        "EPS",
        (
            r"EPS",
            r"trailing eps",
            r"forward eps",
            r"trailingEps",
            r"forwardEps",
            r"1株当たり(?:利益|当期利益)",
            r"earnings per share",
        ),
    ),
    ("dividend", "配当", (r"配当(?:金|利回り)?", r"dividend(?: yield| per share)?")),
    (
        "per",
        "PER",
        (
            r"PER",
            r"trailing PE",
            r"forward PE",
            r"trailingPE",
            r"forwardPE",
            r"price[- ]earnings ratio",
        ),
    ),
    ("pbr", "PBR", (r"PBR", r"price[- ]to[- ]book", r"priceToBook")),
    ("roe", "ROE", (r"ROE", r"return on equity", r"returnOnEquity")),
    (
        "market_cap",
        "時価総額",
        (r"時価総額", r"market cap(?:italization)?", r"marketCap"),
    ),
)
_RESEARCH_BRIEF_RAW_PROVIDER_LABELS = (
    "Company Name",
    "Provider Symbol",
    "Quote Type",
    "Exchange",
    "Currency",
    "Sector",
    "Industry",
    "Country",
    "Website",
    "Fund Name",
    "Fund Family",
    "Asset Category",
    "Category",
    "Benchmark",
    "Market Cap",
    "Enterprise Value",
    "Total Revenue",
    "Revenue",
    "Operating Income",
    "Net Income To Common",
    "Net Income",
    "Trailing EPS",
    "Forward EPS",
    "PER",
    "PBR",
    "ROE",
    "Trailing PE",
    "Forward PE",
    "Price To Book",
    "Return On Equity",
    "Dividend Rate",
    "Dividend Yield",
    "Yield",
    "Trailing Annual Dividend Yield",
    "Expense Ratio",
    "Annual Report Expense Ratio",
    "Net Assets",
    "Total Assets",
    "NAV",
    "NAV Price",
    "Regular Market Price",
    "Market Price",
    "Top Holdings",
    "Holdings",
    "Full Time Employees",
    "Payout Ratio",
    "Beta",
)
_RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES: set[ResearchSourceType] = {
    "annual_report",
    "earnings_report",
    "earnings_presentation",
    "medium_term_plan",
    "integrated_report",
    "company_ir",
    "tdnet",
}
_RESEARCH_BRIEF_MEDIUM_CONFIDENCE_SOURCES: set[ResearchSourceType] = {
    "provider_profile",
    "news",
}


def _research_brief_metrics(
    evidence: Sequence[ResearchEvidence],
) -> list[ResearchMetric]:
    metrics_by_key: dict[ResearchMetricKey, ResearchMetric] = {}
    for row in evidence:
        text = _research_brief_evidence_text(row)
        for key, label, patterns in _RESEARCH_BRIEF_METRIC_SPECS:
            if key in metrics_by_key:
                continue
            value = _research_brief_metric_value(text, patterns)
            if value is None:
                continue
            metrics_by_key[key] = ResearchMetric(
                key=key,
                label=label,
                value=value,
                source_title=row.title,
                source_type=row.source_type,
                source_confidence=_research_brief_source_confidence(row.source_type),
            )
    return [
        metrics_by_key[key] for key, _, _ in _RESEARCH_BRIEF_METRIC_SPECS if key in metrics_by_key
    ]


def _research_brief_metric_value(text: str, patterns: Sequence[str]) -> str | None:
    unit_pattern = (
        r"(?:兆円|億円|百万円|万円|円|％|%|倍|株|"
        r"trillion yen|billion yen|million yen|yen|JPY|USD|per share|x)?"
    )
    for pattern in patterns:
        match = re.search(
            rf"(?:{pattern})\s*(?:[:：=は])?\s*" rf"([+-]?\d[\d,]*(?:\.\d+)?\s*{unit_pattern})",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .。、、")
        if value:
            return value
    return None


def _research_brief_missing_metric_labels(
    metrics: Sequence[ResearchMetric],
) -> list[str]:
    found = {metric.key for metric in metrics}
    return [label for key, label, _ in _RESEARCH_BRIEF_METRIC_SPECS if key not in found]


def _research_fact_summary(
    report: CompanyResearchReport,
    *,
    metrics: Sequence[ResearchMetric],
    positive_materials: Sequence[ResearchBriefMaterial],
    caution_materials: Sequence[ResearchBriefMaterial],
    missing_metrics: Sequence[str],
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> ResearchFactSummary:
    """Extract source-backed facts before shaping the readable brief."""

    business_overview = _research_fact_business_overview_items(report)
    return ResearchFactSummary(
        symbol=report.symbol,
        as_of=report.as_of,
        business_overview=business_overview[:2],
        business_segments=_research_fact_business_segment_items(business_overview),
        business_regions=_research_fact_business_region_items(report, business_overview),
        revenue_drivers=_research_fact_revenue_driver_items(report, business_overview),
        financial_snapshot=_research_fact_financial_items(metrics),
        earnings_outlook=_research_fact_earnings_outlook_items(report),
        shareholder_return_policy=_research_fact_shareholder_return_items(report),
        recent_events=_research_fact_recent_event_items(
            report,
            news_report=news_report,
            external_research_result=external_research_result,
        ),
        positive_materials=_research_fact_material_items(positive_materials),
        caution_materials=_research_fact_material_items(caution_materials),
        missing_items=_research_fact_missing_items(
            report,
            missing_metrics=missing_metrics,
            news_report=news_report,
        ),
    )


def _research_fact_business_overview_items(
    report: CompanyResearchReport,
) -> list[ResearchFactItem]:
    items: list[ResearchFactItem] = []
    for row in _research_brief_prioritized_business_evidence(report):
        cleaned = _research_brief_clean_provider_text(row.excerpt)
        if not cleaned:
            continue
        value = _research_brief_readable_business_overview(cleaned)
        if not value:
            continue
        items.append(
            ResearchFactItem(
                label="事業概要",
                value=value,
                source_title=row.title,
                source_type=row.source_type,
                source_confidence=_research_brief_source_confidence(row.source_type),
                published_at=row.published_at,
                note=_research_fact_source_note(row.source_type),
            )
        )
    return _unique_research_fact_items(items)[:3]


def _research_fact_business_segment_items(
    overview_items: Sequence[ResearchFactItem],
) -> list[ResearchFactItem]:
    items: list[ResearchFactItem] = []
    for item in overview_items:
        segments = _research_fact_segment_labels(item.value)
        if not segments:
            continue
        items.append(
            ResearchFactItem(
                label="主要事業",
                value="、".join(segments[:3]),
                source_title=item.source_title,
                source_type=item.source_type,
                source_confidence=item.source_confidence,
                published_at=item.published_at,
                note=item.note,
            )
        )
    return _unique_research_fact_items(items)[:2]


def _research_fact_business_region_items(
    report: CompanyResearchReport,
    overview_items: Sequence[ResearchFactItem],
) -> list[ResearchFactItem]:
    return _research_fact_label_items_from_sources(
        label="地域展開",
        report=report,
        overview_items=overview_items,
        extractor=_research_fact_region_labels,
    )[:3]


def _research_fact_revenue_driver_items(
    report: CompanyResearchReport,
    overview_items: Sequence[ResearchFactItem],
) -> list[ResearchFactItem]:
    return _research_fact_label_items_from_sources(
        label="収益源",
        report=report,
        overview_items=overview_items,
        extractor=_research_fact_revenue_driver_labels,
    )[:3]


def _research_fact_financial_items(
    metrics: Sequence[ResearchMetric],
) -> list[ResearchFactItem]:
    return [
        ResearchFactItem(
            label=metric.label,
            value=metric.value,
            source_title=metric.source_title,
            source_type=metric.source_type,
            source_confidence=metric.source_confidence,
            note="抽出済みの定量指標です。公式資料で最終確認してください。",
        )
        for metric in metrics
    ]


def _research_fact_earnings_outlook_items(
    report: CompanyResearchReport,
) -> list[ResearchFactItem]:
    return _research_fact_sentence_items(
        report,
        label="業績見通し",
        keywords=(
            "通期予想",
            "業績予想",
            "業績見通し",
            "業績修正",
            "上方修正",
            "下方修正",
            "guidance",
            "outlook",
            "forecast",
            "revised",
            "raised guidance",
            "lowered guidance",
        ),
        source_note="業績予想・業績修正に関する確認材料です。",
    )[:3]


def _research_fact_shareholder_return_items(
    report: CompanyResearchReport,
) -> list[ResearchFactItem]:
    return _research_fact_sentence_items(
        report,
        label="配当・株主還元方針",
        keywords=(
            "配当方針",
            "配当",
            "増配",
            "減配",
            "自社株買い",
            "株主還元",
            "配当性向",
            "dividend policy",
            "dividend",
            "shareholder return",
            "buyback",
            "payout",
        ),
        source_note="配当・株主還元に関する確認材料です。",
    )[:3]


def _research_fact_recent_event_items(
    report: CompanyResearchReport,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> list[ResearchFactItem]:
    items: list[ResearchFactItem] = []
    event_source_types: set[ResearchSourceType] = {
        "tdnet",
        "earnings_report",
        "earnings_presentation",
        "news",
    }
    for row in report.evidence:
        if row.source_type not in event_source_types:
            continue
        items.append(
            ResearchFactItem(
                label=_research_brief_source_type_label(row.source_type),
                value=_research_fact_event_value(row.title, row.source_type),
                source_title=row.title,
                source_type=row.source_type,
                source_confidence=_research_brief_source_confidence(row.source_type),
                published_at=row.published_at,
                note=_research_fact_source_note(row.source_type),
            )
        )
    if news_report is not None:
        for news in news_report.news:
            items.append(
                ResearchFactItem(
                    label="ニュース",
                    value=_clip_text(news.summary or news.title, max_chars=120),
                    source_title=news.title,
                    source_type="news",
                    source_confidence=_research_brief_source_confidence("news"),
                    published_at=news.published_at,
                    note="URL付きニュースとして確認した補助情報です。",
                )
            )
    if external_research_result is not None:
        for entry in external_research_result.entries:
            if entry.source_type not in event_source_types:
                continue
            items.append(
                ResearchFactItem(
                    label=_research_brief_source_type_label(entry.source_type),
                    value=_research_fact_event_value(entry.title, entry.source_type),
                    source_title=entry.title,
                    source_type=entry.source_type,
                    source_confidence=_research_brief_source_confidence(entry.source_type),
                    published_at=entry.published_at,
                    note="AI調査で一時参照した外部ソースです。",
                )
            )
    return _unique_research_fact_items(items)[:6]


def _research_fact_material_items(
    materials: Sequence[ResearchBriefMaterial],
) -> list[ResearchFactItem]:
    return _unique_research_fact_items(
        [
            ResearchFactItem(
                label=material.label,
                value=material.summary,
                source_title=material.source_title,
                source_type=material.source_type,
                source_confidence=material.source_confidence,
                published_at=material.published_at,
                note=_research_fact_source_note(material.source_type),
            )
            for material in materials
        ]
    )


def _research_fact_missing_items(
    report: CompanyResearchReport,
    *,
    missing_metrics: Sequence[str],
    news_report: StockNewsReport | None,
) -> list[ResearchMissingItem]:
    items: list[ResearchMissingItem] = []
    if missing_metrics:
        items.append(
            ResearchMissingItem(
                category="financial_metric",
                label="未確認の主要指標",
                reason="、".join(missing_metrics[:8]),
                next_source_hint="決算短信、有価証券報告書、公式IR資料",
            )
        )
    if not any(
        row.source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES for row in report.evidence
    ):
        items.append(
            ResearchMissingItem(
                category="official_source",
                label="公式資料の裏取り",
                reason="公式IR、TDnet、EDINETなどの一次情報がまだ十分ではありません。",
                next_source_hint="TDnet、EDINET、企業IRサイト",
            )
        )
    if news_report is not None and news_report.warnings:
        items.append(
            ResearchMissingItem(
                category="news",
                label="ニュース取得の確認",
                reason=" / ".join(news_report.warnings[:3]),
                next_source_hint="URL付きニュース、公式発表、TDnet",
            )
        )
    for warning in report.data_quality.warnings:
        category: ResearchMissingItemCategory = (
            "source_freshness" if "鮮度" in warning or "2年以上" in warning else "other"
        )
        items.append(
            ResearchMissingItem(
                category=category,
                label="根拠資料の確認",
                reason=warning,
                next_source_hint="最新の公式資料または保存済み資料",
            )
        )
    return _unique_research_missing_items(items)[:8]


def _research_brief_business_overview(
    report: CompanyResearchReport,
    *,
    fact_summary: ResearchFactSummary | None = None,
) -> str:
    if fact_summary is not None and fact_summary.business_overview:
        return fact_summary.business_overview[0].value
    for row in _research_brief_prioritized_business_evidence(report):
        cleaned = _research_brief_clean_provider_text(row.excerpt)
        if cleaned:
            return _research_brief_readable_business_overview(cleaned)
    return report.summary


def _research_brief_prioritized_business_evidence(
    report: CompanyResearchReport,
) -> list[ResearchEvidence]:
    return [
        *[row for row in report.evidence if row.source_type == "provider_profile"],
        *[
            row
            for row in report.evidence
            if row.source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES
        ],
        *report.evidence,
    ]


def _research_brief_clean_provider_text(text: str) -> str:
    lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    cleaned = " ".join(lines)
    cleaned = re.sub(r"\bCompany Name\s*[:：]\s*", "", cleaned, flags=re.IGNORECASE)
    for label in (
        "Provider Symbol",
        "Quote Type",
        "Exchange",
        "Currency",
        "Country",
        "Website",
        "Market Cap",
        "Enterprise Value",
        "Total Revenue",
        "Revenue",
        "Operating Income",
        "Net Income To Common",
        "Net Income",
        "Trailing EPS",
        "Forward EPS",
        "PER",
        "PBR",
        "ROE",
        "Trailing PE",
        "Forward PE",
        "Price To Book",
        "Return On Equity",
        "Dividend Rate",
        "Dividend Yield",
        "Full Time Employees",
        "Payout Ratio",
        "Beta",
    ):
        cleaned = re.sub(rf"\b{re.escape(label)}\s*[:：]\s*\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\bSector\s*[:：]\s*[^:。.\n\r]+?(?=\s+Industry\s*[:：]|[。.\n\r]|$)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\bIndustry\s*[:：]\s*[^:。.\n\r]+?(?=[。.\n\r]|$)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return _research_user_facing_text(cleaned)


def _research_brief_raw_label_pattern() -> str:
    return "|".join(
        re.escape(label) for label in (*_RESEARCH_BRIEF_RAW_PROVIDER_LABELS, "Business Summary")
    )


def _research_user_facing_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    replacements = (
        (r"\bsource_type\s*=\s*news\b", "外部ニュース"),
        (r"\bsource_type\s*=\s*tdnet\b", "TDnet適時開示"),
        (r"\bsource_type\s*=\s*provider_profile\b", "企業プロフィール"),
        (r"\bprovider_profile\b", "企業プロフィール"),
        (r"\bExternalResearchFetchResult\b", "外部取得結果"),
        (r"\bsource_ynews\b", "外部ニュース"),
    )
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bBusiness Summary\s*[:：]\s*", "", cleaned, flags=re.IGNORECASE)
    for raw_label in _RESEARCH_BRIEF_RAW_PROVIDER_LABELS:
        cleaned = re.sub(
            rf"\b{re.escape(raw_label)}\s*[:：]\s*.*?(?=\s+(?:{_research_brief_raw_label_pattern()})\s*[:：]|[。.\n\r]|$)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(rf"\b{re.escape(raw_label)}\s*[:：]", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" .。")


def _research_brief_readable_business_overview(text: str) -> str:
    readable = _research_brief_plain_sentences(text)
    domain_sentence = _research_brief_business_domain_sentence(readable)
    if domain_sentence:
        return domain_sentence
    if _looks_mostly_english(readable):
        return (
            "外部データから確認できる範囲では、事業概要の材料は限定的です。"
            "公式IRで事業内容、主要セグメント、地域別構成を追加確認してください。"
        )
    return _clip_text(readable, max_chars=220)


def _research_brief_plain_sentences(text: str) -> str:
    chunks = [
        chunk.strip(" ・-") for chunk in re.split(r"(?<=[。.!?])\s+|[\r\n]+", text) if chunk.strip()
    ]
    useful_chunks = [
        chunk
        for chunk in chunks
        if not any(
            re.search(rf"\b{re.escape(label)}\s*[:：]", chunk, flags=re.IGNORECASE)
            for label in _RESEARCH_BRIEF_RAW_PROVIDER_LABELS
        )
    ]
    return re.sub(r"\s+", " ", " ".join(useful_chunks or chunks)).strip()


def _research_brief_business_domain_sentence(text: str) -> str:
    lowered = text.lower()
    domains: list[str] = []
    if any(
        keyword in lowered
        for keyword in (
            "vehicle",
            "vehicles",
            "automotive",
            "automobile",
            "passenger car",
            "commercial vehicle",
        )
    ):
        domains.append("自動車・モビリティ関連事業（車両の設計・製造・販売）")
    if any(keyword in lowered for keyword in ("software", "connected", "mobility service")):
        domains.append("ソフトウェアやモビリティサービスへの取り組み")
    if any(keyword in lowered for keyword in ("semiconductor", "chip", "foundry")):
        domains.append("半導体・電子部品関連事業")
    if any(keyword in lowered for keyword in ("cloud", "saas", "platform")):
        domains.append("ソフトウェア・クラウド関連事業")
    if any(keyword in lowered for keyword in ("bank", "insurance", "financial services")):
        domains.append("金融サービス関連事業")
    if any(keyword in lowered for keyword in ("pharmaceutical", "drug", "medical")):
        domains.append("医薬品・ヘルスケア関連事業")
    if any(keyword in lowered for keyword in ("retail", "store", "e-commerce")):
        domains.append("小売・EC関連事業")
    if not domains:
        return ""
    unique_domains = list(dict.fromkeys(domains))[:3]
    return (
        "外部データでは、"
        f"{'、'.join(unique_domains)}が確認できます。"
        "公式IRで事業セグメント、主要市場、収益源を確認してください。"
    )


def _research_fact_segment_labels(text: str) -> list[str]:
    segment_specs = (
        (
            "自動車・モビリティ",
            ("自動車", "モビリティ", "車両", "automotive", "vehicle"),
        ),
        ("ソフトウェア・サービス", ("ソフトウェア", "サービス", "software", "service")),
        ("半導体・電子部品", ("半導体", "電子部品", "semiconductor", "chip")),
        ("金融サービス", ("金融", "bank", "insurance", "financial services")),
        ("医薬品・ヘルスケア", ("医薬品", "ヘルスケア", "pharmaceutical", "medical")),
        ("小売・EC", ("小売", "EC", "retail", "e-commerce")),
    )
    lowered = text.lower()
    segments: list[str] = []
    for label, keywords in segment_specs:
        if any(keyword.lower() in lowered for keyword in keywords):
            segments.append(label)
    return list(dict.fromkeys(segments))


def _research_fact_region_labels(text: str) -> list[str]:
    region_specs = (
        ("日本", ("日本", "国内", "japan", "jp")),
        (
            "北米",
            (
                "北米",
                "米国",
                "アメリカ",
                "north america",
                "united states",
                "u.s.",
                "us",
            ),
        ),
        ("欧州", ("欧州", "ヨーロッパ", "europe", "eu")),
        ("中国", ("中国", "china")),
        ("アジア", ("アジア", "asia", "asean", "インド", "india")),
        ("海外", ("海外", "グローバル", "global", "overseas", "international")),
    )
    return _research_fact_labels_from_keywords(text, region_specs)


def _research_fact_revenue_driver_labels(text: str) -> list[str]:
    driver_specs = (
        (
            "製品・車両販売",
            (
                "販売",
                "売上",
                "車両",
                "vehicle sales",
                "sells vehicles",
                "product sales",
            ),
        ),
        (
            "ソフトウェア・サービス",
            ("ソフトウェア", "サービス", "software", "services", "subscription"),
        ),
        (
            "金融サービス",
            ("金融", "リース", "financial services", "leasing", "finance"),
        ),
        ("部品・保守", ("部品", "保守", "parts", "maintenance", "aftermarket")),
        (
            "海外売上",
            ("海外売上", "overseas sales", "international sales", "global sales"),
        ),
    )
    return _research_fact_labels_from_keywords(text, driver_specs)


def _research_fact_labels_from_keywords(
    text: str,
    specs: Sequence[tuple[str, Sequence[str]]],
) -> list[str]:
    lowered = text.lower()
    labels: list[str] = []
    for label, keywords in specs:
        if any(keyword.lower() in lowered for keyword in keywords):
            labels.append(label)
    return list(dict.fromkeys(labels))


def _research_fact_label_items_from_sources(
    *,
    label: str,
    report: CompanyResearchReport,
    overview_items: Sequence[ResearchFactItem],
    extractor: Callable[[str], list[str]],
) -> list[ResearchFactItem]:
    items: list[ResearchFactItem] = []
    for item in overview_items:
        labels = extractor(item.value)
        if labels:
            items.append(
                ResearchFactItem(
                    label=label,
                    value="、".join(labels[:4]),
                    source_title=item.source_title,
                    source_type=item.source_type,
                    source_confidence=item.source_confidence,
                    published_at=item.published_at,
                    note=item.note,
                )
            )
    for row in _research_brief_prioritized_business_evidence(report):
        labels = extractor(_research_brief_evidence_text(row))
        if not labels:
            continue
        items.append(
            ResearchFactItem(
                label=label,
                value="、".join(labels[:4]),
                source_title=row.title,
                source_type=row.source_type,
                source_confidence=_research_brief_source_confidence(row.source_type),
                published_at=row.published_at,
                note=_research_fact_source_note(row.source_type),
            )
        )
    return _unique_research_fact_items(items)


def _research_fact_sentence_items(
    report: CompanyResearchReport,
    *,
    label: str,
    keywords: Sequence[str],
    source_note: str,
) -> list[ResearchFactItem]:
    items: list[ResearchFactItem] = []
    for row in _research_brief_prioritized_fact_evidence(report):
        sentence = _research_fact_sentence_for_keywords(
            _research_brief_evidence_text(row),
            keywords,
        )
        if not sentence:
            continue
        items.append(
            ResearchFactItem(
                label=label,
                value=sentence,
                source_title=row.title,
                source_type=row.source_type,
                source_confidence=_research_brief_source_confidence(row.source_type),
                published_at=row.published_at,
                note=source_note,
            )
        )
    return _unique_research_fact_items(items)


def _research_fact_sentence_for_keywords(
    text: str,
    keywords: Sequence[str],
) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""
    chunks = [
        chunk.strip(" 　・-")
        for chunk in re.split(r"(?<=[。.!?])\s+|[。\n\r;；]", normalized)
        if chunk.strip()
    ]
    lowered_chunks = [(chunk, chunk.lower()) for chunk in (chunks or [normalized])]
    for keyword in (keyword.lower() for keyword in keywords):
        for chunk, lowered in lowered_chunks:
            if keyword in lowered:
                return _clip_text(chunk, max_chars=130)
    return ""


def _research_brief_prioritized_fact_evidence(
    report: CompanyResearchReport,
) -> list[ResearchEvidence]:
    return [
        *[
            row
            for row in report.evidence
            if row.source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES
        ],
        *[row for row in report.evidence if row.source_type == "provider_profile"],
        *[row for row in report.evidence if row.source_type == "news"],
        *report.evidence,
    ]


def _research_fact_event_value(title: str, source_type: ResearchSourceType) -> str:
    source_label = _research_brief_source_type_label(source_type)
    return f"{source_label}「{_clip_text(title, max_chars=72)}」を確認しました。"


def _research_fact_source_note(source_type: ResearchSourceType) -> str:
    if source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES:
        return "公式資料・開示由来の確認材料です。"
    if source_type == "provider_profile":
        return "外部データ由来の補助情報です。公式資料で裏取りしてください。"
    if source_type == "news":
        return "ニュース由来の補助情報です。公式発表と合わせて確認してください。"
    return "確認材料として扱い、必要に応じて一次情報で裏取りしてください。"


def _unique_research_fact_items(
    items: Sequence[ResearchFactItem],
) -> list[ResearchFactItem]:
    unique: list[ResearchFactItem] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in items:
        key = (item.label, item.value, item.source_title, item.source_type)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _unique_research_missing_items(
    items: Sequence[ResearchMissingItem],
) -> list[ResearchMissingItem]:
    unique: list[ResearchMissingItem] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.category, item.label, item.reason)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _looks_mostly_english(text: str) -> bool:
    letters = sum(1 for char in text if char.isascii() and char.isalpha())
    japanese = sum(
        1 for char in text if "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff"
    )
    return letters > japanese * 2 and letters > 20


def _research_brief_positive_candidates(
    report: CompanyResearchReport,
    news_report: StockNewsReport | None,
) -> list[str]:
    return [
        material.summary for material in _research_brief_positive_materials(report, news_report)
    ]


def _research_brief_positive_materials(
    report: CompanyResearchReport,
    news_report: StockNewsReport | None,
) -> list[ResearchBriefMaterial]:
    materials = [
        _research_brief_material_from_point(point)
        for point in report.points
        if point.category in {"growth", "shareholder_return", "financial_safety"} and point.evidence
    ]
    if news_report is not None:
        materials.extend(
            _research_brief_material_from_news(row, label="ニュース")
            for row in news_report.news
            if row.sentiment_for_investment == "positive"
        )
    return _unique_research_brief_materials(materials)[:5]


def _research_brief_caution_candidates(
    report: CompanyResearchReport,
    news_report: StockNewsReport | None,
) -> list[str]:
    return [material.summary for material in _research_brief_caution_materials(report, news_report)]


def _research_brief_caution_materials(
    report: CompanyResearchReport,
    news_report: StockNewsReport | None,
) -> list[ResearchBriefMaterial]:
    materials = [
        _research_brief_material_from_point(point)
        for point in report.points
        if point.category == "business_risk" and point.evidence
    ]
    if news_report is not None:
        materials.extend(
            _research_brief_material_from_news(row, label="ニュース")
            for row in news_report.news
            if row.sentiment_for_investment in {"negative", "mixed", "unknown"}
        )
    return _unique_research_brief_materials(materials)[:6]


def _research_brief_material_from_point(
    point: ResearchSummaryPoint,
) -> ResearchBriefMaterial:
    evidence = _dedupe_evidence(point.evidence)
    lead = evidence[0]
    return ResearchBriefMaterial(
        label=point.label,
        summary=_research_brief_point_candidate(point),
        source_title=lead.title,
        source_type=lead.source_type,
        source_confidence=_research_brief_source_confidence(lead.source_type),
        source_count=len(evidence),
        published_at=lead.published_at,
    )


def _research_brief_material_from_news(
    row: StockNewsEvidence,
    *,
    label: str,
) -> ResearchBriefMaterial:
    title = _clip_text(row.title, max_chars=60)
    summary = _clip_text(row.summary, max_chars=100)
    return ResearchBriefMaterial(
        label=label,
        summary=f"ニュース: 「{title}」を確認しました。要約: {summary}",
        source_title=row.title,
        source_type="news",
        source_confidence=_research_brief_source_confidence("news"),
        source_count=1,
        published_at=row.published_at,
    )


def _unique_research_brief_materials(
    materials: Sequence[ResearchBriefMaterial],
) -> list[ResearchBriefMaterial]:
    unique: list[ResearchBriefMaterial] = []
    seen: set[tuple[str, str, str]] = set()
    for material in materials:
        key = (material.summary, material.source_title, material.source_type)
        if key in seen:
            continue
        seen.add(key)
        unique.append(material)
    return unique


def _research_brief_point_candidate(point: ResearchSummaryPoint) -> str:
    evidence = _dedupe_evidence(point.evidence)
    if not evidence:
        return f"{point.label}: まだ十分な根拠がありません。追加資料で確認してください。"
    lead = evidence[0]
    themes = _research_brief_topic_terms(point.category, lead.excerpt)
    theme_text = "、".join(themes[:3]) if themes else _research_brief_topic_focus(point.category)
    published = lead.published_at.isoformat() if lead.published_at else "日付未設定"
    source_type = _research_brief_source_type_label(lead.source_type)
    return (
        f"{point.label}: {theme_text}に関する記述を{len(evidence)}件確認しました。"
        f"主な出典は{source_type}「{lead.title}」（{published}）です。"
    )


def _research_brief_topic_terms(
    category: ResearchTopicCategory,
    text: str,
) -> list[str]:
    lowered = text.lower()
    term_specs: dict[ResearchTopicCategory, tuple[tuple[str, tuple[str, ...]], ...]] = {
        "growth": (
            ("成長戦略", ("成長戦略", "growth strategy", "growth")),
            ("売上・収益拡大", ("売上", "収益", "revenue", "sales")),
            ("新規事業", ("新規事業", "new business", "software", "service")),
        ),
        "shareholder_return": (
            ("配当", ("配当", "dividend")),
            ("自社株買い", ("自社株買い", "buyback")),
            ("株主還元方針", ("株主還元", "shareholder return", "payout")),
        ),
        "financial_safety": (
            ("現金・流動性", ("cash", "liquidity", "キャッシュ", "現金")),
            ("負債・資本構成", ("debt", "equity", "有利子負債", "自己資本")),
            ("財務安全性", ("財務安全性", "balance sheet")),
        ),
        "business_risk": (
            ("供給制約", ("供給制約", "supply", "supply chain")),
            ("為替変動", ("為替", "foreign exchange")),
            ("規制・競争環境", ("regulation", "competition", "規制", "競争")),
        ),
        "confirmation_gap": (
            ("確認不足", ("確認不足", "根拠不足", "missing")),
            ("資料鮮度", ("鮮度", "stale")),
            ("追加確認", ("追加確認", "additional confirmation")),
        ),
    }
    terms: list[str] = []
    for label, keywords in term_specs.get(category, ()):
        if any(keyword.lower() in lowered for keyword in keywords):
            terms.append(label)
    return terms


def _research_brief_topic_focus(category: ResearchTopicCategory) -> str:
    labels: dict[ResearchTopicCategory, str] = {
        "growth": "成長・収益拡大",
        "shareholder_return": "配当・株主還元",
        "financial_safety": "財務安全性",
        "business_risk": "事業リスク",
        "confirmation_gap": "資料面の確認不足",
    }
    return labels.get(category, "確認材料")


def _research_brief_source_type_label(source_type: ResearchSourceType) -> str:
    labels: dict[ResearchSourceType, str] = {
        "annual_report": "有価証券報告書",
        "earnings_report": "決算短信",
        "earnings_presentation": "決算説明資料",
        "medium_term_plan": "中期経営計画",
        "integrated_report": "統合報告書",
        "company_ir": "企業IRサイト",
        "tdnet": "適時開示",
        "provider_profile": "取得元プロフィール",
        "news": "ニュース",
        "user_note": "ユーザーメモ",
    }
    return labels[source_type]


def _research_brief_confirmation_gaps(
    report: CompanyResearchReport,
    missing_metrics: Sequence[str],
    *,
    news_report: StockNewsReport | None,
) -> list[str]:
    gaps = list(report.data_quality.warnings)
    gaps.extend(
        missing for claim in report.extracted_claims for missing in claim.missing_information
    )
    if news_report is not None:
        gaps.extend(f"ニュース確認: {warning}" for warning in news_report.warnings)
    if missing_metrics:
        gaps.append(f"未確認の定量指標: {'、'.join(missing_metrics[:8])}")
    return _unique_text(gaps)[:8]


def _research_brief_next_actions(
    report: CompanyResearchReport,
    missing_metrics: Sequence[str],
    *,
    external_research_result: ExternalResearchFetchResult | None,
) -> list[str]:
    actions: list[str] = []
    if missing_metrics:
        actions.append("決算短信・有価証券報告書・公式IRで未確認の定量指標を確認します。")
    if not any(
        row.source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES for row in report.evidence
    ):
        actions.append("公式資料やTDnet開示で、外部データとニュースの裏取りをします。")
    if any("鮮度" in warning or "2年以上" in warning for warning in report.data_quality.warnings):
        actions.append("最新の決算資料、適時開示、ニュースで情報の鮮度を確認します。")
    if external_research_result is not None and external_research_result.warnings:
        actions.append("外部取得の警告を確認し、取得できなかった資料を個別に確認します。")
    actions.append("出典カードの資料名、公開日、URL、情報源信頼度を確認します。")
    return _unique_text(actions)[:5]


def _research_brief_source_cards(
    report: CompanyResearchReport,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> list[ResearchBriefSourceCard]:
    cards: dict[tuple[str, str, str], ResearchBriefSourceCard] = {}
    for evidence in report.evidence:
        published_at = evidence.published_at.isoformat() if evidence.published_at else ""
        key = (evidence.title, evidence.source_type, published_at)
        cards.setdefault(
            key,
            ResearchBriefSourceCard(
                title=evidence.title,
                source_type=evidence.source_type,
                published_at=evidence.published_at,
                source_confidence=_research_brief_source_confidence(evidence.source_type),
                note="検索で確認した根拠資料です。",
            ),
        )

    if news_report is not None:
        for news in news_report.news:
            key = (news.title, "news", news.url)
            cards.setdefault(
                key,
                ResearchBriefSourceCard(
                    title=news.title,
                    source_type="news",
                    provider=news.source,
                    source_url=news.url,
                    published_at=news.published_at,
                    freshness_status=news.freshness_status,
                    source_confidence=_research_brief_source_confidence("news"),
                    note="URL付きニュースとして確認した材料です。",
                ),
            )

    if external_research_result is not None:
        for entry in external_research_result.entries:
            key = (entry.title, entry.source_type, entry.source_url)
            cards.setdefault(
                key,
                ResearchBriefSourceCard(
                    title=entry.title,
                    source_type=entry.source_type,
                    provider=entry.provider,
                    source_url=entry.source_url,
                    published_at=entry.published_at,
                    fetched_at=entry.fetched_at,
                    freshness_status=entry.freshness_status,
                    source_confidence=_research_brief_source_confidence(entry.source_type),
                    note="AI調査で一時参照した外部ソースです。",
                ),
            )
    return list(cards.values())


def _research_brief_memo(
    report: CompanyResearchReport,
    metrics: Sequence[ResearchMetric],
    source_cards: Sequence[ResearchBriefSourceCard],
    *,
    fact_summary: ResearchFactSummary | None = None,
) -> str:
    if report.data_quality.evidence_count <= 0:
        return (
            "現時点で確認できた根拠資料が少ないため、Research Summary は未確認メモとして"
            "扱います。売買推奨ではなく、追加で確認する資料を整理するための表示です。"
        )
    overview_summary = ""
    if fact_summary is not None and fact_summary.business_overview:
        overview_summary = _clip_text(fact_summary.business_overview[0].value, max_chars=86)
    metric_summary = "主要な定量指標はまだ抽出できていません。"
    if metrics:
        metric_pairs = [f"{metric.label} {metric.value}" for metric in metrics[:4]]
        metric_summary = f"確認できた主な数値は{'、'.join(metric_pairs)}です。"
        if len(metrics) > 4:
            metric_summary += f"ほか{len(metrics) - 4}指標は定量指標カードで確認できます。"
    caution = (
        "注意点があります。" if report.data_quality.warnings else "大きな資料警告はありません。"
    )
    source_context = ""
    if source_cards:
        high_source_count = sum(1 for card in source_cards if card.source_confidence == "high")
        source_context = (
            "公式資料を含む根拠から整理しています。"
            if high_source_count
            else "外部データ・ニュース中心のため、公式資料で裏取りしてください。"
        )
    if overview_summary:
        return (
            f"{overview_summary} {metric_summary}{caution}{source_context}"
            "売買推奨ではありません。"
        )
    return (
        f"事業概要・主要数値・材料候補・確認不足を整理しました。{metric_summary}{caution}"
        f"{source_context}"
        "売買推奨ではありません。"
    )


def _company_research_normalized_evidence(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> list[CompanyResearchEvidence]:
    evidence: list[CompanyResearchEvidence] = []
    for row in report.evidence:
        body = _research_brief_evidence_text(row)
        evidence.append(
            CompanyResearchEvidence(
                kind=_company_research_evidence_kind(row.source_type, row.title, body),
                title=row.title,
                body=body,
                source_type=row.source_type,
                source_title=row.title,
                reliability=_company_research_reliability(row.source_type),
                information_status="found",
                published_at=row.published_at,
                extracted_keywords=_company_research_extracted_keywords(body),
            )
        )
    for metric in brief.metrics:
        evidence.append(
            CompanyResearchEvidence(
                kind="financial_metric",
                title=metric.label,
                body=f"{metric.label}: {metric.value}",
                source_type=metric.source_type,
                source_title=metric.source_title,
                reliability=_company_research_reliability(metric.source_type),
                information_status="found",
                extracted_keywords=[metric.label],
            )
        )
    if news_report is not None:
        for news in news_report.news:
            evidence.append(
                CompanyResearchEvidence(
                    kind="news",
                    title=news.title,
                    body=news.summary,
                    source_type="news",
                    source_title=news.source or news.title,
                    source_url=news.url,
                    reliability="news",
                    information_status="unverified",
                    published_at=news.published_at,
                    extracted_keywords=_company_research_extracted_keywords(
                        f"{news.title} {news.summary}"
                    ),
                )
            )
    if external_research_result is not None:
        for entry in external_research_result.entries:
            body = entry.content_summary.strip()
            evidence.append(
                CompanyResearchEvidence(
                    kind=_company_research_evidence_kind(entry.source_type, entry.title, body),
                    title=entry.title,
                    body=body,
                    source_type=entry.source_type,
                    source_title=entry.provider,
                    source_url=entry.source_url,
                    reliability=_company_research_reliability(entry.source_type),
                    information_status=_company_research_external_information_status(
                        entry.source_type,
                        body,
                    ),
                    published_at=entry.published_at,
                    extracted_keywords=_company_research_extracted_keywords(
                        f"{entry.title} {body}"
                    ),
                )
            )
    return _unique_company_research_evidence(evidence)


def _company_research_overview_summary(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    normalized_evidence: Sequence[CompanyResearchEvidence],
    news_report: StockNewsReport | None,
) -> CompanyOverviewSummary:
    fact_summary = brief.fact_summary
    business_profile = _company_research_business_profile(
        report,
        brief,
        normalized_evidence=normalized_evidence,
        news_report=news_report,
    )
    overview_items = list(fact_summary.business_overview if fact_summary else [])
    segment_items = list(fact_summary.business_segments if fact_summary else [])
    region_items = list(fact_summary.business_regions if fact_summary else [])
    revenue_items = list(fact_summary.revenue_drivers if fact_summary else [])
    recent_items = list(fact_summary.recent_events if fact_summary else [])
    company_name = business_profile.company_name or (
        news_report.company_name if news_report is not None and news_report.company_name else ""
    )
    business_overview = business_profile.business_summary or (
        overview_items[0].value
        if overview_items
        else (
            "企業概要は外部プロフィールから一部確認できますが、主力事業や収益構造は"
            "公式資料で追加確認が必要です。"
        )
    )
    business_segments = business_profile.main_businesses or _company_research_values(
        segment_items or revenue_items,
        limit=4,
    )
    regions = business_profile.regions or _company_research_values(region_items, limit=4)
    scale_summary = _company_research_scale_summary(
        brief,
        normalized_evidence=normalized_evidence,
    )
    recent_focus = _company_research_recent_focus(recent_items, news_report=news_report)
    source_items = [
        *overview_items,
        *segment_items,
        *region_items,
        *revenue_items,
        *recent_items,
    ]
    source_types = [item.source_type for item in source_items]
    source_types.extend(row.source_type for row in report.evidence[:3])
    return CompanyOverviewSummary(
        company_name=company_name or "",
        symbol=report.symbol,
        business_profile=business_profile,
        industry=business_profile.industry,
        sector=business_profile.sector,
        business_overview=_clip_text(business_overview, max_chars=220),
        main_businesses=business_segments,
        business_segments=business_segments,
        supporting_businesses=business_profile.supporting_businesses,
        products_services=business_profile.products_services,
        products_services_status=business_profile.products_services_status,
        regions=regions,
        customer_segments=business_profile.customer_segments,
        scale_summary=scale_summary,
        recent_focus=recent_focus,
        information_status=business_profile.information_status,
        evidence_level=(
            business_profile.evidence_level
            if business_profile.evidence_level != "missing"
            else _company_research_evidence_level_from_source_types(source_types)
        ),
        source_titles=_unique_text(
            [
                *business_profile.source_titles,
                *[item.source_title for item in source_items if item.source_title.strip()],
                *[row.title for row in report.evidence[:3]],
            ]
        )[:5],
    )


def _company_research_business_profile(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    normalized_evidence: Sequence[CompanyResearchEvidence],
    news_report: StockNewsReport | None,
) -> CompanyBusinessProfile:
    fact_summary = brief.fact_summary
    overview_items = [
        item
        for item in list(fact_summary.business_overview if fact_summary else [])
        if item.source_type != "news"
    ]
    segment_items = [
        item
        for item in list(fact_summary.business_segments if fact_summary else [])
        if item.source_type != "news"
    ]
    region_items = [
        item
        for item in list(fact_summary.business_regions if fact_summary else [])
        if item.source_type != "news"
    ]
    revenue_items = [
        item
        for item in list(fact_summary.revenue_drivers if fact_summary else [])
        if item.source_type != "news"
    ]
    profile_evidence = [
        item
        for item in normalized_evidence
        if item.kind in {"company_profile", "business_description"}
        and item.reliability != "news"
        and item.body.strip()
    ]
    profile_text = "\n".join(
        [
            *[item.value for item in overview_items],
            *[item.value for item in segment_items],
            *[item.value for item in revenue_items],
            *[item.body for item in profile_evidence],
        ]
    )
    profile_raw_text = "\n".join(item.body for item in profile_evidence)
    business_summary = (
        overview_items[0].value
        if overview_items
        else _company_research_business_summary_from_text(profile_text)
    )
    source_types: list[str] = [
        item.source_type for item in overview_items + segment_items + revenue_items
    ]
    source_types.extend(item.source_type for item in profile_evidence)
    company_name = _company_research_profile_field(profile_text, "Company Name") or (
        news_report.company_name if news_report is not None and news_report.company_name else ""
    )
    main_businesses = _unique_text(
        [
            *_company_research_business_terms(profile_text),
            *_company_research_values(segment_items or revenue_items, limit=6),
        ]
    )[:5]
    main_businesses = _company_research_filter_main_businesses(profile_text, main_businesses)
    supporting_businesses = _company_research_supporting_business_terms(
        profile_text,
        main_businesses=main_businesses,
    )
    supporting_businesses = _company_research_filter_supporting_businesses(
        profile_text,
        supporting_businesses,
        main_businesses=main_businesses,
    )
    products_services = _company_research_products_services(profile_raw_text or profile_text)
    products_services_status: InformationStatus = "found" if products_services else "missing"
    if not products_services:
        products_services = _company_research_inferred_products_services(
            profile_text,
            main_businesses=main_businesses,
            supporting_businesses=supporting_businesses,
        )
        products_services_status = "unverified" if products_services else "missing"
    regions = _unique_text(
        [
            *_company_research_values(region_items, limit=6),
            *_company_research_regions_from_text(profile_text),
        ]
    )[:6]
    customer_segments = _company_research_customer_segments(profile_text)
    information_status: InformationStatus = (
        "found" if business_summary or main_businesses else "missing"
    )
    evidence_level = _company_research_evidence_level_from_source_types(source_types)
    return CompanyBusinessProfile(
        company_name=company_name or "",
        symbol=report.symbol,
        industry=_company_research_profile_field(profile_text, "Industry"),
        sector=_company_research_profile_field(profile_text, "Sector"),
        business_summary=_company_research_natural_business_summary(
            business_summary,
            company_name=company_name or report.symbol,
            main_businesses=main_businesses,
            supporting_businesses=supporting_businesses,
            products_services=products_services,
            regions=regions,
            evidence_level=evidence_level,
        ),
        main_businesses=main_businesses,
        supporting_businesses=supporting_businesses,
        products_services=products_services,
        products_services_status=products_services_status,
        regions=regions,
        customer_segments=customer_segments,
        information_status=information_status,
        evidence_level=evidence_level,
        source_titles=_unique_text(
            [
                *[item.source_title for item in overview_items + segment_items + revenue_items],
                *[item.title for item in profile_evidence],
            ]
        )[:5],
    )


def _company_research_quantitative_summary(
    brief: ResearchBrief,
    *,
    normalized_evidence: Sequence[CompanyResearchEvidence],
) -> QuantitativeSummary:
    metrics = {metric.key: metric for metric in brief.metrics}
    field_specs: tuple[
        tuple[str, str, ResearchMetricKey | None, tuple[str, ...]],
        ...,
    ] = (
        (
            "revenue",
            "売上高",
            "revenue",
            (
                r"売上(?:高|収益)?",
                r"total revenue",
                r"totalRevenue",
                r"revenue",
                r"sales",
            ),
        ),
        (
            "operating_profit",
            "営業利益",
            "operating_income",
            (r"営業利益", r"operating income", r"operatingIncome"),
        ),
        (
            "net_income",
            "純利益",
            "net_income",
            (
                r"純利益",
                r"当期利益",
                r"net income to common",
                r"netIncomeToCommon",
                r"netIncome",
                r"net income",
                r"net profit",
            ),
        ),
        (
            "eps",
            "EPS",
            "eps",
            (
                r"EPS",
                r"trailing eps",
                r"forward eps",
                r"trailingEps",
                r"forwardEps",
                r"1株当たり(?:利益|当期利益)",
                r"earnings per share",
            ),
        ),
        (
            "per",
            "PER",
            "per",
            (r"PER", r"trailing PE", r"forward PE", r"trailingPE", r"forwardPE"),
        ),
        ("pbr", "PBR", "pbr", (r"PBR", r"price[- ]to[- ]book", r"priceToBook")),
        ("roe", "ROE", "roe", (r"ROE", r"return on equity", r"returnOnEquity")),
        (
            "dividend_yield",
            "配当利回り",
            "dividend",
            (r"配当(?:金|利回り)?", r"dividend yield", r"dividendYield"),
        ),
        (
            "market_cap",
            "時価総額",
            "market_cap",
            (r"時価総額", r"market cap(?:italization)?", r"marketCap"),
        ),
        (
            "enterprise_value",
            "企業価値",
            None,
            (r"企業価値", r"enterprise value", r"enterpriseValue"),
        ),
        (
            "employee_count",
            "従業員数",
            None,
            (r"従業員数", r"employees", r"full time employees", r"fullTimeEmployees"),
        ),
    )
    values: dict[str, str | None] = {}
    source_titles: list[str] = []
    source_types: list[str] = []
    for key, _label, metric_key, patterns in field_specs:
        value, titles, types = _company_research_quantitative_field_value(
            key,
            metrics,
            metric_key,
            normalized_evidence,
            patterns,
        )
        values[key] = value
        source_titles.extend(titles)
        source_types.extend(types)

    missing_items = [label for key, label, _metric_key, _patterns in field_specs if not values[key]]
    found_items = [
        f"{label} {values[key]}"
        for key, label, _metric_key, _patterns in field_specs
        if values[key]
    ]
    if found_items:
        summary = f"確認できた主要指標は{'、'.join(found_items[:5])}です。"
        if missing_items:
            summary += f"{'、'.join(missing_items[:5])}は追加確認が必要です。"
    else:
        summary = "主要な財務指標が未取得のため、業績トレンドや規模感の把握には追加確認が必要です。"
    return QuantitativeSummary(
        revenue=values["revenue"],
        operating_profit=values["operating_profit"],
        net_income=values["net_income"],
        eps=values["eps"],
        per=values["per"],
        pbr=values["pbr"],
        roe=values["roe"],
        dividend_yield=values["dividend_yield"],
        market_cap=values["market_cap"],
        enterprise_value=values["enterprise_value"],
        employee_count=values["employee_count"],
        summary=summary,
        missing_items=missing_items,
        item_statuses={key: "found" if value else "missing" for key, value in values.items()},
        information_status="found" if found_items else "missing",
        evidence_level=_company_research_evidence_level_from_source_types(source_types),
        source_titles=_unique_text(source_titles)[:5],
    )


def _company_research_ir_items(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    normalized_evidence: Sequence[CompanyResearchEvidence],
    external_research_result: ExternalResearchFetchResult | None,
) -> list[IRSummaryItem]:
    specs: tuple[
        tuple[str, IRDocumentType, tuple[ResearchSourceType, ...], tuple[str, ...]],
        ...,
    ] = (
        (
            "決算短信",
            "earnings_summary",
            ("earnings_report",),
            ("決算短信", "financial results"),
        ),
        (
            "決算説明資料",
            "earnings_presentation",
            ("earnings_presentation",),
            ("決算説明", "presentation", "briefing"),
        ),
        (
            "有価証券報告書",
            "annual_report",
            ("annual_report", "integrated_report"),
            ("有価証券報告書", "annual securities report", "annual report"),
        ),
        (
            "公式IRサイト",
            "other",
            ("company_ir",),
            ("IR", "investor relations", "投資家", "株主"),
        ),
        (
            "適時開示",
            "timely_disclosure",
            ("tdnet",),
            ("適時開示", "TDnet", "timely disclosure"),
        ),
        (
            "中期経営計画",
            "medium_term_plan",
            ("medium_term_plan",),
            ("中期経営計画", "medium-term"),
        ),
        (
            "配当・自社株買い",
            "shareholder_return",
            ("earnings_report", "tdnet"),
            ("配当", "自己株式", "自社株買い", "株主還元", "dividend", "buyback"),
        ),
        (
            "業績予想修正",
            "forecast_revision",
            ("tdnet", "earnings_report"),
            ("業績予想修正", "上方修正", "下方修正", "forecast revision"),
        ),
    )
    cards = list(brief.source_cards)
    if external_research_result is not None:
        cards.extend(
            ResearchBriefSourceCard(
                title=entry.title,
                source_type=entry.source_type,
                provider=entry.provider,
                source_url=entry.source_url,
                published_at=entry.published_at,
                fetched_at=entry.fetched_at,
                freshness_status=entry.freshness_status,
                source_confidence=_research_brief_source_confidence(entry.source_type),
                note=entry.content_summary,
            )
            for entry in external_research_result.entries
        )
    return [
        _company_research_ir_item_for_spec(
            document_type=document_type,
            ir_document_type=ir_document_type,
            source_types=source_types,
            keywords=keywords,
            report=report,
            brief=brief,
            cards=cards,
            normalized_evidence=normalized_evidence,
        )
        for document_type, ir_document_type, source_types, keywords in specs
    ]


def _company_research_news_items(
    brief: ResearchBrief,
    *,
    normalized_evidence: Sequence[CompanyResearchEvidence],
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> list[NewsSummaryItem]:
    items: list[NewsSummaryItem] = []
    if news_report is not None:
        for news in news_report.news:
            topic_text = f"{news.title} {news.summary}"
            items.append(
                NewsSummaryItem(
                    topic_type=_company_research_latest_topic_type("news", topic_text),
                    title=news.title,
                    summary=_company_research_latest_topic_summary(
                        source_type="news",
                        title=news.title,
                        raw_summary=news.summary,
                        information_status="unverified",
                    ),
                    published_at=news.published_at,
                    source_title=news.source or news.title,
                    source_url=news.url,
                    impact_hint=_company_research_news_impact_hint(
                        news.investment_viewpoint,
                        topic_text,
                    ),
                    official_confirmation_required=True,
                    information_status="unverified",
                    evidence_level="low",
                )
            )
    if brief.fact_summary is not None:
        for item in brief.fact_summary.recent_events:
            if item.source_type not in {"news", "tdnet"}:
                continue
            is_tdnet = item.source_type == "tdnet"
            topic_type = _company_research_latest_topic_type(
                item.source_type,
                f"{item.source_title} {item.value}",
            )
            items.append(
                NewsSummaryItem(
                    topic_type=topic_type,
                    title=item.source_title,
                    summary=_company_research_latest_topic_summary(
                        source_type=item.source_type,
                        title=item.source_title,
                        raw_summary=item.value,
                        information_status="unparsed" if is_tdnet else "unverified",
                    ),
                    published_at=item.published_at,
                    source_title=item.source_title,
                    impact_hint=_company_research_news_impact_hint(
                        "other",
                        f"{item.source_title} {item.value}",
                        source_type=item.source_type,
                    ),
                    official_confirmation_required=not is_tdnet,
                    information_status="unparsed" if is_tdnet else "unverified",
                    evidence_level="high" if is_tdnet else "low",
                )
            )
    if external_research_result is not None:
        for entry in external_research_result.entries:
            if entry.source_type not in {"news", "tdnet"}:
                continue
            is_tdnet = entry.source_type == "tdnet"
            topic_type = _company_research_latest_topic_type(
                entry.source_type,
                f"{entry.title} {entry.content_summary}",
            )
            default_summary = "" if is_tdnet else "外部ニュースを確認しています。"
            items.append(
                NewsSummaryItem(
                    topic_type=topic_type,
                    title=entry.title,
                    summary=_company_research_latest_topic_summary(
                        source_type=entry.source_type,
                        title=entry.title,
                        raw_summary=entry.content_summary or default_summary,
                        information_status="unparsed" if is_tdnet else "unverified",
                    ),
                    published_at=entry.published_at,
                    source_title=entry.provider,
                    source_url=entry.source_url,
                    impact_hint=_company_research_news_impact_hint(
                        "other",
                        f"{entry.title} {entry.content_summary}",
                        source_type=entry.source_type,
                    ),
                    official_confirmation_required=not is_tdnet,
                    information_status="unparsed" if is_tdnet else "unverified",
                    evidence_level="high" if is_tdnet else "low",
                )
            )
    if not items:
        for evidence in normalized_evidence:
            if evidence.kind not in {"news", "tdnet_disclosure"}:
                continue
            is_tdnet = evidence.source_type == "tdnet"
            topic_type = _company_research_latest_topic_type(
                evidence.source_type,
                f"{evidence.title} {evidence.body}",
            )
            items.append(
                NewsSummaryItem(
                    topic_type=topic_type,
                    title=evidence.title,
                    summary=_company_research_latest_topic_summary(
                        source_type=evidence.source_type,
                        title=evidence.title,
                        raw_summary=(evidence.body if evidence.body or not is_tdnet else ""),
                        information_status=(
                            evidence.information_status if is_tdnet else "unverified"
                        ),
                    ),
                    published_at=evidence.published_at,
                    source_title=evidence.source_title,
                    source_url=evidence.source_url,
                    impact_hint=_company_research_news_impact_hint(
                        "other",
                        f"{evidence.title} {evidence.body}",
                        source_type=evidence.source_type,
                    ),
                    official_confirmation_required=not is_tdnet,
                    information_status=(evidence.information_status if is_tdnet else "unverified"),
                    evidence_level="high" if is_tdnet else "low",
                )
            )
    return _unique_company_news_items(items)[:5]


def _company_research_latest_topic_summary(
    *,
    source_type: ResearchSourceType | str,
    title: str,
    raw_summary: str,
    information_status: InformationStatus,
) -> str:
    cleaned = _research_user_facing_text(raw_summary)
    title_cleaned = _research_user_facing_text(title)
    detail = _company_research_non_repeating_topic_detail(
        title=title_cleaned,
        summary=cleaned,
    )
    topic_type = _company_research_latest_topic_type(source_type, f"{title} {raw_summary}")
    meaning = _company_research_latest_topic_meaning(topic_type)
    if source_type == "tdnet":
        detail_phrase = f" 内容メモ: {detail}" if detail else ""
        parse_note = (
            "本文未解析のため、詳細はリンク先で確認してください。"
            if information_status == "unparsed"
            else "詳細はリンク先で確認してください。"
        )
        return _clip_text(
            "概要: 公式開示として取得済みです。会社発表ベースの開示資料です。"
            f"{detail_phrase} 企業理解上の意味: {meaning} "
            f"追加確認: {parse_note}",
            max_chars=220,
        )
    if source_type == "news":
        detail_phrase = f" 内容メモ: {detail}" if detail else ""
        return _clip_text(
            "概要: 外部ニュースとして取得されています。"
            f"{detail_phrase} 企業理解上の意味: {meaning} "
            "追加確認: 業績影響や公式発表との整合性は、IR資料で確認してください。"
            "公式IRで確認が必要です。",
            max_chars=240,
        )
    if detail:
        return _clip_text(
            f"概要: 外部情報として取得されています。内容メモ: {detail} "
            f"企業理解上の意味: {meaning} 追加確認: 詳細は出典リンクで確認してください。",
            max_chars=220,
        )
    if cleaned:
        return _clip_text(cleaned, max_chars=180)
    return "外部情報として取得されています。詳細は出典リンクで確認してください。"


def _company_research_non_repeating_topic_detail(*, title: str, summary: str) -> str:
    cleaned = re.sub(r"\bsummary\s*[:：]\s*", "", summary, flags=re.IGNORECASE)
    cleaned = re.sub(r"\burl\s*[:：]\s*\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .。")
    title_cleaned = re.sub(r"\s+", " ", title).strip(" .。")
    if not cleaned or cleaned == title_cleaned:
        return ""
    if title_cleaned and cleaned.replace(title_cleaned, "").strip(" .。、「」『』") == "":
        return ""
    if title_cleaned and title_cleaned in cleaned and len(cleaned) <= len(title_cleaned) + 32:
        return ""
    return _clip_text(cleaned, max_chars=92)


def _company_research_latest_topic_meaning(topic_type: LatestTopicType) -> str:
    labels = {
        "earnings": "決算・業績確認に関する情報です。",
        "forecast_revision": "業績予想の修正や会社計画に関する情報です。",
        "shareholder_return": "配当・自己株式取得など株主還元に関する情報です。",
        "business_reorganization": "事業再編、M&A、会社分割など事業構造に関する情報です。",
        "product": "製品・サービスや事業展開に関する情報です。",
        "governance": "ガバナンス、監査、訴訟、規制対応などに関する情報です。",
        "tdnet": "会社発表ベースの適時開示です。",
        "ir_disclosure": "公式IR・開示資料として確認する情報です。",
        "news": "市場材料または事業トピックとして確認する情報です。",
        "unknown": "企業理解の補助情報として確認するトピックです。",
    }
    return labels.get(topic_type, labels["unknown"])


def _company_research_ai_reading_notes(
    brief: ResearchBrief,
    insight: InvestmentInsight,
    *,
    quantitative: QuantitativeSummary,
    ir_items: Sequence[IRSummaryItem],
    news_items: Sequence[NewsSummaryItem],
) -> list[str]:
    notes: list[str] = []
    if brief.business_overview:
        notes.append(f"確認できたこと: {_clip_text(brief.business_overview, max_chars=110)}")
    if quantitative.missing_items:
        notes.append(
            "不足している情報: "
            f"{'、'.join(quantitative.missing_items[:6])}は追加確認が必要です。"
        )
    missing_ir = [item.document_type for item in ir_items if item.availability != "found"]
    if missing_ir:
        notes.append(
            "追加確認する資料: "
            f"{'、'.join(missing_ir[:5])}を公式IRまたはTDnetで確認してください。"
        )
    if news_items:
        notes.append(
            "最新ニュース・開示: ニュースや適時開示は事業・業績への影響を公式IRと合わせて確認します。"
        )
    elif not news_items:
        notes.append(
            "最新ニュース・開示: 業績や事業に直接影響しそうなニュース・開示は確認できていません。"
        )
    for gap in insight.confirmation_gaps[:2]:
        notes.append(f"注意して読む情報: {_clip_text(gap, max_chars=110)}")
    return _unique_text(notes)[:6]


def _company_research_missing_critical_items(
    overview: CompanyOverviewSummary,
    quantitative: QuantitativeSummary,
    ir_items: Sequence[IRSummaryItem],
    news_items: Sequence[NewsSummaryItem],
) -> list[str]:
    items: list[str] = []
    if overview.evidence_level == "missing":
        items.append("企業概要")
    if not news_items:
        items.append("直近ニュース・開示")
    items.extend(quantitative.missing_items[:8])
    items.extend(item.document_type for item in ir_items if item.availability != "found")
    return _unique_text(items)[:12]


def _security_research_detection_text(
    report: CompanyResearchReport,
    *,
    external_research_result: ExternalResearchFetchResult | None,
    metadata: Mapping[str, Any] | None,
) -> str:
    parts: list[str] = [report.symbol]
    if metadata:
        parts.extend(f"{key}: {value}" for key, value in metadata.items())
    parts.extend(_research_brief_evidence_text(row) for row in report.evidence)
    if external_research_result is not None:
        parts.extend(
            f"{entry.title}\nsource_type: {entry.source_type}\nprovider: {entry.provider}\n{entry.content_summary}"
            for entry in external_research_result.entries
        )
    return "\n".join(part for part in parts if str(part).strip())


def _security_research_metadata_value(text: str, *field_names: str) -> str:
    stop_labels = "|".join(
        re.escape(label)
        for label in (
            *_RESEARCH_BRIEF_RAW_PROVIDER_LABELS,
            "Fund Name",
            "Fund Family",
            "Asset Category",
            "Benchmark",
            "Expense Ratio",
            "AUM",
            "NAV",
            "Top Holdings",
            "Holdings",
            "Description",
            "Fund Objective",
        )
    )
    for field_name in field_names:
        escaped = re.escape(field_name)
        pattern = (
            rf"(?:^|\n|\b){escaped}\s*[:：]\s*" rf"(.*?)(?=\s+(?:{stop_labels})\s*[:：]|[\n\r,;]|$)"
        )
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        if match:
            value = _security_research_clean_metadata_value(match.group(1))
            if value:
                return value
    return ""


def _security_research_clean_metadata_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" .。")
    for label in (
        *_RESEARCH_BRIEF_RAW_PROVIDER_LABELS,
        "Fund Name",
        "Fund Family",
        "Asset Category",
        "Benchmark",
        "Expense Ratio",
        "AUM",
        "NAV",
        "Top Holdings",
        "Holdings",
        "Description",
        "Fund Objective",
    ):
        cleaned = re.sub(
            rf"\s*\b{re.escape(label)}\s*[:：].*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" .。")
    return _clip_text(_research_user_facing_text(cleaned), max_chars=120)


def _security_research_exchange_is_domestic(exchange: str) -> bool:
    return exchange.upper() in {"TSE", "TYO", "JPX", "TOKYO"}


def _security_research_exchange_is_foreign(exchange: str) -> bool:
    return exchange.upper() in {
        "NYSE",
        "NASDAQ",
        "AMEX",
        "NYSEARCA",
        "ARCA",
        "NMS",
        "NYQ",
        "NGM",
        "ASE",
        "PCX",
    }


def _etf_research_source_text(
    report: CompanyResearchReport,
    *,
    external_research_result: ExternalResearchFetchResult | None,
) -> str:
    parts = [_research_brief_evidence_text(row) for row in report.evidence]
    if external_research_result is not None:
        parts.extend(
            f"{entry.title}\nprovider: {entry.provider}\n{entry.content_summary}"
            for entry in external_research_result.entries
        )
    return "\n".join(part for part in parts if part.strip())


def _etf_research_investment_target(text: str) -> str:
    lowered = text.lower()
    if "s&p 500" in lowered or "sp500" in lowered:
        return "S&P 500などの米国大型株指数に連動する投資対象です。"
    if "nasdaq" in lowered:
        return "NASDAQ関連の成長株・テクノロジー銘柄を中心とする投資対象です。"
    if "topix" in lowered:
        return "TOPIXなど日本株指数への連動を目指す投資対象です。"
    if "nikkei" in lowered or "日経" in lowered:
        return "日経平均など日本株指数への連動を目指す投資対象です。"
    if any(keyword in lowered for keyword in ("bond", "treasury", "債券")):
        return "債券を主な投資対象とするETFです。"
    if any(keyword in lowered for keyword in ("reit", "real estate", "不動産")):
        return "REIT・不動産関連資産を主な投資対象とするETFです。"
    if any(keyword in lowered for keyword in ("commodity", "gold", "原油", "金 ")):
        return "コモディティ関連資産を主な投資対象とするETFです。"
    summary = _security_research_metadata_value(
        text,
        "Business Summary",
        "Long Business Summary",
        "Description",
        "Fund Objective",
    )
    if summary:
        return _clip_text(_research_user_facing_text(summary), max_chars=120)
    return "投資対象は外部プロフィールから一部確認できますが、正確な対象指数や構成銘柄は運用会社資料で確認してください。"


def _etf_research_asset_class(text: str) -> str | None:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("bond", "treasury", "債券")):
        return "債券"
    if any(keyword in lowered for keyword in ("reit", "real estate", "不動産")):
        return "REIT・不動産"
    if any(keyword in lowered for keyword in ("commodity", "gold", "原油", "金 ")):
        return "コモディティ"
    if any(keyword in lowered for keyword in ("equity", "stock", "株式")):
        return "株式"
    return None


def _etf_research_region_focus(text: str) -> str | None:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("global", "world", "全世界")):
        return "グローバル"
    if any(
        keyword in lowered
        for keyword in ("united states", "u.s.", "us ", "米国", "s&p 500", "nasdaq")
    ):
        return "米国"
    if any(keyword in lowered for keyword in ("japan", "topix", "nikkei", "日本")):
        return "日本"
    if any(keyword in lowered for keyword in ("emerging", "新興国")):
        return "新興国"
    return None


def _etf_research_sector_focus(text: str) -> str | None:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ("technology", "tech", "テクノロジー", "半導体")):
        return "テクノロジー"
    if any(keyword in lowered for keyword in ("healthcare", "ヘルスケア")):
        return "ヘルスケア"
    if any(keyword in lowered for keyword in ("financial", "金融")):
        return "金融"
    if any(keyword in lowered for keyword in ("energy", "エネルギー")):
        return "エネルギー"
    return None


def _etf_research_benchmark_index(text: str) -> str | None:
    explicit = _security_research_metadata_value(text, "benchmark", "Benchmark", "index", "Index")
    if explicit:
        return _clip_text(_research_user_facing_text(explicit), max_chars=80)
    lowered = text.lower()
    if "s&p 500" in lowered:
        return "S&P 500"
    if "nasdaq-100" in lowered or "nasdaq 100" in lowered:
        return "NASDAQ-100"
    if "topix" in lowered:
        return "TOPIX"
    if "nikkei" in lowered:
        return "日経平均"
    return None


def _etf_research_top_holdings(text: str) -> list[str]:
    holdings_text = ""
    for field_name in (
        "Top Holdings",
        "topHoldings",
        "Holdings",
        "holdings",
        "TopHolding",
        "構成銘柄",
        "上位保有銘柄",
    ):
        match = re.search(
            rf"(?:^|\n){re.escape(field_name)}\s*[:：]\s*([^\n\r]+)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            holdings_text = match.group(1)
            break
    if not holdings_text:
        return []
    parts = re.split(r"[,、;/|]", holdings_text)
    return _unique_text([_clip_text(part.strip(), max_chars=42) for part in parts if part.strip()])[
        :8
    ]


def _etf_research_metric_value(field_key: str, text: str, patterns: Sequence[str]) -> str | None:
    value = _company_research_metric_text_value(text, patterns)
    if not value:
        return None
    if field_key in {"expense_ratio", "dividend_yield"}:
        return _company_research_format_percentage_text(value)
    if field_key in {"aum", "nav"}:
        return _company_research_format_money_text(value, context=text)
    if field_key in {"per", "pbr"}:
        return _company_research_format_ratio_text(value, suffix="倍")
    return value


def _etf_research_fund_overview(
    *,
    fund_name: str,
    investment_target: str,
    asset_class: str | None,
    region_focus: str | None,
    benchmark_index: str | None,
) -> str:
    target_parts = [part for part in (region_focus, asset_class, benchmark_index) if part]
    if target_parts:
        return (
            f"外部プロフィールから、{fund_name}は{'・'.join(target_parts)}を確認対象とするETFとして整理できます。"
            "ただし、正確な対象指数、構成銘柄、費用は運用会社資料で追加確認してください。"
        )
    return (
        f"外部プロフィールから、{fund_name}はETFまたはファンドとして確認できます。"
        f"{investment_target} 運用会社ページ、目論見書、月次レポートで詳細を確認してください。"
    )


def _etf_research_risk_notes(
    *,
    top_holdings: Sequence[str],
    benchmark_index: str | None,
    region_focus: str | None,
    asset_class: str | None,
    expense_ratio: str | None,
    aum: str | None,
    nav: str | None,
) -> list[str]:
    notes = []
    if asset_class == "債券":
        notes.append(
            "債券ETFとして、デュレーション、信用格付け、金利感応度、分配金利回りを確認してください。"
        )
    elif asset_class == "コモディティ":
        notes.append(
            "商品ETFとして、連動対象、裏付け資産、価格変動要因、為替影響を確認してください。"
        )
    elif asset_class == "REIT・不動産":
        notes.append(
            "REIT ETFとして、対象地域、不動産セクター、分配金、金利影響を確認してください。"
        )
    elif asset_class == "株式":
        notes.append(
            "株式ETFとして、対象指数、上位保有銘柄、セクター集中度、地域分散、経費率を確認してください。"
        )
    if expense_ratio is None:
        notes.append(
            "経費率は未取得です。運用会社ページ、目論見書、ETF情報サイトで確認してください。"
        )
    if aum is None or nav is None:
        notes.append(
            "純資産総額またはNAVは未取得です。運用会社ページまたはETF情報サイトで確認してください。"
        )
    if not top_holdings:
        notes.append(
            "上位保有銘柄は未取得です。運用会社の月次レポートや構成銘柄ページで確認してください。"
        )
    if not benchmark_index:
        notes.append(
            "ベンチマーク指数が未取得のため、何に連動するETFか運用会社資料で確認してください。"
        )
    if region_focus and region_focus != "日本":
        notes.append("海外資産を含む場合は、為替影響と対象市場の偏りを確認してください。")
    return notes[:4]


def _etf_research_missing_items(
    *,
    expense_ratio: str | None,
    dividend_yield: str | None,
    aum: str | None,
    nav: str | None,
    top_holdings: Sequence[str],
    benchmark_index: str | None,
) -> list[str]:
    items: list[str] = []
    if expense_ratio is None:
        items.append("経費率")
    if dividend_yield is None:
        items.append("分配金利回り")
    if aum is None:
        items.append("純資産総額")
    if nav is None:
        items.append("基準価額 / NAV")
    if not top_holdings:
        items.append("上位保有銘柄")
    if benchmark_index is None:
        items.append("ベンチマーク指数")
    return items


def _company_research_scale_summary(
    brief: ResearchBrief,
    *,
    normalized_evidence: Sequence[CompanyResearchEvidence],
) -> str:
    metrics = {metric.key: metric for metric in brief.metrics}
    scale_specs: tuple[tuple[str, str, ResearchMetricKey, tuple[str, ...]], ...] = (
        (
            "market_cap",
            "時価総額",
            "market_cap",
            (r"時価総額", r"market cap(?:italization)?", r"marketCap"),
        ),
        (
            "revenue",
            "売上高",
            "revenue",
            (
                r"売上(?:高|収益)?",
                r"total revenue",
                r"totalRevenue",
                r"revenue",
                r"sales",
            ),
        ),
        (
            "operating_profit",
            "営業利益",
            "operating_income",
            (r"営業利益", r"operating income", r"operatingIncome"),
        ),
    )
    scale_parts: list[str] = []
    for field_key, label, metric_key, patterns in scale_specs:
        value, _, _ = _company_research_quantitative_field_value(
            field_key,
            metrics,
            metric_key,
            normalized_evidence,
            patterns,
        )
        if value and _company_research_scale_value_has_unit(value):
            scale_parts.append(f"{label} {value}")
    if scale_parts:
        return f"確認できた規模情報は{'、'.join(scale_parts)}です。"
    return "売上高・利益・時価総額などの規模情報が不足しているため、定量的な把握には追加確認が必要です。"


def _company_research_scale_value_has_unit(value: str) -> bool:
    normalized = value.strip()
    if re.fullmatch(r"[+-]?\d[\d,]*(?:\.\d+)?円", normalized):
        return False
    return bool(
        re.search(
            r"(?:兆円|億円|百万円|万円|円|\b(?:JPY|USD)\b|\d\s*[TBM]\b)",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _company_research_recent_focus(
    recent_items: Sequence[ResearchFactItem],
    *,
    news_report: StockNewsReport | None,
) -> str:
    if news_report is not None and news_report.news:
        lead = news_report.news[0]
        return (
            f"直近ニュースとして「{_clip_text(lead.title, max_chars=72)}」を確認しています。"
            "業績影響は公式IRで裏取りしてください。"
        )
    if recent_items:
        return _clip_text(recent_items[0].value, max_chars=150)
    return "直近ニュースやTDnet情報から確認できる注目点はまだ限定的です。"


def _company_research_metric_value(
    metrics: Mapping[ResearchMetricKey, ResearchMetric],
    key: ResearchMetricKey,
) -> str | None:
    metric = metrics.get(key)
    return metric.value if metric is not None else None


def _company_research_quantitative_field_value(
    field_key: str,
    metrics: Mapping[ResearchMetricKey, ResearchMetric],
    metric_key: ResearchMetricKey | None,
    evidence: Sequence[CompanyResearchEvidence],
    patterns: Sequence[str],
) -> tuple[str | None, list[str], list[str]]:
    if metric_key is not None:
        metric = metrics.get(metric_key)
        if metric is not None:
            context = _company_research_metric_context(metric, evidence)
            context_value = (
                _company_research_metric_text_value(context, patterns) if context else None
            )
            raw_value = context_value or metric.value
            return (
                _company_research_format_quantitative_value(
                    field_key,
                    raw_value,
                    context=context,
                ),
                [metric.source_title],
                [metric.source_type],
            )
    for item in evidence:
        if item.reliability == "news" or not item.body.strip():
            continue
        value = _company_research_metric_text_value(item.body, patterns)
        if value:
            return (
                _company_research_format_quantitative_value(field_key, value, context=item.body),
                [item.source_title or item.title],
                [item.source_type],
            )
    return None, [], []


def _company_research_metric_context(
    metric: ResearchMetric,
    evidence: Sequence[CompanyResearchEvidence],
) -> str:
    candidates: list[str] = []
    for item in evidence:
        if item.source_title == metric.source_title and item.source_type == metric.source_type:
            candidates.append(item.body)
        if item.title == metric.source_title and item.source_type == metric.source_type:
            candidates.append(item.body)
    if not candidates:
        return ""
    return max(candidates, key=len)


def _company_research_format_quantitative_value(
    field_key: str,
    value: str,
    *,
    context: str = "",
) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" .。、、")
    if not cleaned:
        return ""
    if field_key in {
        "market_cap",
        "enterprise_value",
        "revenue",
        "operating_profit",
        "net_income",
    }:
        return _company_research_format_money_text(cleaned, context=context)
    if field_key == "eps":
        return _company_research_format_eps_text(cleaned, context=context)
    if field_key == "employee_count":
        return _company_research_format_employee_count_text(cleaned)
    if field_key in {"per", "pbr"}:
        return _company_research_format_ratio_text(cleaned, suffix="倍")
    if field_key in {"roe", "dividend_yield"}:
        return _company_research_format_percentage_text(cleaned)
    return cleaned


def _company_research_format_money_text(value: str, *, context: str = "") -> str:
    if any(unit in value for unit in ("兆円", "億円", "百万円", "万円", "円")):
        return value
    match = re.search(
        r"([+-]?\d[\d,]*(?:\.\d+)?)\s*([TBM])?\s*(JPY|USD)?",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return value
    amount = _external_decimal_value(match.group(1))
    if amount is None:
        return value
    suffix = (match.group(2) or "").upper()
    if suffix == "T":
        amount *= Decimal("1000000000000")
    elif suffix == "B":
        amount *= Decimal("1000000000")
    elif suffix == "M":
        amount *= Decimal("1000000")
    currency = (match.group(3) or "").upper()
    if not currency and _company_research_context_currency(context) == "JPY":
        currency = "JPY"
    if not currency and _company_research_context_currency(context) == "USD":
        currency = "USD"
    if currency:
        return _format_external_money(amount, currency=currency)
    return f"{_format_external_decimal(amount, thousands=True)} {currency}".strip()


def _company_research_format_eps_text(value: str, *, context: str = "") -> str:
    if "円" in value or "JPY" in value.upper() or "USD" in value.upper():
        amount = _external_decimal_value(re.sub(r"\b(?:JPY|USD)\b", "", value, flags=re.IGNORECASE))
        if amount is not None and ("円" in value or "JPY" in value.upper()):
            return f"{_format_external_decimal(amount)}円"
        return value
    amount = _external_decimal_value(value)
    if amount is None:
        return value
    if _company_research_context_currency(context) == "JPY":
        return f"{_format_external_decimal(amount)}円"
    return _format_external_decimal(amount)


def _company_research_context_currency(text: str) -> str:
    if re.search(r"\b(?:Currency|通貨)\s*[:：]\s*JPY\b", text, flags=re.IGNORECASE):
        return "JPY"
    if re.search(r"\b(?:Currency|通貨)\s*[:：]\s*USD\b", text, flags=re.IGNORECASE):
        return "USD"
    return ""


def _company_research_format_employee_count_text(value: str) -> str:
    if "人" in value or "名" in value:
        return value
    match = re.search(r"([+-]?\d[\d,]*(?:\.\d+)?)", value)
    if match is None:
        return value
    amount = _external_decimal_value(match.group(1))
    if amount is None:
        return value
    return f"{_format_external_decimal(amount, thousands=True)}人"


def _company_research_format_ratio_text(value: str, *, suffix: str) -> str:
    if suffix in value:
        return value
    amount = _external_decimal_value(value)
    if amount is None:
        return value
    return f"{_format_external_decimal(amount)}{suffix}"


def _company_research_format_percentage_text(value: str) -> str:
    if "%" in value or "％" in value:
        return value.replace("％", "%")
    amount = _external_decimal_value(value)
    if amount is None:
        return value
    percentage = amount * Decimal("100") if abs(amount) <= 1 else amount
    return f"{_format_external_decimal(percentage)}%"


def _company_research_evidence_kind(
    source_type: ResearchSourceType,
    title: str,
    body: str,
) -> ResearchEvidenceKind:
    text = f"{title} {body}".lower()
    if source_type == "provider_profile":
        return "company_profile"
    if source_type == "news":
        return "news"
    if source_type == "tdnet":
        return "tdnet_disclosure"
    if source_type == "company_ir":
        return "ir_document"
    if source_type in {
        "annual_report",
        "earnings_report",
        "earnings_presentation",
        "medium_term_plan",
        "integrated_report",
    }:
        return "ir_document"
    if any(keyword in text for keyword in ("market cap", "per", "pbr", "roe", "dividend")):
        return "market_data"
    return "unknown"


def _company_research_reliability(
    source_type: ResearchSourceType | str,
) -> ResearchEvidenceReliability:
    if source_type in {
        "annual_report",
        "earnings_report",
        "earnings_presentation",
        "medium_term_plan",
        "integrated_report",
        "company_ir",
        "tdnet",
    }:
        return "official"
    if source_type == "provider_profile":
        return "market_provider"
    if source_type == "news":
        return "news"
    if source_type == "user_note":
        return "semi_official"
    return "unknown"


def _company_research_external_information_status(
    source_type: ResearchSourceType,
    body: str,
) -> InformationStatus:
    if source_type == "news":
        return "unverified"
    if source_type == "tdnet":
        return "unparsed"
    if body.strip():
        return "found"
    return "unparsed"


def _company_research_extracted_keywords(text: str) -> list[str]:
    keyword_specs = (
        ("自動車", ("自動車", "車両", "vehicle", "automotive", "motor")),
        ("金融サービス", ("金融", "financial services")),
        ("ソフトウェア", ("software", "ソフトウェア")),
        ("配当", ("配当", "dividend")),
        ("自社株買い", ("自社株買い", "自己株式", "buyback")),
        ("業績予想", ("業績予想", "forecast", "guidance")),
        ("中期経営計画", ("中期経営計画", "medium-term")),
        (
            "地域展開",
            ("日本", "北米", "欧州", "アジア", "global", "north america", "europe"),
        ),
    )
    lowered = text.lower()
    return [
        label
        for label, keywords in keyword_specs
        if any(keyword.lower() in lowered for keyword in keywords)
    ]


def _unique_company_research_evidence(
    evidence: Sequence[CompanyResearchEvidence],
) -> list[CompanyResearchEvidence]:
    unique: list[CompanyResearchEvidence] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for item in evidence:
        key = (item.kind, item.title, item.body, item.source_url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _company_research_profile_field(text: str, label: str) -> str | None:
    match = re.search(
        rf"{re.escape(label)}\s*[:：]\s*(.*?)(?=\s+(?:{_research_brief_raw_label_pattern()})\s*[:：]|[。\n\r]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    value = _clip_text(match.group(1).strip(" .、"), max_chars=80)
    return value or None


def _company_research_business_summary_from_text(text: str) -> str:
    cleaned = _research_user_facing_text(_research_brief_clean_provider_text(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    for raw_label in _RESEARCH_BRIEF_RAW_PROVIDER_LABELS:
        cleaned = re.sub(rf"\b{re.escape(raw_label)}\s*[:：]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .。")
    if not cleaned:
        return ""
    readable = _research_brief_readable_business_overview(cleaned)
    return _clip_text(_research_user_facing_text(readable), max_chars=220)


def _company_research_natural_business_summary(
    summary: str,
    *,
    company_name: str,
    main_businesses: Sequence[str],
    supporting_businesses: Sequence[str],
    products_services: Sequence[str],
    regions: Sequence[str],
    evidence_level: ResearchEvidenceLevel,
) -> str:
    cleaned = _research_user_facing_text(summary)
    needs_rewrite = (
        not cleaned
        or _looks_mostly_english(cleaned)
        or any(label in cleaned for label in _RESEARCH_BRIEF_RAW_PROVIDER_LABELS)
    )
    business_terms = _unique_text(main_businesses or supporting_businesses)[:4]
    support_terms = [item for item in supporting_businesses if item not in business_terms][:3]
    product_terms = [
        item.replace("（補完候補）", "")
        for item in products_services
        if item and "補完候補" not in item
    ][:3]
    if business_terms and (needs_rewrite or not cleaned or evidence_level != "high"):
        target_name = company_name.strip() or "この企業"
        business_phrase = "、".join(business_terms[:4])
        product_phrase = (
            f"主な製品・サービスとして{'、'.join(product_terms)}も確認できます。"
            if product_terms
            else ""
        )
        support_phrase = (
            f"関連事業として{'、'.join(support_terms)}も確認できます。" if support_terms else ""
        )
        region_phrase = f"地域は{'、'.join(regions[:3])}などで展開しています。" if regions else ""
        confirmation = (
            "ただし、事業別売上や利益構成は未取得のため、公式資料で追加確認が必要です。"
            if evidence_level != "high"
            else "事業別売上、利益構成、地域別構成は決算資料で続けて確認してください。"
        )
        return _clip_text(
            f"外部プロフィールから、{target_name}は{business_phrase}を展開する企業として確認できます。"
            f"{support_phrase}{product_phrase}{region_phrase}{confirmation}",
            max_chars=280,
        )
    if not cleaned:
        return "外部プロフィールから一部情報は確認できますが、公式資料での裏取りが必要です。"
    if main_businesses and "公式資料" not in cleaned:
        return _clip_text(
            f"{cleaned} ただし、事業別売上や利益構成は公式資料で追加確認が必要です。",
            max_chars=280,
        )
    return _clip_text(cleaned, max_chars=280)


def _company_research_business_terms(text: str) -> list[str]:
    lowered = text.lower()
    specs = (
        (
            "自動車事業",
            (
                "自動車",
                "車両",
                "vehicle",
                "vehicles",
                "automotive",
                "auto manufacturers",
                "motor",
            ),
        ),
        (
            "半導体・GPU",
            (
                "semiconductor",
                "semiconductors",
                "gpu",
                "graphics processing unit",
                "accelerated computing",
                "半導体",
            ),
        ),
        (
            "AI・データセンター",
            (
                "artificial intelligence",
                "ai infrastructure",
                "data center",
                "datacenter",
                "データセンター",
            ),
        ),
        (
            "半導体製造装置",
            ("semiconductor equipment", "半導体製造装置", "wafer", "lithography"),
        ),
        (
            "FAセンサー・制御機器",
            ("fa sensor", "factory automation", "control equipment", "制御機器"),
        ),
        (
            "科学・計測機器",
            (
                "scientific instrument",
                "measurement",
                "measuring",
                "sensor",
                "測定器",
                "計測",
            ),
        ),
        (
            "産業インフラ・デジタル",
            (
                "industry: conglomerates",
                "industrial conglomerate",
                "digital systems and services",
                "green energy and mobility",
                "connective industries",
                "industrial systems",
                "power grids",
                "産業インフラ",
            ),
        ),
        (
            "産業機械・建設機械",
            (
                "farm & heavy construction machinery",
                "construction machinery",
                "heavy machinery",
                "heavy equipment",
                "earthmoving",
                "industrial machinery",
                "建設機械",
                "産業機械",
            ),
        ),
        (
            "鉄道・交通インフラ",
            (
                "industry: railroads",
                "railroad",
                "railway",
                "rail transport",
                "passenger railway",
                "鉄道",
                "交通インフラ",
            ),
        ),
        ("モビリティ事業", ("モビリティ", "mobility")),
        (
            "エレクトロニクス",
            ("electronics", "consumer electronics", "家電", "映像機器", "音響機器"),
        ),
        (
            "ゲーム・エンタメ",
            (
                "game",
                "gaming",
                "music",
                "movie",
                "entertainment",
                "ゲーム",
                "音楽",
                "映画",
            ),
        ),
        (
            "ソフトウェア・クラウド",
            (
                "software",
                "cloud",
                "cloud computing",
                "cloud services",
                "saas",
                "platform",
                "aws",
                "amazon web services",
                "azure",
                "enterprise services",
                "ソフトウェア",
                "クラウド",
            ),
        ),
        (
            "広告・マーケティング",
            ("advertising", "advertisement", "ads", "marketing services", "広告"),
        ),
        (
            "決済ネットワーク",
            (
                "payment",
                "payments",
                "card network",
                "transaction",
                "merchant",
                "fintech",
                "digital payment",
                "settlement",
            ),
        ),
        (
            "銀行・金融サービス",
            (
                "sector: financial services",
                "banks -",
                "banking",
                "commercial banking",
                "investment banking",
                "asset management",
                "credit",
                "loan",
                "securities",
                "銀行",
                "証券",
            ),
        ),
        (
            "医薬品・ヘルスケア",
            (
                "sector: healthcare",
                "pharmaceutical",
                "healthcare",
                "medical device",
                "medicine",
                "biotech",
                "drug",
                "therapy",
                "diagnostics",
                "医薬品",
                "医療機器",
            ),
        ),
        (
            "エネルギー",
            (
                "sector: energy",
                "oil & gas",
                "oil and gas",
                "refining",
                "exploration",
                "production",
                "renewable",
                "石油",
                "ガス",
                "エネルギー",
            ),
        ),
        (
            "ガス・エネルギーインフラ",
            (
                "sector: utilities",
                "industry: utilities",
                "utilities - regulated gas",
                "gas utilities",
                "natural gas distribution",
                "city gas",
                "town gas",
                "gas distribution",
                "gas supply",
                "gas pipeline",
                "都市ガス",
                "ガス供給",
                "エネルギー供給",
                "公益",
                "インフラ",
            ),
        ),
        (
            "電力・エネルギー供給",
            (
                "electric power",
                "electricity",
                "power generation",
                "power supply",
                "domestic energy",
                "international energy",
                "電力",
                "発電",
                "エネルギー供給",
            ),
        ),
        (
            "通信サービス",
            (
                "telecom services",
                "telecommunications",
                "wireless",
                "broadband",
                "通信",
            ),
        ),
        (
            "人材・HRサービス",
            (
                "human resources",
                "staffing",
                "recruitment",
                "recruiting",
                "employment",
                "job matching",
                "hr technology",
                "人材",
                "採用",
                "求人",
            ),
        ),
        (
            "総合商社・事業投資",
            (
                "trading company",
                "general trading",
                "sogo shosha",
                "industrial finance",
                "事業投資",
                "総合商社",
            ),
        ),
        (
            "アパレル小売",
            (
                "apparel",
                "fashion",
                "clothing",
                "brand",
                "private label",
                "SPA",
                "衣料",
                "アパレル",
            ),
        ),
        (
            "小売・EC",
            ("retail", "e-commerce", "marketplace", "store", "apparel", "小売", "EC"),
        ),
    )
    labels = [label for label, keywords in specs if any(keyword in lowered for keyword in keywords)]
    finance_main_context = (
        "sector: financial" in lowered
        or "financial sector" in lowered
        or "banking" in lowered
        or "asset management" in lowered
        or "銀行" in lowered
        or "証券" in lowered
    )
    if finance_main_context and "金融サービス" not in labels and "銀行・金融サービス" not in labels:
        labels.append("金融サービス")
    return labels


def _company_research_filter_main_businesses(
    text: str,
    businesses: Sequence[str],
) -> list[str]:
    lowered = text.lower()
    finance_main_context = (
        "sector: financial" in lowered
        or "financial sector" in lowered
        or "banking" in lowered
        or "asset management" in lowered
        or "銀行" in lowered
        or "証券" in lowered
    )
    auto_manufacturer_context = _company_research_is_auto_manufacturer_context(lowered)
    software_cloud_context = _company_research_is_software_cloud_context(lowered)
    retail_main_context = _company_research_is_retail_main_context(lowered)
    payment_context = _company_research_is_payment_context(lowered)
    hr_context = _company_research_is_hr_services_context(lowered)
    trading_context = _company_research_is_trading_company_context(lowered)
    cloud_infra_context = _company_research_is_cloud_infrastructure_context(lowered)
    bank_context = any(
        keyword in lowered
        for keyword in (
            "bank",
            "banking",
            "banks -",
            "commercial banking",
            "investment banking",
        )
    )
    healthcare_context = _company_research_is_healthcare_context(lowered)
    energy_context = _company_research_is_energy_context(lowered)
    utility_energy_context = _company_research_is_utility_energy_context(lowered)
    telecom_context = _company_research_is_telecom_context(lowered)
    consumer_electronics_context = _company_research_is_consumer_electronics_context(lowered)
    industrial_conglomerate_context = _company_research_is_industrial_conglomerate_context(lowered)
    heavy_machinery_context = _company_research_is_heavy_machinery_context(lowered)
    railroad_context = _company_research_is_railroad_context(lowered)
    auto_related_main = {"自動車事業", "モビリティ事業", "自動車・モビリティ"}
    software_related_main = {"ソフトウェア・クラウド", "ソフトウェア・サービス"}
    finance_related_main = {"金融サービス", "銀行・金融サービス"}
    utility_related_main = {"ガス・エネルギーインフラ", "電力・エネルギー供給"}
    industrial_related_main = {
        "産業インフラ・デジタル",
        "産業機械・建設機械",
        "鉄道・交通インフラ",
    }
    filtered = [
        item
        for item in businesses
        if not (item == "金融サービス" and not finance_main_context)
        and not (payment_context and not bank_context and item == "金融サービス")
        and not (item == "銀行・金融サービス" and not finance_main_context)
        and not (payment_context and not bank_context and item == "銀行・金融サービス")
        and not (not auto_manufacturer_context and item in auto_related_main)
        and not (auto_manufacturer_context and item in {"小売・EC", "アパレル小売"})
        and not (auto_manufacturer_context and item == "決済ネットワーク")
        and not (item == "小売・EC" and software_cloud_context and not retail_main_context)
        and not (item == "アパレル小売" and not retail_main_context)
        and not (retail_main_context and item in software_related_main and not cloud_infra_context)
        and not (retail_main_context and item == "通信サービス")
        and not (finance_main_context and item == "小売・EC")
        and not (bank_context and item == "決済ネットワーク")
        and not (payment_context and not bank_context and item == "銀行・金融サービス")
        and not (payment_context and item == "広告・マーケティング")
        and not (hr_context and item == "通信サービス")
        and not (
            trading_context
            and item
            in (
                software_related_main
                | industrial_related_main
                | utility_related_main
                | {"小売・EC", "アパレル小売", "決済ネットワーク", "エネルギー"}
            )
        )
        and not (not healthcare_context and item == "医薬品・ヘルスケア")
        and not (not energy_context and item == "エネルギー")
        and not (not telecom_context and item == "通信サービス")
        and not (not industrial_conglomerate_context and item == "産業インフラ・デジタル")
        and not (not heavy_machinery_context and item == "産業機械・建設機械")
        and not (not railroad_context and item == "鉄道・交通インフラ")
        and not (finance_main_context and item in software_related_main)
        and not (healthcare_context and item in finance_related_main | software_related_main)
        and not (healthcare_context and item in {"小売・EC", "アパレル小売"})
        and not (
            energy_context
            and item in finance_related_main | software_related_main | {"AI・データセンター"}
        )
        and not (
            utility_energy_context
            and item
            in (
                finance_related_main
                | software_related_main
                | {
                    "自動車事業",
                    "モビリティ事業",
                    "小売・EC",
                    "通信サービス",
                    "AI・データセンター",
                }
            )
        )
        and not (telecom_context and item in finance_related_main | software_related_main)
        and not (consumer_electronics_context and item in finance_related_main)
        and not (
            industrial_conglomerate_context
            and item
            in (
                auto_related_main
                | finance_related_main
                | software_related_main
                | {
                    "医薬品・ヘルスケア",
                    "広告・マーケティング",
                    "小売・EC",
                    "アパレル小売",
                    "部品・保守",
                }
            )
        )
        and not (
            heavy_machinery_context
            and item
            in (
                finance_related_main
                | software_related_main
                | {"エレクトロニクス", "医薬品・ヘルスケア", "広告・マーケティング"}
            )
        )
        and not (
            railroad_context
            and item
            in (
                auto_related_main
                | finance_related_main
                | software_related_main
                | utility_related_main
                | {
                    "医薬品・ヘルスケア",
                    "広告・マーケティング",
                    "エレクトロニクス",
                    "小売・EC",
                    "エネルギー",
                    "部品・保守",
                }
            )
        )
        and not (
            item == "総合商社・事業投資" and industrial_conglomerate_context and not trading_context
        )
        and item not in {"部品・アフターサービス", "部品・保守", "リース", "ソフトウェア"}
    ]
    if trading_context:
        filtered = ["総合商社・事業投資"] + [
            item
            for item in filtered
            if item
            not in (
                industrial_related_main | utility_related_main | {"エネルギー", "決済ネットワーク"}
            )
        ]
    if railroad_context and "鉄道・交通インフラ" in filtered:
        priority = ["鉄道・交通インフラ"]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
    if heavy_machinery_context and "産業機械・建設機械" in filtered:
        priority = ["産業機械・建設機械"]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
    if industrial_conglomerate_context and "産業インフラ・デジタル" in filtered:
        priority = ["産業インフラ・デジタル", "エネルギー"]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
    if utility_energy_context and any(item in filtered for item in utility_related_main):
        priority = ["ガス・エネルギーインフラ", "電力・エネルギー供給", "エネルギー"]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
        if "ガス・エネルギーインフラ" in filtered:
            filtered = [item for item in filtered if item != "エネルギー"]
    if "銀行・金融サービス" in filtered:
        filtered = [item for item in filtered if item != "金融サービス"]
    elif bank_context and finance_main_context and not consumer_electronics_context:
        filtered.insert(0, "銀行・金融サービス")
    if "ソフトウェア・クラウド" in filtered:
        filtered = [item for item in filtered if item != "ソフトウェア・サービス"]
    if retail_main_context and cloud_infra_context:
        priority = [
            "小売・EC",
            "ソフトウェア・クラウド",
            "広告・マーケティング",
            "AI・データセンター",
            "ゲーム・エンタメ",
        ]
        filtered = [item for item in priority if item in filtered] + [
            item for item in filtered if item not in priority
        ]
    return _unique_text(filtered)[:5]


def _company_research_is_semiconductor_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: semiconductors",
            "semiconductor",
            "semiconductors",
            "gpu",
            "accelerated computing",
            "ai infrastructure",
            "data center",
            "datacenter",
        )
    )


def _company_research_is_auto_manufacturer_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: auto manufacturers",
            "auto manufacturers",
            "automobile manufacturer",
            "motor corporation",
        )
    )


def _company_research_is_software_cloud_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "software",
            "cloud",
            "saas",
            "platform",
            "azure",
            "enterprise services",
        )
    )


def _company_research_is_cloud_infrastructure_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "cloud computing",
            "cloud infrastructure",
            "cloud services",
            "aws",
            "amazon web services",
            "azure",
            "google cloud",
        )
    )


def _company_research_is_payment_context(lowered_text: str) -> bool:
    strong_keywords = (
        "industry: credit services",
        "card network",
        "payment network",
        "payments network",
        "transaction processing",
        "merchant services",
        "digital payment",
        "settlement network",
    )
    if any(keyword in lowered_text for keyword in strong_keywords):
        return True
    return "sector: financial" in lowered_text and any(
        keyword in lowered_text for keyword in ("payment", "payments", "transaction", "merchant")
    )


def _company_research_is_hr_services_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "human resources",
            "staffing",
            "recruitment",
            "recruiting",
            "employment",
            "job matching",
            "hr technology",
            "人材",
            "採用",
            "求人",
        )
    )


def _company_research_is_trading_company_context(lowered_text: str) -> bool:
    if any(
        keyword in lowered_text
        for keyword in (
            "trading company",
            "general trading",
            "sogo shosha",
            "事業投資",
            "総合商社",
        )
    ):
        return True
    if "sector: industrials" not in lowered_text or "industry: conglomerates" not in lowered_text:
        return False
    diversified_trading_terms = (
        "natural gas",
        "industrial materials",
        "petroleum",
        "chemicals solution",
        "mineral resources",
        "industrial infrastructure",
        "automotive & mobility",
        "food industry",
        "consumer industry",
        "power solution",
        "urban development",
    )
    return sum(term in lowered_text for term in diversified_trading_terms) >= 4


def _company_research_is_industrial_conglomerate_context(lowered_text: str) -> bool:
    if _company_research_is_trading_company_context(lowered_text):
        return False
    return (
        "sector: industrials" in lowered_text
        and ("industry: conglomerates" in lowered_text or "industrial conglomerate" in lowered_text)
    ) or any(
        keyword in lowered_text
        for keyword in (
            "digital systems and services",
            "green energy and mobility",
            "connective industries",
            "industrial systems",
            "power grids",
        )
    )


def _company_research_is_heavy_machinery_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: farm & heavy construction machinery",
            "construction machinery",
            "heavy construction machinery",
            "heavy machinery",
            "heavy equipment",
            "earthmoving",
            "industrial machinery",
        )
    )


def _company_research_is_consumer_electronics_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: consumer electronics",
            "consumer electronics",
            "electronic gaming & multimedia",
        )
    )


def _company_research_is_railroad_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: railroads",
            "railroad",
            "railway",
            "rail transport",
            "passenger railway",
            "rail station",
        )
    )


def _company_research_is_materials_chemical_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: chemicals",
            "specialty chemicals",
            "chemical manufacturing",
            "chemical products",
            "fine materials",
            "carbon material",
            "materials segment",
            "materials business",
            "material products",
            "材料事業",
            "材料製品",
            "化学",
        )
    )


def _company_research_is_apparel_retail_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "apparel",
            "fashion",
            "clothing",
            "private label",
            "specialty retail",
            "衣料",
            "アパレル",
        )
    )


def _company_research_is_retail_main_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "industry: internet retail",
            "industry: apparel retail",
            "industry: specialty retail",
            "sector: consumer cyclical",
            "retail trade",
            "retailer",
            "e-commerce company",
        )
    )


def _company_research_is_healthcare_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "sector: healthcare",
            "industry: healthcare",
            "industry: pharmaceutical",
            "medical device",
            "drug manufacturers",
            "biotech",
        )
    )


def _company_research_is_energy_context(lowered_text: str) -> bool:
    return _company_research_is_utility_energy_context(lowered_text) or any(
        keyword in lowered_text
        for keyword in (
            "sector: energy",
            "oil & gas",
            "oil and gas",
            "refining",
            "exploration",
            "production",
        )
    )


def _company_research_is_utility_energy_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "sector: utilities",
            "industry: utilities",
            "utilities - regulated gas",
            "gas utilities",
            "natural gas distribution",
            "city gas",
            "town gas",
            "gas distribution",
            "gas supply",
            "gas pipeline",
            "electric power",
            "electricity",
            "power generation",
            "domestic energy",
            "international energy",
            "都市ガス",
            "ガス供給",
            "電力",
            "発電",
            "エネルギー供給",
            "公益",
            "インフラ",
        )
    )


def _company_research_is_telecom_context(lowered_text: str) -> bool:
    return any(
        keyword in lowered_text
        for keyword in (
            "telecom services",
            "telecommunications",
            "wireless",
            "broadband",
            "mobile network",
            "fixed-line",
            "fiber optic",
        )
    )


def _company_research_supporting_business_terms(
    text: str,
    *,
    main_businesses: Sequence[str],
) -> list[str]:
    lowered = text.lower()
    specs = (
        ("金融サービス", ("financial services", "金融")),
        ("リース", ("lease", "leasing", "リース")),
        (
            "部品・アフターサービス",
            ("parts", "components", "maintenance", "repair", "部品", "保守", "整備"),
        ),
        ("ソフトウェア", ("software", "ソフトウェア")),
        ("保険", ("insurance", "保険")),
        ("資産運用", ("asset management", "資産運用")),
        (
            "海外エネルギー",
            ("international energy", "overseas energy", "海外エネルギー"),
        ),
        (
            "ライフサービス",
            (
                "life & business solutions",
                "life services",
                "lifestyle",
                "生活",
                "ライフサービス",
            ),
        ),
        ("不動産", ("real estate", "property", "不動産")),
        (
            "情報ソリューション",
            (
                "information solutions",
                "information service",
                "it services",
                "情報ソリューション",
            ),
        ),
        (
            "材料・化学",
            (
                "fine materials",
                "carbon material",
                "chemical products",
                "chemicals",
                "materials segment",
                "materials business",
                "material products",
                "材料事業",
                "材料製品",
                "化学",
            ),
        ),
    )
    main_set = set(main_businesses)
    return [
        label
        for label, keywords in specs
        if label not in main_set and any(keyword in lowered for keyword in keywords)
    ]


def _company_research_filter_supporting_businesses(
    text: str,
    businesses: Sequence[str],
    *,
    main_businesses: Sequence[str],
) -> list[str]:
    lowered = text.lower()
    main_set = set(main_businesses)
    finance_main_context = (
        "sector: financial" in lowered
        or "financial sector" in lowered
        or "banking" in lowered
        or "asset management" in lowered
        or "銀行" in lowered
        or "証券" in lowered
    )
    auto_manufacturer_context = _company_research_is_auto_manufacturer_context(lowered)
    retail_main_context = _company_research_is_retail_main_context(lowered)
    cloud_infra_context = _company_research_is_cloud_infrastructure_context(lowered)
    filtered = list(businesses)
    if not (
        _company_research_is_materials_chemical_context(lowered)
        or _company_research_is_trading_company_context(lowered)
        or _company_research_is_energy_context(lowered)
        or _company_research_is_utility_energy_context(lowered)
    ):
        filtered = [item for item in filtered if item != "材料・化学"]
    if auto_manufacturer_context:
        filtered = [item for item in filtered if item != "資産運用"]
    if _company_research_is_industrial_conglomerate_context(lowered):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "リース", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_railroad_context(lowered):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "リース", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_heavy_machinery_context(lowered):
        filtered = [item for item in filtered if item not in {"ソフトウェア", "資産運用"}]
    if _company_research_is_consumer_electronics_context(lowered):
        filtered = [item for item in filtered if item not in {"リース", "保険", "資産運用"}]
    if retail_main_context and not cloud_infra_context and not auto_manufacturer_context:
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "リース", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_healthcare_context(lowered):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "リース", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_energy_context(lowered):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "保険", "資産運用", "ソフトウェア"}
        ]
    if _company_research_is_utility_energy_context(lowered):
        filtered = [
            item
            for item in filtered
            if item
            not in {
                "金融サービス",
                "リース",
                "部品・アフターサービス",
                "ソフトウェア",
                "保険",
                "資産運用",
            }
        ]
    if _company_research_is_telecom_context(lowered):
        filtered = [item for item in filtered if item not in {"金融サービス", "保険", "資産運用"}]
    if (
        _company_research_is_software_cloud_context(lowered)
        and not finance_main_context
        and not auto_manufacturer_context
    ):
        filtered = [
            item
            for item in filtered
            if item not in {"金融サービス", "保険", "資産運用", "リース", "ソフトウェア"}
        ]
    if "決済ネットワーク" in main_set:
        filtered = [
            item for item in filtered if item not in {"金融サービス", "資産運用", "ソフトウェア"}
        ]
    if "銀行・金融サービス" in main_set or "金融サービス" in main_set:
        filtered = [item for item in filtered if item != "ソフトウェア"]
    return _unique_text(filtered)[:5]


def _company_research_products_services(text: str) -> list[str]:
    lowered = text.lower()
    specs = (
        (
            "電気自動車",
            ("electric vehicle", "electric vehicles", "evs", "EV", "電気自動車"),
        ),
        ("自動車", ("automobile", "automotive", "自動車")),
        ("商用車", ("commercial vehicle", "commercial vehicles", "商用車")),
        ("車両", ("vehicle", "vehicles", "車両")),
        (
            "蓄電池",
            ("battery", "batteries", "energy storage", "storage systems", "蓄電池"),
        ),
        ("充電サービス", ("charging", "supercharger", "充電")),
        (
            "車載ソフトウェア",
            ("autopilot", "full self-driving", "vehicle software", "車載ソフトウェア"),
        ),
        ("部品", ("parts", "components", "部品")),
        (
            "保守・整備",
            ("maintenance", "repair", "after-sales", "aftersales", "保守", "整備"),
        ),
        (
            "建設機械",
            (
                "construction machinery",
                "heavy construction machinery",
                "construction equipment",
                "建設機械",
            ),
        ),
        (
            "産業機械",
            ("industrial machinery", "heavy machinery", "heavy equipment", "産業機械"),
        ),
        ("エンジン", ("engine", "engines", "turbine", "turbines", "エンジン")),
        (
            "鉄道サービス",
            ("railroad", "railway", "rail transport", "passenger railway", "鉄道"),
        ),
        (
            "交通インフラ",
            (
                "transportation infrastructure",
                "rail station",
                "station",
                "交通インフラ",
            ),
        ),
        (
            "デジタルシステム",
            (
                "digital systems",
                "it services",
                "information technology",
                "デジタルシステム",
            ),
        ),
        (
            "産業インフラ",
            (
                "industrial systems",
                "power grids",
                "connective industries",
                "産業インフラ",
            ),
        ),
        ("金融サービス", ("financial services", "金融")),
        ("リース", ("lease", "leasing", "リース")),
        (
            "モビリティサービス",
            ("mobility service", "mobility services", "モビリティサービス"),
        ),
        ("ソフトウェアサービス", ("software", "ソフトウェア")),
        (
            "クラウドサービス",
            ("cloud service", "cloud services", "cloud computing", "aws", "azure"),
        ),
        (
            "求人・採用サービス",
            ("recruitment", "recruiting", "employment", "job matching", "求人", "採用"),
        ),
        (
            "HRプラットフォーム",
            ("human resources", "hr technology", "staffing", "HR", "人材"),
        ),
        ("衣料品", ("apparel", "fashion", "clothing", "garment", "衣料", "アパレル")),
        ("店舗販売", ("store", "stores", "retail store", "店舗")),
        ("オンライン販売", ("e-commerce", "online sales", "online store", "EC")),
        ("ブランド運営", ("brand", "brands", "private label", "ブランド")),
        ("マーケットプレイスサービス", ("marketplace", "マーケットプレイス")),
        ("金融商品", ("financial products", "金融商品")),
        ("決済", ("payment", "payments", "決済")),
        ("カード決済", ("card payment", "card payments", "card network")),
        ("デジタル決済", ("digital payment", "digital payments")),
        ("決済ネットワーク", ("card network", "transaction", "merchant", "settlement")),
        ("加盟店サービス", ("merchant services", "加盟店")),
        ("不正検知", ("fraud", "fraud detection", "不正検知")),
        (
            "広告サービス",
            ("advertising", "advertisement", "ads", "marketing services", "広告"),
        ),
        ("保険", ("insurance", "保険")),
        ("資産運用", ("asset management", "資産運用")),
        ("銀行サービス", ("banking", "commercial bank", "銀行")),
        ("融資・クレジット", ("loan", "credit", "lending", "融資", "ローン")),
        ("センサー", ("sensor", "sensors", "センサー")),
        ("GPU", ("gpu", "graphics processing unit")),
        (
            "AIインフラ",
            ("artificial intelligence", "ai infrastructure", "accelerated computing"),
        ),
        ("データセンター向け製品", ("data center", "datacenter")),
        ("半導体", ("semiconductor", "semiconductors", "半導体")),
        (
            "医薬品",
            ("pharmaceutical", "medicine", "drug", "therapy", "医薬品", "治療薬"),
        ),
        ("医療機器", ("medical device", "medical devices", "医療機器")),
        ("診断・検査", ("diagnostics", "diagnostic", "診断", "検査")),
        ("石油・ガス", ("oil & gas", "oil and gas", "natural gas", "石油", "ガス")),
        (
            "都市ガス",
            ("city gas", "town gas", "都市ガス", "gas supply", "gas distribution"),
        ),
        (
            "電力",
            (
                "electric power",
                "electricity",
                "power generation",
                "power supply",
                "電力",
                "発電",
            ),
        ),
        ("LNG", ("lng", "liquefied natural gas")),
        ("LPG", ("lpg", "liquefied petroleum gas")),
        (
            "エネルギーサービス",
            (
                "energy services",
                "energy service",
                "energy solution",
                "エネルギーサービス",
            ),
        ),
        ("ガス機器", ("gas appliances", "gas equipment", "ガス機器")),
        (
            "エネルギーインフラ",
            ("gas pipeline", "energy infrastructure", "パイプライン"),
        ),
        (
            "生活関連サービス",
            ("life services", "life & business solutions", "生活", "ライフサービス"),
        ),
        (
            "情報ソリューション",
            (
                "information solutions",
                "information service",
                "it services",
                "情報ソリューション",
            ),
        ),
        ("不動産サービス", ("real estate", "property", "不動産")),
        (
            "材料・化学製品",
            (
                "fine materials",
                "carbon material",
                "chemical products",
                "chemicals",
                "materials segment",
                "materials business",
                "material products",
                "材料事業",
                "材料製品",
                "化学",
            ),
        ),
        ("精製・販売", ("refining", "refinery", "販売")),
        ("エネルギー開発", ("exploration", "production", "renewable", "エネルギー")),
        ("通信サービス", ("telecom", "telecommunications", "wireless", "通信")),
        ("ブロードバンド", ("broadband", "fiber optic", "optical fiber", "光回線")),
        ("測定器", ("measuring instruments", "measurement", "測定器", "計測器")),
        ("制御機器", ("control equipment", "制御機器")),
        ("検査装置", ("inspection equipment", "検査装置")),
        ("ゲーム", ("game", "gaming", "ゲーム")),
        ("音楽", ("music", "音楽")),
        ("映画", ("movie", "film", "映画")),
    )
    products = [
        label for label, keywords in specs if any(keyword in lowered for keyword in keywords)
    ]
    if _company_research_is_semiconductor_context(
        lowered
    ) and not _company_research_is_auto_manufacturer_context(lowered):
        products = [
            item for item in products if item not in {"電気自動車", "自動車", "商用車", "車両"}
        ]
    if _company_research_is_auto_manufacturer_context(lowered) and any(
        keyword in lowered for keyword in ("electric vehicle", "electric vehicles", "evs")
    ):
        products = [
            item
            for item in products
            if item not in {"金融サービス", "金融商品", "リース", "保険", "融資・クレジット"}
        ]
    if (
        _company_research_is_retail_main_context(lowered)
        and not _company_research_is_cloud_infrastructure_context(lowered)
        and not _company_research_is_auto_manufacturer_context(lowered)
    ):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "リース",
                "保険",
                "資産運用",
                "通信サービス",
                "ブロードバンド",
            }
        ]
    if _company_research_is_payment_context(lowered) and not any(
        keyword in lowered for keyword in ("bank", "banking", "banks -")
    ):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "オンライン販売",
                "融資・クレジット",
                "資産運用",
                "広告サービス",
            }
        ]
    if _company_research_is_trading_company_context(lowered):
        products = [item for item in products if item not in {"決済", "決済ネットワーク"}]
    if (
        not _company_research_is_auto_manufacturer_context(lowered)
        and "sector: financial" not in lowered
        and "banking" not in lowered
    ):
        products = [item for item in products if item != "リース"]
    if any(
        keyword in lowered
        for keyword in (
            "scientific & technical instruments",
            "measurement",
            "measuring",
            "sensor",
            "測定器",
            "計測",
        )
    ) and not _company_research_is_telecom_context(lowered):
        products = [item for item in products if item not in {"通信サービス", "ブロードバンド"}]
    if _company_research_is_healthcare_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "石油・ガス",
                "精製・販売",
                "エネルギー開発",
                "通信サービス",
                "ブロードバンド",
                "店舗販売",
                "オンライン販売",
                "ブランド運営",
                "不動産サービス",
            }
        ]
    if _company_research_is_industrial_conglomerate_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "自動車",
                "商用車",
                "車両",
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "医薬品",
                "医療機器",
                "診断・検査",
                "広告サービス",
                "ブランド運営",
                "通信サービス",
                "ブロードバンド",
                "エンジン",
            }
        ]
    if _company_research_is_railroad_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "自動車",
                "商用車",
                "車両",
                "蓄電池",
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "医薬品",
                "医療機器",
                "診断・検査",
                "広告サービス",
                "通信サービス",
                "ブロードバンド",
                "材料・化学製品",
                "電力",
                "エンジン",
            }
        ]
    if _company_research_is_heavy_machinery_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "ソフトウェアサービス",
                "クラウドサービス",
                "広告サービス",
                "ブランド運営",
                "医薬品",
                "医療機器",
                "診断・検査",
                "通信サービス",
                "ブロードバンド",
            }
        ]
    if _company_research_is_consumer_electronics_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "リース",
                "保険",
                "資産運用",
                "銀行サービス",
                "融資・クレジット",
            }
        ]
    if _company_research_is_software_cloud_context(lowered) and not (
        _company_research_is_retail_main_context(lowered)
        or _company_research_is_auto_manufacturer_context(lowered)
    ):
        products = [
            item
            for item in products
            if item
            not in {
                "店舗販売",
                "オンライン販売",
                "ブランド運営",
                "衣料品",
                "エネルギーインフラ",
                "不動産サービス",
            }
        ]
    if _company_research_is_energy_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "AIインフラ",
                "データセンター向け製品",
            }
        ]
    if _company_research_is_trading_company_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "都市ガス",
                "電力",
                "LNG",
                "LPG",
                "エネルギーサービス",
                "ガス機器",
                "エネルギーインフラ",
                "決済",
                "決済ネットワーク",
            }
        ]
    if _company_research_is_utility_energy_context(lowered):
        products = [
            item
            for item in products
            if item
            not in {
                "金融サービス",
                "金融商品",
                "決済",
                "リース",
                "保険",
                "資産運用",
                "保守・整備",
                "ソフトウェアサービス",
                "AIインフラ",
                "データセンター向け製品",
                "通信サービス",
                "ブロードバンド",
                "精製・販売",
            }
        ]
    if _company_research_is_telecom_context(lowered):
        products = [
            item
            for item in products
            if item not in {"金融サービス", "金融商品", "決済", "保険", "資産運用"}
        ]
    if not (
        _company_research_is_materials_chemical_context(lowered)
        or _company_research_is_trading_company_context(lowered)
        or _company_research_is_energy_context(lowered)
        or _company_research_is_utility_energy_context(lowered)
    ):
        products = [item for item in products if item != "材料・化学製品"]
    if _company_research_is_utility_energy_context(lowered):
        priority = [
            "都市ガス",
            "電力",
            "LNG",
            "LPG",
            "エネルギーサービス",
            "ガス機器",
            "エネルギーインフラ",
            "生活関連サービス",
            "情報ソリューション",
            "不動産サービス",
            "材料・化学製品",
            "石油・ガス",
            "エネルギー開発",
        ]
        products = [item for item in priority if item in products] + [
            item for item in products if item not in priority
        ]
    return products


def _company_research_inferred_products_services(
    text: str,
    *,
    main_businesses: Sequence[str],
    supporting_businesses: Sequence[str],
) -> list[str]:
    lowered = text.lower()
    context = " ".join([lowered, *main_businesses, *supporting_businesses])
    inference_specs = (
        (
            (
                "railroad",
                "railway",
                "rail transport",
                "鉄道・交通インフラ",
            ),
            ("鉄道サービス", "交通インフラ", "不動産サービス"),
        ),
        (
            (
                "construction machinery",
                "heavy machinery",
                "heavy equipment",
                "産業機械・建設機械",
            ),
            ("建設機械", "産業機械", "エンジン", "部品", "保守・整備"),
        ),
        (
            (
                "digital systems and services",
                "green energy and mobility",
                "connective industries",
                "産業インフラ・デジタル",
            ),
            ("デジタルシステム", "産業インフラ", "エネルギー開発"),
        ),
        (
            (
                "自動車",
                "automotive",
                "vehicle",
                "mobility",
                "自動車事業",
                "モビリティ事業",
            ),
            ("自動車", "商用車", "部品", "金融サービス", "モビリティ関連サービス"),
        ),
        (
            ("electric vehicle", "energy storage", "charging", "auto manufacturers"),
            ("電気自動車", "蓄電池", "充電サービス", "車載ソフトウェア"),
        ),
        (
            (
                "healthcare",
                "pharmaceutical",
                "drug",
                "medicine",
                "medical device",
                "医薬品・ヘルスケア",
            ),
            ("医薬品", "医療機器", "診断・検査"),
        ),
        (
            (
                "energy",
                "oil & gas",
                "oil and gas",
                "refining",
                "exploration",
                "エネルギー",
            ),
            ("石油・ガス", "エネルギー開発", "精製・販売"),
        ),
        (
            (
                "utilities",
                "regulated gas",
                "city gas",
                "town gas",
                "natural gas distribution",
                "domestic energy",
                "international energy",
                "gas supply",
                "gas distribution",
                "ガス・エネルギーインフラ",
                "電力・エネルギー供給",
            ),
            ("都市ガス", "電力", "LNG", "エネルギーサービス", "ガス機器"),
        ),
        (
            ("telecom", "telecommunications", "wireless", "broadband", "通信サービス"),
            ("通信サービス", "ブロードバンド"),
        ),
        (
            (
                "payment",
                "payments",
                "card network",
                "transaction",
                "merchant",
                "決済ネットワーク",
            ),
            (
                "カード決済",
                "デジタル決済",
                "決済ネットワーク",
                "加盟店サービス",
                "不正検知",
            ),
        ),
        (
            (
                "human resources",
                "staffing",
                "recruitment",
                "employment",
                "人材・HRサービス",
            ),
            ("求人・採用サービス", "人材紹介", "HRプラットフォーム"),
        ),
        (
            ("apparel", "fashion", "clothing", "retail", "アパレル小売", "小売・EC"),
            ("衣料品", "店舗販売", "オンライン販売", "ブランド運営"),
        ),
        (
            ("trading company", "general trading", "sogo shosha", "総合商社・事業投資"),
            ("資源・エネルギー", "金属", "食品", "物流", "インフラ事業"),
        ),
        (
            ("software", "cloud", "saas", "platform", "ソフトウェア・クラウド"),
            ("ソフトウェアサービス", "クラウドサービス", "法人向けサービス"),
        ),
        (
            (
                "金融",
                "financial",
                "banking",
                "insurance",
                "asset management",
                "金融サービス",
            ),
            (
                "銀行サービス",
                "金融商品",
                "決済",
                "融資・クレジット",
                "保険",
                "資産運用",
            ),
        ),
        (
            (
                "electronics",
                "consumer electronics",
                "エレクトロニクス",
                "game",
                "entertainment",
            ),
            ("家電", "映像機器", "音響機器", "ゲーム", "エンタメ関連サービス"),
        ),
        (
            (
                "scientific",
                "measurement",
                "sensor",
                "control equipment",
                "科学・計測機器",
                "FAセンサー",
            ),
            ("センサー", "測定器", "制御機器", "検査装置"),
        ),
        (
            (
                "semiconductor",
                "gpu",
                "ai infrastructure",
                "accelerated computing",
                "data center",
                "半導体・GPU",
                "AI・データセンター",
            ),
            ("GPU", "AIインフラ", "データセンター向け製品", "半導体"),
        ),
    )
    for keywords, candidates in inference_specs:
        if any(keyword.lower() in context for keyword in keywords):
            return [f"{candidate}（補完候補）" for candidate in candidates]
    return []


def _company_research_regions_from_text(text: str) -> list[str]:
    lowered = text.lower()
    specs = (
        ("日本", ("日本", "japan")),
        ("北米", ("北米", "north america", "u.s.", "united states")),
        ("欧州", ("欧州", "europe")),
        ("アジア", ("アジア", "asia")),
        ("グローバル", ("global", "worldwide", "世界")),
    )
    return [label for label, keywords in specs if any(keyword in lowered for keyword in keywords)]


def _company_research_customer_segments(text: str) -> list[str]:
    lowered = text.lower()
    specs = (
        ("個人顧客", ("consumer", "retail", "個人")),
        ("法人顧客", ("corporate", "enterprise", "business customers", "法人")),
        (
            "製造業",
            ("manufacturing", "manufacturers", "factory", "industrial", "製造業"),
        ),
        ("販売店・ディーラー", ("dealer", "dealership", "販売店", "ディーラー")),
        ("フリート顧客", ("fleet", "フリート")),
        ("金融サービス利用者", ("financial services customers", "金融サービス利用者")),
    )
    return [label for label, keywords in specs if any(keyword in lowered for keyword in keywords)]


def _company_research_metric_from_evidence(
    evidence: Sequence[CompanyResearchEvidence],
    patterns: Sequence[str],
) -> str | None:
    for item in evidence:
        value = _company_research_metric_text_value(item.body, patterns)
        if value:
            return value
    return None


def _company_research_metric_text_value(text: str, patterns: Sequence[str]) -> str | None:
    unit_pattern = r"(?:(?:[TBM]\s*)?(?:JPY|USD)|兆円|億円|百万円|万円|円|人|名|employees|%|％|倍)?"
    for pattern in patterns:
        match = re.search(
            rf"(?:{pattern})\s*(?:[:：=は])?\s*([+-]?\d[\d,]*(?:\.\d+)?\s*{unit_pattern})",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        value = re.sub(r"\s+", " ", match.group(1)).strip(" .。、、")
        if value:
            return value
    return None


def _company_research_ir_item_for_spec(
    *,
    document_type: str,
    ir_document_type: IRDocumentType,
    source_types: Sequence[ResearchSourceType],
    keywords: Sequence[str],
    report: CompanyResearchReport,
    brief: ResearchBrief,
    cards: Sequence[ResearchBriefSourceCard],
    normalized_evidence: Sequence[CompanyResearchEvidence],
) -> IRSummaryItem:
    matched_cards = [
        card
        for card in cards
        if card.source_type in source_types
        or (
            _company_research_is_ir_evidence_source(card.source_type)
            and (
                _company_research_keyword_match(card.title, keywords)
                or _company_research_keyword_match(card.note, keywords)
            )
        )
    ]
    matched_card = next(
        (card for card in matched_cards if card.source_url),
        matched_cards[0] if matched_cards else None,
    )
    matched_evidence = next(
        (
            row
            for row in report.evidence
            if row.source_type in source_types
            or (
                _company_research_is_ir_evidence_source(row.source_type)
                and _company_research_keyword_match(_research_brief_evidence_text(row), keywords)
            )
        ),
        None,
    )
    matched_normalized = next(
        (
            item
            for item in normalized_evidence
            if item.kind in {"ir_document", "tdnet_disclosure"}
            and (
                item.source_type in source_types
                or _company_research_keyword_match(item.title, keywords)
                or _company_research_keyword_match(item.body, keywords)
            )
        ),
        None,
    )
    key_points = _company_research_ir_key_points(document_type, brief)
    if not key_points and matched_evidence is not None:
        key_points = [_clip_text(matched_evidence.excerpt, max_chars=120)]
    information_status: InformationStatus = "found" if key_points else "unparsed"
    if matched_card is not None:
        return IRSummaryItem(
            document_type=document_type,
            ir_document_type=ir_document_type,
            title=matched_card.title,
            availability="found",
            information_status=information_status,
            summary=_company_research_ir_summary(document_type, key_points, information_status),
            key_points=key_points,
            source_title=matched_card.title,
            source_url=matched_card.source_url,
            evidence_level=_company_research_evidence_level_from_source_types(
                [matched_card.source_type]
            ),
        )
    if matched_evidence is not None:
        return IRSummaryItem(
            document_type=document_type,
            ir_document_type=ir_document_type,
            title=matched_evidence.title,
            availability="found",
            information_status=information_status,
            summary=_company_research_ir_summary(document_type, key_points, information_status),
            key_points=key_points,
            source_title=matched_evidence.title,
            evidence_level=_company_research_evidence_level_from_source_types(
                [matched_evidence.source_type]
            ),
        )
    if matched_normalized is not None:
        return IRSummaryItem(
            document_type=document_type,
            ir_document_type=ir_document_type,
            title=matched_normalized.title,
            availability="found",
            information_status=matched_normalized.information_status,
            summary=_company_research_ir_summary(
                document_type,
                [],
                matched_normalized.information_status,
            ),
            key_points=[],
            source_title=matched_normalized.source_title or matched_normalized.title,
            source_url=matched_normalized.source_url,
            evidence_level=_company_research_evidence_level_from_source_types(
                [matched_normalized.source_type]
            ),
        )
    return IRSummaryItem(
        document_type=document_type,
        ir_document_type=ir_document_type,
        title="未取得",
        availability="missing",
        information_status="missing",
        summary=f"{document_type}は未取得です。公式IR、TDnet、EDINETで追加確認してください。",
        key_points=[],
        evidence_level="missing",
    )


def _company_research_is_ir_evidence_source(
    source_type: ResearchSourceType | str,
) -> bool:
    return source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES


def _company_research_ir_key_points(
    document_type: str,
    brief: ResearchBrief,
) -> list[str]:
    fact_summary = brief.fact_summary
    if fact_summary is None:
        return []
    if document_type in {"決算短信", "決算説明資料"}:
        return [item.value for item in fact_summary.earnings_outlook[:3]]
    if document_type == "配当・自社株買い":
        return [item.value for item in fact_summary.shareholder_return_policy[:3]]
    if document_type == "適時開示":
        return [item.value for item in fact_summary.recent_events if item.source_type == "tdnet"][
            :3
        ]
    if document_type == "業績予想修正":
        return [
            item.value
            for item in fact_summary.earnings_outlook
            if _company_research_keyword_match(
                item.value,
                ("業績予想修正", "上方修正", "下方修正", "forecast revision"),
            )
        ][:3]
    return []


def _company_research_ir_summary(
    document_type: str,
    key_points: Sequence[str],
    information_status: InformationStatus,
) -> str:
    if key_points:
        return f"{document_type}から確認できる要点があります。"
    if information_status == "unparsed":
        return "資料タイトルは取得済みですが、本文は未解析です。詳細はリンク先で確認してください。"
    return f"{document_type}の出典は確認できています。詳細は出典カードで確認してください。"


def _company_research_latest_topic_type(
    source_type: ResearchSourceType | str,
    text: str,
) -> LatestTopicType:
    lowered_text = text.lower()
    if any(keyword in lowered_text for keyword in ("業績予想修正", "forecast revision")):
        return "forecast_revision"
    if any(keyword in lowered_text for keyword in ("決算", "earnings", "financial results")):
        return "earnings"
    if any(
        keyword in lowered_text
        for keyword in (
            "配当",
            "自己株式",
            "自社株買い",
            "株主還元",
            "dividend",
            "buyback",
        )
    ):
        return "shareholder_return"
    if any(
        keyword in lowered_text
        for keyword in (
            "m&a",
            "merger",
            "acquisition",
            "spin-off",
            "restructuring",
            "合併",
            "買収",
            "会社分割",
            "事業譲渡",
            "事業再編",
        )
    ):
        return "business_reorganization"
    if any(
        keyword in lowered_text
        for keyword in (
            "governance",
            "audit",
            "lawsuit",
            "不祥事",
            "訴訟",
            "監査",
            "規制",
        )
    ):
        return "governance"
    if any(
        keyword in lowered_text
        for keyword in (
            "product",
            "new product",
            "service launch",
            "services",
            "製品",
            "新製品",
            "サービス開始",
        )
    ):
        return "product"
    if source_type == "news":
        return "news"
    if source_type == "tdnet":
        return "tdnet"
    if source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES:
        return "ir_disclosure"
    return "unknown"


def _company_research_news_impact_hint(
    viewpoint: StockNewsInvestmentViewpoint,
    text: str = "",
    *,
    source_type: ResearchSourceType | str = "",
) -> NewsImpactHint:
    lowered_text = text.lower()
    if any(
        keyword in lowered_text
        for keyword in (
            "決算",
            "業績予想",
            "上方修正",
            "下方修正",
            "配当",
            "自己株式",
            "自社株買い",
            "earnings",
            "forecast",
            "guidance",
            "dividend",
            "buyback",
        )
    ):
        return "financial"
    if any(
        keyword in lowered_text
        for keyword in (
            "m&a",
            "merger",
            "acquisition",
            "spin-off",
            "restructuring",
            "合併",
            "買収",
            "会社分割",
            "事業譲渡",
            "事業再編",
        )
    ):
        return "business"
    if any(
        keyword in lowered_text
        for keyword in (
            "governance",
            "audit",
            "lawsuit",
            "不祥事",
            "訴訟",
            "監査",
            "規制",
        )
    ):
        return "governance"
    if any(
        keyword in lowered_text
        for keyword in (
            "product",
            "new product",
            "service launch",
            "services",
            "製品",
            "新製品",
            "サービス開始",
        )
    ):
        return "product"
    if source_type == "tdnet":
        return "ir"
    labels: dict[
        StockNewsInvestmentViewpoint,
        NewsImpactHint,
    ] = {
        "earnings": "financial",
        "growth": "business",
        "shareholder_return": "financial",
        "risk": "business",
        "macro": "market",
        "other": "unknown",
    }
    return labels.get(viewpoint, "unknown")


def _company_research_values(
    items: Sequence[ResearchFactItem],
    *,
    limit: int,
) -> list[str]:
    values: list[str] = []
    for item in items:
        values.extend(part.strip() for part in item.value.split("、") if part.strip())
    return _unique_text(values)[:limit]


def _company_research_keyword_match(text: str, keywords: Sequence[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _company_research_evidence_level_from_source_types(
    source_types: Sequence[ResearchSourceType | str],
) -> ResearchEvidenceLevel:
    cleaned = [str(source_type) for source_type in source_types if str(source_type).strip()]
    if not cleaned:
        return "missing"
    if any(source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES for source_type in cleaned):
        return "high"
    if any(source_type == "provider_profile" for source_type in cleaned):
        return "medium"
    if any(source_type in {"news", "user_note"} for source_type in cleaned):
        return "low"
    return "low"


def _unique_company_news_items(
    items: Sequence[NewsSummaryItem],
) -> list[NewsSummaryItem]:
    unique_by_key: dict[tuple[str, LatestTopicType], NewsSummaryItem] = {}
    for item in items:
        key = (item.title, item.topic_type)
        existing = unique_by_key.get(key)
        if existing is None:
            unique_by_key[key] = item
            continue
        if not existing.source_url and item.source_url:
            unique_by_key[key] = item
    return list(unique_by_key.values())


_INVESTMENT_INSIGHT_POSITIVE_KEYWORDS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "業績改善",
        ("増収", "増益", "利益改善", "revenue growth", "profit growth"),
        "業績改善に関係する表現を確認したため。",
    ),
    (
        "上方修正",
        ("上方修正", "raised guidance", "raises guidance", "raise guidance"),
        "業績予想の上方修正に関係する表現を確認したため。",
    ),
    (
        "株主還元",
        ("増配", "自社株買い", "株主還元", "dividend increase", "buyback"),
        "配当や自社株買いなど株主還元に関係する表現を確認したため。",
    ),
    (
        "成長材料",
        (
            "成長",
            "成長戦略",
            "受注増",
            "新製品",
            "市場拡大",
            "中期経営計画",
            "growth",
            "market expansion",
            "new product",
            "order growth",
        ),
        "成長領域や事業拡大に関係する表現を確認したため。",
    ),
)
_INVESTMENT_INSIGHT_NEGATIVE_KEYWORDS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "業績悪化",
        ("減収", "減益", "利益率悪化", "decline", "decrease", "margin pressure"),
        "業績悪化や利益率低下に関係する表現を確認したため。",
    ),
    (
        "下方修正",
        ("下方修正", "lowered guidance", "lower guidance", "cut guidance"),
        "業績予想の下方修正に関係する表現を確認したため。",
    ),
    (
        "株主還元の注意",
        ("減配", "dividend cut", "reduced dividend"),
        "配当や株主還元の後退に関係する表現を確認したため。",
    ),
    (
        "事業リスク",
        (
            "訴訟",
            "不祥事",
            "需要減",
            "コスト増",
            "為替リスク",
            "地政学リスク",
            "供給制約",
            "リスク",
            "lawsuit",
            "scandal",
            "demand decline",
            "cost increase",
            "foreign exchange risk",
            "geopolitical risk",
            "supply constraint",
        ),
        "事業リスクや外部環境の注意点に関係する表現を確認したため。",
    ),
)
_INVESTMENT_INSIGHT_NEUTRAL_SOURCE_TYPES: set[ResearchSourceType] = {
    "provider_profile",
    "user_note",
}


def _investment_insight_positive_points(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> list[InvestmentInsightItem]:
    items: list[InvestmentInsightItem] = []
    items.extend(
        _investment_insight_item_from_material(
            material,
            signal="positive",
            reason="ResearchBriefで良材料候補として分類したため。",
        )
        for material in brief.positive_materials
        if material.source_type != "provider_profile"
    )
    items.extend(
        item
        for row in report.evidence
        if row.source_type != "provider_profile"
        for item in [
            _investment_insight_item_from_evidence(
                row,
                signal="positive",
                keyword_specs=_INVESTMENT_INSIGHT_POSITIVE_KEYWORDS,
            )
        ]
        if item is not None
    )
    if news_report is not None:
        items.extend(
            _investment_insight_item_from_news(row, signal="positive")
            for row in news_report.news
            if row.sentiment_for_investment == "positive"
        )
    if external_research_result is not None:
        items.extend(
            item
            for entry in external_research_result.entries
            if entry.source_type != "provider_profile"
            for item in [
                _investment_insight_item_from_external_entry(
                    entry,
                    signal="positive",
                    keyword_specs=_INVESTMENT_INSIGHT_POSITIVE_KEYWORDS,
                )
            ]
            if item is not None
        )
    return _unique_investment_insight_items(items)[:6]


def _investment_insight_negative_points(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> list[InvestmentInsightItem]:
    items: list[InvestmentInsightItem] = []
    items.extend(
        _investment_insight_item_from_material(
            material,
            signal="negative",
            reason="ResearchBriefで注意材料候補として分類したため。",
        )
        for material in brief.caution_materials
        if material.source_type != "provider_profile"
    )
    items.extend(
        item
        for row in report.evidence
        if row.source_type != "provider_profile"
        for item in [
            _investment_insight_item_from_evidence(
                row,
                signal="negative",
                keyword_specs=_INVESTMENT_INSIGHT_NEGATIVE_KEYWORDS,
            )
        ]
        if item is not None
    )
    if news_report is not None:
        items.extend(
            _investment_insight_item_from_news(row, signal="negative")
            for row in news_report.news
            if row.sentiment_for_investment in {"negative", "mixed"}
        )
        if news_report.news and not _investment_insight_has_official_source(report, brief):
            lead = news_report.news[0]
            items.append(
                InvestmentInsightItem(
                    label="公式資料の裏取り不足",
                    summary=(
                        "ニュース由来の材料は確認できますが、公式IRでの裏取りが不足しています。"
                    ),
                    signal="negative",
                    source_title=lead.title,
                    source_type="news",
                    source_confidence=_research_brief_source_confidence("news"),
                    published_at=lead.published_at,
                    reason="ニュースはありますが、公式資料を含む根拠が不足しているため。",
                )
            )
    if external_research_result is not None:
        items.extend(
            item
            for entry in external_research_result.entries
            if entry.source_type != "provider_profile"
            for item in [
                _investment_insight_item_from_external_entry(
                    entry,
                    signal="negative",
                    keyword_specs=_INVESTMENT_INSIGHT_NEGATIVE_KEYWORDS,
                )
            ]
            if item is not None
        )
    return _unique_investment_insight_items(items)[:6]


def _investment_insight_neutral_points(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    external_research_result: ExternalResearchFetchResult | None,
) -> list[InvestmentInsightItem]:
    items: list[InvestmentInsightItem] = []
    fact_summary = brief.fact_summary
    if fact_summary is not None:
        fact_items = [
            *fact_summary.business_overview,
            *fact_summary.business_segments,
            *fact_summary.business_regions,
            *fact_summary.revenue_drivers,
        ]
        items.extend(
            InvestmentInsightItem(
                label=item.label,
                summary=item.value,
                signal="neutral",
                source_title=item.source_title,
                source_type=item.source_type,
                source_confidence=item.source_confidence,
                published_at=item.published_at,
                reason="会社概要や事業構造として有用ですが、方向感は断定していません。",
            )
            for item in fact_items
        )
    for row in report.evidence:
        if row.source_type not in _INVESTMENT_INSIGHT_NEUTRAL_SOURCE_TYPES:
            continue
        items.append(
            InvestmentInsightItem(
                label=_research_brief_source_type_label(row.source_type),
                summary=_investment_insight_neutral_summary(row),
                signal="neutral",
                source_title=row.title,
                source_type=row.source_type,
                source_confidence=_research_brief_source_confidence(row.source_type),
                published_at=row.published_at,
                reason="補助情報として確認できる内容で、良悪どちらにも寄せていません。",
            )
        )
    if external_research_result is not None:
        for entry in external_research_result.entries:
            if entry.source_type != "provider_profile":
                continue
            summary = entry.content_summary or "外部プロフィール情報を確認しています。"
            items.append(
                InvestmentInsightItem(
                    label="会社概要",
                    summary=_clip_text(summary, max_chars=150),
                    signal="neutral",
                    source_title=entry.title,
                    source_type=entry.source_type,
                    source_confidence=_research_brief_source_confidence(entry.source_type),
                    published_at=entry.published_at,
                    reason="外部プロフィール情報は補助材料として扱うため。",
                )
            )
    if not items and report.evidence:
        lead = report.evidence[0]
        items.append(
            InvestmentInsightItem(
                label="確認済み資料",
                summary=_investment_insight_neutral_summary(lead),
                signal="neutral",
                source_title=lead.title,
                source_type=lead.source_type,
                source_confidence=_research_brief_source_confidence(lead.source_type),
                published_at=lead.published_at,
                reason="出典はありますが、方向感は追加確認が必要なため。",
            )
        )
    return _unique_investment_insight_items(items)[:5]


def _investment_insight_item_from_material(
    material: ResearchBriefMaterial,
    *,
    signal: InvestmentSignal,
    reason: str,
) -> InvestmentInsightItem:
    return InvestmentInsightItem(
        label=material.label,
        summary=material.summary,
        signal=signal,
        source_title=material.source_title,
        source_type=material.source_type,
        source_confidence=material.source_confidence,
        published_at=material.published_at,
        reason=reason,
    )


def _investment_insight_item_from_news(
    row: StockNewsEvidence,
    *,
    signal: InvestmentSignal,
) -> InvestmentInsightItem:
    summary = _clip_text(
        f"ニュースでは「{row.summary}」と確認できます。",
        max_chars=160,
    )
    return InvestmentInsightItem(
        label=_investment_insight_news_label(row),
        summary=summary,
        signal=signal,
        source_title=row.title,
        source_type="news",
        source_confidence=_research_brief_source_confidence("news"),
        published_at=row.published_at,
        reason="URL付きニュースの投資観点分類を確認材料として使ったため。",
    )


def _investment_insight_item_from_evidence(
    row: ResearchEvidence,
    *,
    signal: InvestmentSignal,
    keyword_specs: Sequence[tuple[str, tuple[str, ...], str]],
) -> InvestmentInsightItem | None:
    match = _investment_insight_keyword_match(_research_brief_evidence_text(row), keyword_specs)
    if match is None:
        return None
    label, keywords, reason = match
    snippet = _investment_insight_keyword_snippet(_research_brief_evidence_text(row), keywords)
    return InvestmentInsightItem(
        label=label,
        summary=f"出典では、{label}に関係する記述（{snippet}）を確認できます。",
        signal=signal,
        source_title=row.title,
        source_type=row.source_type,
        source_confidence=_research_brief_source_confidence(row.source_type),
        published_at=row.published_at,
        reason=reason,
    )


def _investment_insight_item_from_external_entry(
    entry: ExternalResearchFetchManifestEntry,
    *,
    signal: InvestmentSignal,
    keyword_specs: Sequence[tuple[str, tuple[str, ...], str]],
) -> InvestmentInsightItem | None:
    text = " ".join(part for part in (entry.title, entry.content_summary) if part.strip())
    match = _investment_insight_keyword_match(text, keyword_specs)
    if match is None:
        return None
    label, keywords, reason = match
    snippet = _investment_insight_keyword_snippet(text, keywords)
    return InvestmentInsightItem(
        label=label,
        summary=f"外部参照ソースでは、{label}に関係する記述（{snippet}）を確認できます。",
        signal=signal,
        source_title=entry.title,
        source_type=entry.source_type,
        source_confidence=_research_brief_source_confidence(entry.source_type),
        published_at=entry.published_at,
        reason=reason,
    )


def _investment_insight_keyword_match(
    text: str,
    keyword_specs: Sequence[tuple[str, tuple[str, ...], str]],
) -> tuple[str, tuple[str, ...], str] | None:
    lowered = text.lower()
    for label, keywords, reason in keyword_specs:
        if any(keyword.lower() in lowered for keyword in keywords):
            return label, keywords, reason
    return None


def _investment_insight_keyword_snippet(text: str, keywords: Sequence[str]) -> str:
    sentences = [
        sentence.strip(" ・-")
        for sentence in re.split(r"(?<=[。.!?])\s+|[\r\n]+", text)
        if sentence.strip()
    ]
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    for sentence in sentences or [text]:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            return f"「{_clip_text(sentence, max_chars=82)}」"
    return f"「{_clip_text(text, max_chars=82)}」"


def _investment_insight_news_label(row: StockNewsEvidence) -> str:
    labels: dict[StockNewsInvestmentViewpoint, str] = {
        "earnings": "業績ニュース",
        "growth": "成長ニュース",
        "shareholder_return": "株主還元ニュース",
        "risk": "リスクニュース",
        "macro": "外部環境ニュース",
        "other": "ニュース材料",
    }
    return labels.get(row.investment_viewpoint, "ニュース材料")


def _investment_insight_neutral_summary(row: ResearchEvidence) -> str:
    cleaned = _research_brief_clean_provider_text(row.excerpt)
    if row.source_type == "provider_profile":
        readable = _research_brief_readable_business_overview(cleaned)
        return _clip_text(readable, max_chars=160)
    source_type = _research_brief_source_type_label(row.source_type)
    return _clip_text(f"{source_type}から確認できる補助情報です。{cleaned}", max_chars=160)


def _investment_insight_confirmation_gaps(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    news_report: StockNewsReport | None,
) -> list[str]:
    gaps: list[str] = []
    missing_metrics = set(brief.missing_metrics)
    has_news = news_report is not None and bool(news_report.news)
    has_official = _investment_insight_has_official_source(report, brief)
    if has_news and not has_official:
        gaps.append("ニュースはありますが、公式IRで裏取りできていません。")
    if not has_official:
        gaps.append("決算短信・有価証券報告書・決算説明資料などの公式資料が不足しています。")
    earnings_missing = [
        metric for metric in ("売上高", "営業利益", "純利益", "EPS") if metric in missing_metrics
    ]
    if earnings_missing:
        if "売上高" in earnings_missing:
            rest = [metric for metric in earnings_missing if metric != "売上高"]
            suffix = f"{'・'.join(rest)}も確認してください。" if rest else ""
            gaps.append(f"売上高が未確認です。{suffix}")
        else:
            gaps.append(f"{'・'.join(earnings_missing)}が未確認です。")
    valuation_missing = [metric for metric in ("PER", "PBR", "ROE") if metric in missing_metrics]
    if valuation_missing:
        gaps.append(f"{'/'.join(valuation_missing)}が未確認です。")
    if "配当" in missing_metrics:
        gaps.append("配当方針・配当実績が未確認です。")
    fact_summary = brief.fact_summary
    if fact_summary is not None:
        gaps.extend(
            f"{item.label}: {item.reason}。{item.next_source_hint}で確認してください。"
            for item in fact_summary.missing_items
        )
    gaps.extend(_investment_insight_gap_display_text(gap) for gap in brief.confirmation_gaps)
    if not report.evidence:
        gaps.append("source-backed な判断材料が不足しています。")
    return _unique_text(gaps)[:10]


def _investment_insight_gap_display_text(gap: str) -> str:
    cleaned = " ".join(gap.split())
    if cleaned.startswith("未確認の定量指標:"):
        metrics = cleaned.split(":", 1)[1].strip()
        return f"主要な定量指標（{metrics}）が未確認です。"
    if cleaned.startswith("ニュース確認:"):
        warning = cleaned.split(":", 1)[1].strip()
        return f"ニュース根拠の確認が必要です: {warning}"
    if "登録済みResearch資料がありません" in cleaned:
        return "保存済みResearch資料が不足しています。公式IRや決算資料を確認してください。"
    if "検索できたResearch根拠がありません" in cleaned:
        return "関連する根拠資料をまだ見つけられていません。"
    return cleaned


def _investment_insight_action_hints(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    positive_points: Sequence[InvestmentInsightItem],
    negative_points: Sequence[InvestmentInsightItem],
    confirmation_gaps: Sequence[str],
    news_report: StockNewsReport | None,
) -> list[InvestmentActionHint]:
    hints: list[InvestmentActionHint] = []
    has_sources = bool(
        report.evidence or brief.source_cards or (news_report is not None and news_report.news)
    )
    has_official = _investment_insight_has_official_source(report, brief)
    if not has_sources or report.data_quality.evidence_count <= 0:
        hints.append("insufficient_evidence")
    if not has_official:
        hints.append("check_official_materials")
    if news_report is not None and news_report.news and (brief.missing_metrics or not has_official):
        hints.append("wait_for_confirmation")
    if positive_points and negative_points:
        hints.append("review")
    if has_sources and "insufficient_evidence" not in hints:
        hints.append("watch")
    if not hints and confirmation_gaps:
        hints.append("watch")
    return list(dict.fromkeys(hints))[:5]


def _investment_insight_confidence(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> ResearchSourceConfidence:
    source_cards = list(brief.source_cards)
    if external_research_result is not None:
        source_cards.extend(
            ResearchBriefSourceCard(
                title=entry.title,
                source_type=entry.source_type,
                provider=entry.provider,
                source_url=entry.source_url,
                published_at=entry.published_at,
                fetched_at=entry.fetched_at,
                freshness_status=entry.freshness_status,
                source_confidence=_research_brief_source_confidence(entry.source_type),
            )
            for entry in external_research_result.entries
        )
    if news_report is not None:
        source_cards.extend(
            ResearchBriefSourceCard(
                title=row.title,
                source_type="news",
                provider=row.source,
                source_url=row.url,
                published_at=row.published_at,
                freshness_status=row.freshness_status,
                source_confidence=_research_brief_source_confidence("news"),
            )
            for row in news_report.news
        )
    if not source_cards and not report.evidence:
        return "unknown"
    high_count = sum(1 for card in source_cards if card.source_confidence == "high")
    medium_count = sum(1 for card in source_cards if card.source_confidence == "medium")
    low_count = sum(1 for card in source_cards if card.source_confidence == "low")
    if high_count and report.data_quality.status == "OK" and len(brief.metrics) >= 4:
        return "high"
    if high_count or medium_count:
        return "medium"
    if low_count:
        return "low"
    return "unknown"


def _investment_insight_headline(
    *,
    positive_points: Sequence[InvestmentInsightItem],
    negative_points: Sequence[InvestmentInsightItem],
    neutral_points: Sequence[InvestmentInsightItem],
    confirmation_gaps: Sequence[str],
) -> str:
    if positive_points and negative_points:
        return "良い材料と注意材料が混在しており、追加確認が必要です。"
    if positive_points:
        return "良い材料候補はありますが、主要指標と公式資料の確認が必要です。"
    if negative_points:
        return "注意材料を優先して確認する状態です。"
    if neutral_points:
        return "会社概要など補助情報が中心で、方向感はまだ限定的です。"
    if confirmation_gaps:
        return "根拠が不足しており、判断前の資料確認が必要です。"
    return "現時点で投資判断向けに整理できる材料は限定的です。"


def _investment_insight_status_label(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    positive_points: Sequence[InvestmentInsightItem],
    negative_points: Sequence[InvestmentInsightItem],
    news_report: StockNewsReport | None,
) -> InvestmentViewStatus:
    has_news = news_report is not None and bool(news_report.news)
    has_evidence = bool(report.evidence or brief.source_cards)
    has_official = _investment_insight_has_official_source(report, brief)
    if not has_evidence and not has_news:
        return "判断材料不足"
    if has_news and not report.evidence and not has_official:
        return "ニュース先行"
    if positive_points and negative_points:
        return "材料混在"
    if not has_official:
        return "公式資料確認待ち"
    if _investment_insight_has_major_metric_gap(brief):
        return "定量指標不足"
    return "監視向き"


def _investment_insight_confidence_label(
    status_label: InvestmentViewStatus,
    confidence: ResearchSourceConfidence,
) -> str:
    if status_label in {"判断材料不足", "公式資料確認待ち", "ニュース先行"}:
        return "低"
    if status_label == "定量指標不足":
        return "低〜中"
    if status_label == "材料混在":
        return "中"
    labels: dict[ResearchSourceConfidence, str] = {
        "high": "中〜高",
        "medium": "中",
        "low": "低",
        "unknown": "低",
    }
    return labels[confidence]


def _investment_insight_primary_action_label(status_label: InvestmentViewStatus) -> str:
    labels: dict[InvestmentViewStatus, str] = {
        "追加確認が必要": "確認資料を追加",
        "監視向き": "継続して材料を確認",
        "材料混在": "良悪材料を比較",
        "判断材料不足": "資料追加が必要",
        "公式資料確認待ち": "決算資料を確認",
        "ニュース先行": "公式IRで裏取り",
        "定量指標不足": "PER/PBR/ROEを確認",
    }
    return labels[status_label]


def _investment_insight_has_major_metric_gap(brief: ResearchBrief) -> bool:
    missing = set(brief.missing_metrics)
    return bool(missing.intersection({"売上高", "営業利益", "純利益", "EPS", "PER", "PBR", "ROE"}))


def _investment_insight_short_summary(
    report: CompanyResearchReport,
    brief: ResearchBrief,
    *,
    positive_points: Sequence[InvestmentInsightItem],
    negative_points: Sequence[InvestmentInsightItem],
    neutral_points: Sequence[InvestmentInsightItem],
    confirmation_gaps: Sequence[str],
    action_hints: Sequence[InvestmentActionHint],
    confidence: ResearchSourceConfidence,
    status_label: InvestmentViewStatus,
) -> str:
    if _investment_insight_has_official_source(report, brief):
        source_phrase = "公式資料を含む根拠から、この企業を見る材料を確認できます。"
    elif positive_points or negative_points:
        source_phrase = "外部ニュースや補助データから、一部の判断材料を確認できます。"
    elif neutral_points:
        source_phrase = "会社概要や外部プロフィールなど、基本情報を整理しています。"
    else:
        source_phrase = "現時点で確認できた根拠はまだ限られています。"

    if confirmation_gaps:
        gap_phrase = "一方で、公式IR・決算資料・主要財務指標の裏取りがまだ必要です。"
    elif negative_points:
        gap_phrase = "一方で、注意材料の前提や公開日を確認してから読み比べる必要があります。"
    else:
        gap_phrase = "一方で、出典の公開日と対象期間は念のため確認してください。"

    if status_label == "材料混在" or "review" in action_hints:
        action_phrase = "現時点では、良い材料と注意材料を比較して見る状態です。"
    elif status_label == "判断材料不足" or "insufficient_evidence" in action_hints:
        action_phrase = "現時点では、結論を急がず資料追加を優先する状態です。"
    elif status_label in {"公式資料確認待ち", "ニュース先行", "定量指標不足"}:
        action_phrase = "現時点では、売買判断ではなく「監視・追加確認」向きです。"
    else:
        confidence_text = _investment_insight_confidence_phrase(confidence)
        action_phrase = f"現時点では、情報源の信頼度は{confidence_text}で、継続確認向きです。"
    return " ".join((source_phrase, gap_phrase, action_phrase))


_INVESTMENT_QUESTION_SPECS: tuple[tuple[InvestmentQuestionCategory, str], ...] = (
    ("business_model", "この会社は何で稼いでいるか？"),
    ("financial_trend", "売上・利益は伸びているか？"),
    ("profitability", "利益率は良いか？"),
    ("forecast", "今期見通しは強いか？"),
    ("growth_driver", "成長ドライバーは何か？"),
    ("risk", "注意すべきリスクは何か？"),
    ("shareholder_return", "株主還元はどうか？"),
    ("valuation", "割高・割安感はあるか？"),
    ("recent_news_impact", "直近ニュースは業績に影響しそうか？"),
    ("key_takeaway", "この銘柄を見るうえで一番重要な論点は何か？"),
)
_INVESTMENT_QUESTION_MISSING_ITEM_LABELS: dict[InvestmentQuestionCategory, str] = {
    "business_model": "主力事業・収益構造",
    "financial_trend": "売上高・営業利益・純利益の推移",
    "profitability": "営業利益率・純利益率",
    "forecast": "通期業績予想・会社計画",
    "growth_driver": "成長ドライバー",
    "risk": "事業等のリスク",
    "shareholder_return": "配当方針・株主還元",
    "valuation": "PER / PBR / ROE / 配当利回り",
    "recent_news_impact": "直近ニュースの業績影響",
    "key_takeaway": "最優先で確認する論点",
}
_INVESTMENT_QUESTION_FORBIDDEN_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("買い推奨", "確認候補"),
    ("購入推奨", "確認候補"),
    ("売り推奨", "注意して確認"),
    ("売却推奨", "注意して確認"),
    ("今すぐ買う", "追加確認する"),
    ("今すぐ売る", "追加確認する"),
    ("買いです", "確認材料があります"),
    ("売りです", "注意材料があります"),
    ("割安です", "割安とは断定できません"),
    ("割高です", "割高とは断定できません"),
    ("投資妙味があります", "比較材料があります"),
    ("成長が期待されます", "成長に関する記述があります"),
)


def _investment_question_answer(
    category: InvestmentQuestionCategory,
    report: CompanyResearchReport,
    brief: ResearchBrief,
    insight: InvestmentInsight,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> InvestmentQuestionAnswer:
    if category == "business_model":
        return _investment_question_business_model(category, brief)
    if category == "financial_trend":
        return _investment_question_financial_trend(category, brief)
    if category == "profitability":
        return _investment_question_profitability(category, brief)
    if category == "forecast":
        return _investment_question_forecast(category, brief, insight)
    if category == "growth_driver":
        return _investment_question_growth_driver(category, brief, insight)
    if category == "risk":
        return _investment_question_risk(category, brief, insight)
    if category == "shareholder_return":
        return _investment_question_shareholder_return(category, brief, insight)
    if category == "valuation":
        return _investment_question_valuation(category, brief)
    if category == "recent_news_impact":
        return _investment_question_recent_news_impact(
            category,
            brief,
            news_report=news_report,
        )
    return _investment_question_key_takeaway(
        category,
        report,
        brief,
        insight,
        news_report=news_report,
        external_research_result=external_research_result,
    )


def _investment_question_business_model(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
) -> InvestmentQuestionAnswer:
    fact_summary = brief.fact_summary
    if fact_summary is None:
        return _investment_question_missing_answer(
            category,
            "事業概要を判断できる資料が未取得です。主力事業、主要セグメント、地域、収益源を公式資料で追加確認してください。",
            "事業概要・セグメント情報が未取得です。",
        )
    items = [
        *fact_summary.business_overview,
        *fact_summary.business_segments,
        *fact_summary.business_regions,
        *fact_summary.revenue_drivers,
    ]
    if not items:
        return _investment_question_missing_answer(
            category,
            "外部データから事業概要は一部確認できますが、主力セグメントや収益構造は公式資料で追加確認が必要です。",
            "事業概要・セグメント情報が未取得です。",
        )

    overview = fact_summary.business_overview[0].value if fact_summary.business_overview else ""
    segments = _investment_question_values(fact_summary.business_segments, limit=2)
    regions = _investment_question_values(fact_summary.business_regions, limit=2)
    drivers = _investment_question_values(fact_summary.revenue_drivers, limit=2)
    level = _investment_question_evidence_level_for_fact_items(items)
    source_phrase = "公式資料から" if level == "high" else "外部データから"
    sentences: list[str] = []
    if overview:
        sentences.append(f"{source_phrase}、{_clip_text(overview, max_chars=120)}")
    detail_parts: list[str] = []
    if segments:
        detail_parts.append(f"主要事業は{'、'.join(segments)}")
    if drivers:
        detail_parts.append(f"収益源は{'、'.join(drivers)}")
    if regions:
        detail_parts.append(f"地域展開は{'、'.join(regions)}")
    if detail_parts:
        sentences.append(f"確認できる範囲では、{'、'.join(detail_parts)}です。")
    if level != "high":
        sentences.append("主力セグメントや収益構造は公式資料で追加確認が必要です。")
    else:
        sentences.append("セグメント別売上や収益構造は決算資料で続けて確認してください。")
    return _investment_question_build_answer(
        category,
        " ".join(sentences),
        evidence_level=level,
        source_titles=_investment_question_titles_from_fact_items(items),
    )


def _investment_question_financial_trend(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
) -> InvestmentQuestionAnswer:
    metrics = _investment_question_metrics_by_key(brief)
    metric_rows = _investment_question_metric_texts(
        metrics,
        ("revenue", "operating_income", "net_income", "eps"),
    )
    trend_items = _investment_question_fact_items_by_keywords(
        _investment_question_fact_items(brief),
        (
            "増収",
            "増益",
            "減収",
            "減益",
            "前年比",
            "revenue growth",
            "profit growth",
            "decline",
        ),
    )
    source_types = [metric.source_type for metric in metrics.values()]
    source_types.extend(item.source_type for item in trend_items)
    if not metric_rows and not trend_items:
        return _investment_question_missing_answer(
            category,
            "売上高・営業利益・純利益の推移が未取得のため、業績トレンドは判断できません。",
            "売上高・営業利益・純利益・EPSの推移が未取得です。",
        )

    sentences: list[str] = []
    if metric_rows:
        sentences.append(f"{'、'.join(metric_rows[:4])}を確認できます。")
    if trend_items:
        sentences.append(
            f"業績変化に関する記述として、{_clip_text(trend_items[0].value, max_chars=100)}を確認できます。"
        )
    sentences.append("前年同期比や複数期の推移は、決算短信・有価証券報告書で追加確認してください。")
    return _investment_question_build_answer(
        category,
        " ".join(sentences),
        evidence_level=_investment_question_evidence_level_from_source_types(source_types),
        source_titles=[
            *_investment_question_titles_from_metrics(metrics.values()),
            *_investment_question_titles_from_fact_items(trend_items),
        ],
        missing_reason=_investment_question_missing_metrics_reason(
            brief,
            ("売上高", "営業利益", "純利益", "EPS"),
        ),
    )


def _investment_question_profitability(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
) -> InvestmentQuestionAnswer:
    metrics = _investment_question_metrics_by_key(brief)
    metric_rows = _investment_question_metric_texts(
        metrics,
        ("operating_income", "net_income", "roe"),
    )
    profitability_items = _investment_question_fact_items_by_keywords(
        _investment_question_fact_items(brief),
        (
            "利益率",
            "収益性",
            "価格転嫁",
            "コスト増",
            "margin",
            "profitability",
            "roe",
        ),
    )
    if not metric_rows and not profitability_items:
        return _investment_question_missing_answer(
            category,
            "営業利益率・純利益率が未取得のため、収益性は判断できません。",
            "営業利益率・純利益率・収益性に関する情報が未取得です。",
        )

    source_types = [metric.source_type for metric in metrics.values()]
    source_types.extend(item.source_type for item in profitability_items)
    sentences: list[str] = []
    if metric_rows:
        sentences.append(f"{'、'.join(metric_rows[:3])}を確認できます。")
    if profitability_items:
        sentences.append(
            f"収益性に関する記述として、{_clip_text(profitability_items[0].value, max_chars=96)}を確認できます。"
        )
    sentences.append("営業利益率・純利益率、コスト要因、価格転嫁は公式資料で追加確認が必要です。")
    return _investment_question_build_answer(
        category,
        " ".join(sentences),
        evidence_level=_investment_question_evidence_level_from_source_types(source_types),
        source_titles=[
            *_investment_question_titles_from_metrics(metrics.values()),
            *_investment_question_titles_from_fact_items(profitability_items),
        ],
        missing_reason=_investment_question_missing_metrics_reason(
            brief,
            ("営業利益", "純利益", "ROE"),
        ),
    )


def _investment_question_forecast(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
    insight: InvestmentInsight,
) -> InvestmentQuestionAnswer:
    outlook_items = list(brief.fact_summary.earnings_outlook if brief.fact_summary else [])
    revision_points = _investment_question_insight_points_by_keywords(
        [*insight.positive_points, *insight.negative_points],
        ("上方修正", "下方修正", "通期予想", "業績予想", "guidance", "forecast"),
    )
    if not outlook_items and not revision_points:
        return _investment_question_missing_answer(
            category,
            "通期業績予想や会社計画が未取得のため、今期見通しは判断できません。",
            "通期業績予想、会社計画、業績修正に関する情報が未取得です。",
        )

    source_types = [item.source_type for item in outlook_items]
    source_types.extend(point.source_type for point in revision_points)
    lead_text = (
        outlook_items[0].value
        if outlook_items
        else revision_points[0].summary if revision_points else ""
    )
    answer = (
        f"今期見通しに関する材料として、{_clip_text(lead_text, max_chars=110)}を確認できます。"
        "会社計画の前提、上方修正・下方修正の有無、市場コンセンサスとの差は公式IRで追加確認してください。"
    )
    return _investment_question_build_answer(
        category,
        answer,
        evidence_level=_investment_question_evidence_level_from_source_types(source_types),
        source_titles=[
            *_investment_question_titles_from_fact_items(outlook_items),
            *_investment_question_titles_from_insight_points(revision_points),
        ],
    )


def _investment_question_growth_driver(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
    insight: InvestmentInsight,
) -> InvestmentQuestionAnswer:
    fact_summary = brief.fact_summary
    revenue_driver_items = list(fact_summary.revenue_drivers if fact_summary else [])
    growth_items = _investment_question_fact_items_by_keywords(
        list(fact_summary.positive_materials if fact_summary else []),
        (
            "成長",
            "成長戦略",
            "市場拡大",
            "新製品",
            "受注増",
            "中期経営計画",
            "growth",
            "market expansion",
            "new product",
        ),
    )
    growth_points = _investment_question_insight_points_by_keywords(
        insight.positive_points,
        (
            "成長",
            "成長戦略",
            "市場拡大",
            "新製品",
            "受注増",
            "growth",
            "market expansion",
        ),
    )
    if not growth_items and not growth_points and not revenue_driver_items:
        return _investment_question_missing_answer(
            category,
            "成長ドライバーを判断できる公式資料・ニュースが不足しています。",
            "成長セグメント、新製品、市場拡大、受注増などの情報が未取得です。",
        )

    source_types = [item.source_type for item in [*growth_items, *revenue_driver_items]]
    source_types.extend(point.source_type for point in growth_points)
    lead_text = _investment_question_lead_text(
        fact_items=[*growth_items, *revenue_driver_items],
        insight_points=growth_points,
    )
    answer = (
        f"成長ドライバー候補として、{_clip_text(lead_text, max_chars=110)}を確認できます。"
        "売上・利益への効き方や継続性は、決算説明資料や中期経営計画で追加確認してください。"
    )
    return _investment_question_build_answer(
        category,
        answer,
        evidence_level=_investment_question_evidence_level_from_source_types(source_types),
        source_titles=[
            *_investment_question_titles_from_fact_items([*growth_items, *revenue_driver_items]),
            *_investment_question_titles_from_insight_points(growth_points),
        ],
    )


def _investment_question_risk(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
    insight: InvestmentInsight,
) -> InvestmentQuestionAnswer:
    caution_items = list(brief.fact_summary.caution_materials if brief.fact_summary else [])
    risk_points = list(insight.negative_points)
    if not caution_items and not risk_points:
        return _investment_question_missing_answer(
            category,
            "明確なリスク情報は取得できていません。ただし、公式資料の事業等のリスクを確認する必要があります。",
            "事業リスク、コスト増、為替、規制、訴訟などの情報が未取得です。",
        )

    source_types = [item.source_type for item in caution_items]
    source_types.extend(point.source_type for point in risk_points)
    lead_text = _investment_question_lead_text(
        fact_items=caution_items,
        insight_points=risk_points,
    )
    answer = (
        f"注意材料として、{_clip_text(lead_text, max_chars=112)}を確認できます。"
        "一時的なニュースか、業績に継続して効くリスクかを公式IRで裏取りしてください。"
    )
    return _investment_question_build_answer(
        category,
        answer,
        evidence_level=_investment_question_evidence_level_from_source_types(source_types),
        source_titles=[
            *_investment_question_titles_from_fact_items(caution_items),
            *_investment_question_titles_from_insight_points(risk_points),
        ],
    )


def _investment_question_shareholder_return(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
    insight: InvestmentInsight,
) -> InvestmentQuestionAnswer:
    metrics = _investment_question_metrics_by_key(brief)
    dividend_metric = metrics.get("dividend")
    return_items = list(brief.fact_summary.shareholder_return_policy if brief.fact_summary else [])
    return_points = _investment_question_insight_points_by_keywords(
        [*insight.positive_points, *insight.negative_points],
        ("配当", "増配", "減配", "自社株買い", "株主還元", "dividend", "buyback"),
    )
    if dividend_metric is None and not return_items and not return_points:
        return _investment_question_missing_answer(
            category,
            "配当方針・配当実績・自社株買い情報が未取得のため、株主還元は判断できません。",
            "配当方針、配当実績、自社株買い、配当性向が未取得です。",
        )

    source_types = [item.source_type for item in return_items]
    source_types.extend(point.source_type for point in return_points)
    if dividend_metric is not None:
        source_types.append(dividend_metric.source_type)
    sentences: list[str] = []
    if dividend_metric is not None:
        sentences.append(f"{dividend_metric.label} {dividend_metric.value}を確認できます。")
    if return_items or return_points:
        lead_text = _investment_question_lead_text(
            fact_items=return_items,
            insight_points=return_points,
        )
        sentences.append(
            f"株主還元に関する記述として、{_clip_text(lead_text, max_chars=100)}を確認できます。"
        )
    sentences.append("配当方針、配当性向、自社株買いの継続性は公式資料で追加確認してください。")
    return _investment_question_build_answer(
        category,
        " ".join(sentences),
        evidence_level=_investment_question_evidence_level_from_source_types(source_types),
        source_titles=[
            *_investment_question_titles_from_metrics(
                [dividend_metric] if dividend_metric is not None else []
            ),
            *_investment_question_titles_from_fact_items(return_items),
            *_investment_question_titles_from_insight_points(return_points),
        ],
    )


def _investment_question_valuation(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
) -> InvestmentQuestionAnswer:
    metrics = _investment_question_metrics_by_key(brief)
    valuation_keys: tuple[ResearchMetricKey, ...] = ("per", "pbr", "roe")
    valuation_metrics = {key: metrics[key] for key in valuation_keys if key in metrics}
    if not valuation_metrics:
        return _investment_question_missing_answer(
            category,
            "PER・PBR・ROE・配当利回りが未取得のため、割高・割安感は判断できません。",
            "PER、PBR、ROE、配当利回りが未取得です。",
        )

    metric_rows = _investment_question_metric_texts(metrics, ("per", "pbr", "roe", "dividend"))
    missing = [
        label
        for key, label in (("per", "PER"), ("pbr", "PBR"), ("roe", "ROE"))
        if key not in metrics
    ]
    missing_text = f"不足指標は{'、'.join(missing)}です。" if missing else ""
    answer = (
        f"{'、'.join(metric_rows)}を確認できます。{missing_text}"
        "同業比較、過去レンジ、配当利回りが未取得のため、割高・割安感は断定せず追加確認してください。"
    )
    return _investment_question_build_answer(
        category,
        answer,
        evidence_level=_investment_question_evidence_level_from_source_types(
            [metric.source_type for metric in valuation_metrics.values()]
        ),
        source_titles=_investment_question_titles_from_metrics(valuation_metrics.values()),
        missing_reason=_investment_question_missing_metrics_reason(
            brief,
            ("PER", "PBR", "ROE"),
        ),
    )


def _investment_question_recent_news_impact(
    category: InvestmentQuestionCategory,
    brief: ResearchBrief,
    *,
    news_report: StockNewsReport | None,
) -> InvestmentQuestionAnswer:
    if news_report is not None and news_report.news:
        lead = news_report.news[0]
        answer = (
            f"直近ニュースでは「{_clip_text(lead.title, max_chars=70)}」を確認できます。"
            f"{_investment_question_news_impact_phrase(lead)}"
            "業績への影響は、売上・利益への具体的な反映と公式IRでの確認が必要です。"
        )
        return _investment_question_build_answer(
            category,
            answer,
            evidence_level="low",
            source_titles=[lead.title],
        )

    recent_events = list(brief.fact_summary.recent_events if brief.fact_summary else [])
    if recent_events:
        answer = (
            f"直近イベントとして、{_clip_text(recent_events[0].value, max_chars=104)}"
            "業績への直接影響は、数値と公式IRで追加確認してください。"
        )
        return _investment_question_build_answer(
            category,
            answer,
            evidence_level=_investment_question_evidence_level_for_fact_items(recent_events),
            source_titles=_investment_question_titles_from_fact_items(recent_events),
        )
    return _investment_question_missing_answer(
        category,
        "業績に直接影響しそうなニュースは確認できていません。",
        "直近ニュースまたは業績影響を判断できる開示が未取得です。",
    )


def _investment_question_key_takeaway(
    category: InvestmentQuestionCategory,
    report: CompanyResearchReport,
    brief: ResearchBrief,
    insight: InvestmentInsight,
    *,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> InvestmentQuestionAnswer:
    source_types = [row.source_type for row in report.evidence]
    source_titles = [row.title for row in report.evidence[:3]]
    if news_report is not None:
        source_types.extend("news" for _ in news_report.news)
        source_titles.extend(row.title for row in news_report.news[:2])
    if external_research_result is not None:
        source_types.extend(entry.source_type for entry in external_research_result.entries)
        source_titles.extend(entry.title for entry in external_research_result.entries[:2])

    key_gap = _investment_question_key_gap(brief, insight)
    status = getattr(insight, "status_label", "判断材料不足")
    action = getattr(insight, "primary_action_label", "資料追加が必要")
    if source_types:
        answer = (
            f"現時点では、{key_gap}を優先して確認することが最重要です。"
            f"現在の状態は「{status}」で、次の確認アクションは「{action}」です。"
            "売買判断ではなく、確認材料として扱ってください。"
        )
    else:
        answer = (
            "現時点では、事業概要やニュースよりも、公式IR・決算資料・売上高・営業利益・EPS・"
            "PER/PBR/ROEなどの定量情報をそろえることが最重要です。"
        )
    return _investment_question_build_answer(
        category,
        answer,
        evidence_level=_investment_question_evidence_level_from_source_types(source_types),
        source_titles=source_titles,
        missing_reason=" / ".join(brief.confirmation_gaps[:2]),
    )


def _investment_question_missing_answer(
    category: InvestmentQuestionCategory,
    answer: str,
    missing_reason: str,
) -> InvestmentQuestionAnswer:
    return _investment_question_build_answer(
        category,
        answer,
        evidence_level="missing",
        source_titles=[],
        missing_reason=missing_reason,
    )


def _investment_question_build_answer(
    category: InvestmentQuestionCategory,
    answer: str,
    *,
    evidence_level: InvestmentQuestionEvidenceLevel,
    source_titles: Sequence[str],
    missing_reason: str = "",
) -> InvestmentQuestionAnswer:
    questions = dict(_INVESTMENT_QUESTION_SPECS)
    return InvestmentQuestionAnswer(
        category=category,
        question=questions[category],
        answer=_investment_question_clean_answer(answer),
        evidence_level=evidence_level,
        source_titles=_unique_text(list(source_titles))[:5],
        missing_reason=re.sub(r"\s+", " ", missing_reason).strip(),
    )


def _investment_question_clean_answer(text: str) -> str:
    cleaned = _research_user_facing_text(re.sub(r"\s+", " ", text).strip())
    for forbidden, replacement in _INVESTMENT_QUESTION_FORBIDDEN_REPLACEMENTS:
        cleaned = cleaned.replace(forbidden, replacement)
    return _clip_text(cleaned, max_chars=260)


def _investment_question_metrics_by_key(
    brief: ResearchBrief,
) -> dict[ResearchMetricKey, ResearchMetric]:
    return {metric.key: metric for metric in brief.metrics}


def _investment_question_metric_texts(
    metrics: Mapping[ResearchMetricKey, ResearchMetric],
    keys: Sequence[ResearchMetricKey],
) -> list[str]:
    return [f"{metrics[key].label} {metrics[key].value}" for key in keys if key in metrics]


def _investment_question_fact_items(brief: ResearchBrief) -> list[ResearchFactItem]:
    fact_summary = brief.fact_summary
    if fact_summary is None:
        return []
    return [
        *fact_summary.business_overview,
        *fact_summary.business_segments,
        *fact_summary.business_regions,
        *fact_summary.revenue_drivers,
        *fact_summary.financial_snapshot,
        *fact_summary.earnings_outlook,
        *fact_summary.shareholder_return_policy,
        *fact_summary.recent_events,
        *fact_summary.positive_materials,
        *fact_summary.caution_materials,
    ]


def _investment_question_fact_items_by_keywords(
    items: Sequence[ResearchFactItem],
    keywords: Sequence[str],
) -> list[ResearchFactItem]:
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    return [
        item
        for item in items
        if any(keyword in f"{item.label} {item.value}".lower() for keyword in lowered_keywords)
    ]


def _investment_question_insight_points_by_keywords(
    items: Sequence[InvestmentInsightItem],
    keywords: Sequence[str],
) -> list[InvestmentInsightItem]:
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    return [
        item
        for item in items
        if any(
            keyword in f"{item.label} {item.summary} {item.reason}".lower()
            for keyword in lowered_keywords
        )
    ]


def _investment_question_values(
    items: Sequence[ResearchFactItem],
    *,
    limit: int,
) -> list[str]:
    return [_clip_text(item.value, max_chars=38) for item in items[:limit] if item.value.strip()]


def _investment_question_titles_from_fact_items(
    items: Sequence[ResearchFactItem],
) -> list[str]:
    return [item.source_title for item in items if item.source_title.strip()]


def _investment_question_titles_from_metrics(
    metrics: Iterable[ResearchMetric],
) -> list[str]:
    return [metric.source_title for metric in metrics if metric.source_title.strip()]


def _investment_question_titles_from_insight_points(
    items: Sequence[InvestmentInsightItem],
) -> list[str]:
    return [item.source_title for item in items if item.source_title.strip()]


def _investment_question_lead_text(
    *,
    fact_items: Sequence[ResearchFactItem],
    insight_points: Sequence[InvestmentInsightItem],
) -> str:
    if fact_items:
        return fact_items[0].value
    if insight_points:
        return insight_points[0].summary
    return ""


def _investment_question_evidence_level_for_fact_items(
    items: Sequence[ResearchFactItem],
) -> InvestmentQuestionEvidenceLevel:
    return _investment_question_evidence_level_from_source_types(
        [item.source_type for item in items]
    )


def _investment_question_evidence_level_from_source_types(
    source_types: Sequence[ResearchSourceType | str],
) -> InvestmentQuestionEvidenceLevel:
    cleaned = [str(source_type) for source_type in source_types if str(source_type).strip()]
    if not cleaned:
        return "missing"
    if any(source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES for source_type in cleaned):
        return "high"
    if any(source_type == "provider_profile" for source_type in cleaned):
        return "medium"
    if any(source_type in {"news", "user_note"} for source_type in cleaned):
        return "low"
    return "low"


def _investment_question_missing_metrics_reason(
    brief: ResearchBrief,
    labels: Sequence[str],
) -> str:
    missing = [label for label in labels if label in set(brief.missing_metrics)]
    if not missing:
        return ""
    return f"未取得: {'、'.join(missing)}"


def _investment_question_news_impact_phrase(row: StockNewsEvidence) -> str:
    labels: dict[StockNewsInvestmentViewpoint, str] = {
        "earnings": "業績に関係するニュースです。",
        "growth": "売上や成長テーマに関係する可能性があるニュースです。",
        "shareholder_return": "株主還元に関係するニュースです。",
        "risk": "注意材料として確認するニュースです。",
        "macro": "外部環境に関係するニュースです。",
        "other": "業績への直接影響はまだ読み取りにくいニュースです。",
    }
    return labels.get(row.investment_viewpoint, labels["other"])


def _investment_question_key_gap(
    brief: ResearchBrief,
    insight: InvestmentInsight,
) -> str:
    missing_metrics = [
        metric
        for metric in ("売上高", "営業利益", "EPS", "PER", "PBR", "ROE")
        if metric in brief.missing_metrics
    ]
    if missing_metrics:
        return f"{'・'.join(missing_metrics[:4])}などの定量情報"
    if insight.confirmation_gaps:
        return _clip_text(insight.confirmation_gaps[0], max_chars=80)
    if insight.positive_points and insight.negative_points:
        return "良い材料と注意材料の前提を同じ資料で比較すること"
    if insight.positive_points:
        return "確認できた良い材料が業績数値にどう反映されるか"
    if insight.negative_points:
        return "注意材料が一時的か継続的か"
    return "公式IR・決算資料・主要財務指標"


def _investment_question_missing_critical_items(
    brief: ResearchBrief,
    answers: Sequence[InvestmentQuestionAnswer],
) -> list[str]:
    items: list[str] = []
    items.extend(brief.missing_metrics)
    items.extend(
        _INVESTMENT_QUESTION_MISSING_ITEM_LABELS[answer.category]
        for answer in answers
        if answer.evidence_level == "missing"
    )
    return _unique_text(items)[:10]


def _investment_insight_confidence_phrase(confidence: ResearchSourceConfidence) -> str:
    labels: dict[ResearchSourceConfidence, str] = {
        "high": "公式資料を含む高め",
        "medium": "外部データ・ニュースを含む中程度",
        "low": "メモ・低信頼資料中心",
        "unknown": "未確認",
    }
    return labels[confidence]


def _investment_insight_has_official_source(
    report: CompanyResearchReport,
    brief: ResearchBrief,
) -> bool:
    return any(
        row.source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES for row in report.evidence
    ) or any(card.source_confidence == "high" for card in brief.source_cards)


def _unique_investment_insight_items(
    items: Sequence[InvestmentInsightItem],
) -> list[InvestmentInsightItem]:
    unique: list[InvestmentInsightItem] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in items:
        summary = re.sub(r"\s+", " ", item.summary).strip()
        if not summary:
            continue
        key = (item.label, summary, item.source_title, item.source_type)
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            item.model_copy(
                update={
                    "summary": summary,
                    "reason": re.sub(r"\s+", " ", item.reason).strip(),
                }
            )
        )
    return unique


def _research_brief_evidence_text(row: ResearchEvidence) -> str:
    return " ".join(
        part for part in (row.title, row.section_title or "", row.excerpt) if part.strip()
    )


def _research_brief_source_confidence(
    source_type: ResearchSourceType,
) -> ResearchSourceConfidence:
    if source_type in _RESEARCH_BRIEF_HIGH_CONFIDENCE_SOURCES:
        return "high"
    if source_type in _RESEARCH_BRIEF_MEDIUM_CONFIDENCE_SOURCES:
        return "medium"
    if source_type == "user_note":
        return "low"
    return "unknown"


def _unique_text(values: Sequence[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique


def _clip_text(text: str, *, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[: max_chars - 1].rstrip()}…"


def _data_quality_status_factor(status: DataQuality) -> Decimal:
    factors: dict[DataQuality, Decimal] = {
        "OK": Decimal("1"),
        "WARN": Decimal("0.75"),
        "BLOCK": Decimal("0.40"),
    }
    return factors[status]


def _score_100(value: Decimal) -> Decimal:
    return min(Decimal("100"), max(Decimal("0"), value)).quantize(Decimal("0.01"))


def _topic_summary(label: str, evidence: list[ResearchEvidence]) -> str:
    if not evidence:
        return f"{label}について、登録資料から十分な根拠を検索できませんでした。"
    lead = evidence[0]
    return f"{label}は「{lead.excerpt}」を主な確認材料として見ます。"


def _research_data_quality(
    documents: list[ResearchDocument],
    evidence: list[ResearchEvidence],
    *,
    as_of: date,
) -> ResearchDataQuality:
    warnings: list[str] = []
    latest_date = max(
        (document.published_at for document in documents if document.published_at is not None),
        default=None,
    )
    if not documents:
        warnings.append("登録済みResearch資料がありません。")
    if not evidence:
        warnings.append("検索できたResearch根拠がありません。")
    if evidence and max(row.reliability for row in evidence) < Decimal("0.50"):
        warnings.append("検索できたResearch根拠の信頼度が低いため、出所を確認してください。")
    if latest_date and (as_of - latest_date).days > 730:
        warnings.append("最新資料が2年以上前のため、鮮度に注意してください。")

    if not documents or not evidence:
        status: DataQuality = "WARN"
    elif warnings:
        status = "WARN"
    else:
        status = "OK"
    return ResearchDataQuality(
        status=status,
        latest_document_date=latest_date,
        document_count=len(documents),
        evidence_count=len(evidence),
        warnings=warnings,
    )


def _company_summary(evidence: list[ResearchEvidence], data_quality: ResearchDataQuality) -> str:
    if data_quality.status != "OK":
        return "登録資料が限られるため、Research Summary は確認材料として控えめに扱います。"
    return f"{len(evidence)}件の根拠から、長期企業分析の確認材料を整理しました。"


def _stock_news_keywords(request: StockNewsRequest) -> list[str]:
    terms = [request.symbol]
    if request.company_name:
        terms.append(request.company_name)
    terms.extend(request.related_keywords)
    return [term.strip().lower() for term in terms if term.strip()]


def _normalize_external_stock_news(
    rows: Sequence[StockNewsEvidence],
    *,
    request: StockNewsRequest,
    as_of: date,
) -> tuple[list[StockNewsEvidence], list[str]]:
    normalized_symbol = _normalize_symbol(request.symbol)
    keywords = _stock_news_keywords(request)
    deduped: dict[str, StockNewsEvidence] = {}
    warnings: list[str] = []
    for row in rows:
        if not _stock_news_evidence_matches_request(row, normalized_symbol, keywords):
            continue
        url = row.url.strip()
        if not url:
            warnings.append(f"{row.title}: URL がないため外部ニュース根拠から除外しました。")
            continue
        freshness_status = _stock_news_freshness(row.published_at, as_of=as_of)
        normalized = row.model_copy(
            update={
                "symbol": normalized_symbol,
                "company_name": row.company_name or request.company_name,
                "url": url,
                "freshness_status": freshness_status,
            }
        )
        key = url.casefold()
        if key not in deduped:
            deduped[key] = normalized
        if freshness_status == "stale":
            warnings.append(
                f"{row.title}: 公開日が古いため、最新ニュースや公式発表と合わせて確認してください。"
            )
    news = sorted(
        deduped.values(),
        key=lambda row: (
            _stock_news_freshness_rank(row.freshness_status),
            -(row.published_at or date.min).toordinal(),
            row.title,
        ),
    )
    return news, warnings


def _stock_news_evidence_matches_request(
    row: StockNewsEvidence,
    symbol: str,
    keywords: Sequence[str],
) -> bool:
    if _normalize_symbol(row.symbol) == symbol:
        return True
    haystack = f"{row.symbol} {row.company_name or ''} {row.title} {row.summary}".lower()
    return any(keyword and keyword in haystack for keyword in keywords)


def _stock_news_evidence_from_external_payloads(
    payloads: Sequence[ExternalResearchSourcePayload],
    *,
    request: StockNewsRequest,
    as_of: date,
) -> list[StockNewsEvidence]:
    return [
        news
        for payload in payloads
        if payload.source_type == "news"
        for news in [
            _stock_news_evidence_from_external_payload(
                payload,
                request=request,
                as_of=as_of,
            )
        ]
        if news is not None
    ]


def _stock_news_evidence_from_external_payload(
    payload: ExternalResearchSourcePayload,
    *,
    request: StockNewsRequest,
    as_of: date,
) -> StockNewsEvidence | None:
    url = payload.source_url.strip() or _stock_news_url(payload.content)
    if not url:
        return None
    text = f"{payload.title}\n{payload.content}"
    return StockNewsEvidence(
        symbol=_normalize_symbol(request.symbol),
        company_name=payload.company_name or request.company_name,
        title=payload.title,
        url=url,
        source=_stock_news_source(payload.content) or payload.provider,
        published_at=payload.published_at,
        summary=_stock_news_summary(payload.content),
        investment_viewpoint=_stock_news_viewpoint(text),
        sentiment_for_investment=_stock_news_sentiment(text),
        freshness_status=_stock_news_freshness(payload.published_at, as_of=as_of),
    )


def _stock_news_matches(
    document: ResearchDocument,
    text: str,
    symbol: str,
    keywords: Sequence[str],
) -> bool:
    if _normalize_symbol(document.symbol) == symbol:
        return True
    haystack = f"{document.symbol} {document.company_name or ''} {document.title} {text}".lower()
    return any(keyword and keyword in haystack for keyword in keywords)


def _stock_news_url(text: str) -> str:
    labeled = re.search(r"(?im)^\s*(?:source_)?url\s*[:：]\s*(https?://\S+)\s*$", text)
    if labeled:
        return labeled.group(1).strip().rstrip(".,)")
    match = re.search(r"https?://\S+", text)
    if match:
        return match.group(0).strip().rstrip(".,)")
    return ""


def _stock_news_source(text: str) -> str | None:
    match = re.search(r"(?im)^\s*source\s*[:：]\s*(.+?)\s*$", text)
    if not match:
        return None
    source = match.group(1).strip()
    return source or None


def _stock_news_summary(text: str) -> str:
    match = re.search(r"(?im)^\s*(?:short_)?summary\s*[:：]\s*(.+?)\s*$", text)
    if match:
        return _excerpt(match.group(1), max_chars=180)
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
        and not re.match(r"(?i)^\s*(?:source_)?url\s*[:：]", line)
        and not re.match(r"(?i)^\s*source\s*[:：]", line)
    ]
    return _excerpt(" ".join(lines), max_chars=180) or "ニュース本文の要約対象が不足しています。"


def _stock_news_evidence(
    document: ResearchDocument,
    text: str,
    *,
    url: str,
    as_of: date,
) -> StockNewsEvidence:
    return StockNewsEvidence(
        symbol=document.symbol,
        company_name=document.company_name,
        title=document.title,
        url=url,
        source=_stock_news_source(text),
        published_at=document.published_at,
        summary=_stock_news_summary(text),
        investment_viewpoint=_stock_news_viewpoint(text),
        sentiment_for_investment=_stock_news_sentiment(text),
        freshness_status=_stock_news_freshness(document.published_at, as_of=as_of),
    )


def _stock_news_viewpoint(text: str) -> StockNewsInvestmentViewpoint:
    normalized = text.lower()
    terms_by_viewpoint: dict[StockNewsInvestmentViewpoint, tuple[str, ...]] = {
        "earnings": (
            "earnings",
            "profit",
            "revenue",
            "sales",
            "guidance",
            "決算",
            "業績",
        ),
        "growth": ("growth", "expansion", "investment", "new business", "成長", "投資"),
        "shareholder_return": (
            "dividend",
            "buyback",
            "shareholder return",
            "配当",
            "自社株",
        ),
        "risk": ("risk", "lawsuit", "recall", "regulation", "fraud", "リスク", "訴訟"),
        "macro": (
            "rate",
            "inflation",
            "fx",
            "yen",
            "macro",
            "金利",
            "為替",
            "インフレ",
        ),
        "other": (),
    }
    scored = [
        (sum(1 for term in terms if term in normalized), viewpoint)
        for viewpoint, terms in terms_by_viewpoint.items()
        if viewpoint != "other"
    ]
    score, viewpoint = max(scored, key=lambda row: (row[0], row[1]))
    return viewpoint if score > 0 else "other"


def _stock_news_sentiment(text: str) -> StockNewsSentiment:
    normalized = text.lower()
    positive_terms = (
        "positive",
        "beat",
        "raise",
        "growth",
        "increase",
        "record",
        "増益",
        "上方修正",
        "増配",
    )
    negative_terms = (
        "negative",
        "miss",
        "cut",
        "decline",
        "risk",
        "loss",
        "lawsuit",
        "減益",
        "下方修正",
        "減配",
    )
    positive = sum(1 for term in positive_terms if term in normalized)
    negative = sum(1 for term in negative_terms if term in normalized)
    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    return "neutral" if normalized.strip() else "unknown"


def _stock_news_freshness(
    published_at: date | None,
    *,
    as_of: date,
) -> StockNewsFreshnessStatus:
    if published_at is None:
        return "unknown"
    age_days = (as_of - published_at).days
    if age_days < 0:
        return "latest"
    if age_days <= 7:
        return "latest"
    if age_days <= 45:
        return "recent"
    return "stale"


def _stock_news_freshness_rank(status: StockNewsFreshnessStatus) -> int:
    return {
        "latest": 0,
        "recent": 1,
        "unknown": 2,
        "stale": 3,
    }[status]
