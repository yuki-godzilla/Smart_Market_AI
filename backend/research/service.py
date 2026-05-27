from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Literal, Protocol, Sequence, cast

import yaml  # type: ignore[import-untyped]
from pydantic import Field, ValidationError

from backend.core.data_contracts import DataQuality, StrictBaseModel
from backend.core.errors import AppError, ValidationAppError

ResearchSourceType = Literal[
    "annual_report",
    "earnings_report",
    "earnings_presentation",
    "medium_term_plan",
    "integrated_report",
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
    ("trailingPE", "Trailing PE"),
    ("priceToBook", "Price To Book"),
    ("returnOnEquity", "Return On Equity"),
    ("dividendYield", "Dividend Yield"),
    ("payoutRatio", "Payout Ratio"),
    ("beta", "Beta"),
)
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
    """Manifest row for a cached external source."""

    title: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    source_type: ResearchSourceType
    source_url: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    published_at: date | None = None
    fetched_at: datetime
    local_path: str = Field(min_length=1)
    document_hash: str = Field(min_length=1)
    document_id: str = Field(min_length=1)


class ExternalResearchFetchResult(StrictBaseModel):
    """Result of opt-in external fetch persisted to local cache."""

    symbol: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    fetched_at: datetime
    entries: list[ExternalResearchFetchManifestEntry] = Field(default_factory=list)
    manifest_path: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ExternalResearchSourceAdapter(Protocol):
    """Adapter protocol for opt-in external research/news fetches."""

    provider: str
    requires_network: bool

    def fetch_sources(
        self, request: ExternalResearchFetchRequest
    ) -> list[ExternalResearchSourcePayload]: ...


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
            documents, key=lambda doc: (doc.symbol, doc.published_at or date.min, doc.title)
        )

    def replace_chunks(self, document_id: str, chunks: list[ResearchChunk]) -> None:
        self.chunks_by_document_id[document_id] = chunks

    def all_chunks(self, symbol: str | None = None) -> list[ResearchChunk]:
        chunks = [chunk for group in self.chunks_by_document_id.values() for chunk in group]
        if symbol:
            normalized = _normalize_symbol(symbol)
            chunks = [chunk for chunk in chunks if _normalize_symbol(chunk.symbol) == normalized]
        return sorted(
            chunks, key=lambda chunk: (chunk.symbol, chunk.document_id, chunk.chunk_index)
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
            ("growth", "成長材料", "growth strategy revenue sales market expansion new business"),
            ("shareholder_return", "株主還元", "dividend payout buyback shareholder return"),
            ("financial_safety", "財務安全性", "cash debt equity capital liquidity balance sheet"),
            ("business_risk", "事業リスク", "risk competition regulation lawsuit supply demand"),
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


class ExternalResearchFetchService:
    """Persist explicitly fetched external sources into local Research RAG cache."""

    def __init__(
        self,
        adapter: ExternalResearchSourceAdapter,
        ingestion: ResearchIngestionService,
        index: ResearchIndexService,
        *,
        cache_dir: Path,
    ) -> None:
        self.adapter = adapter
        self.ingestion = ingestion
        self.index = index
        self.cache_dir = cache_dir

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
        payloads = self.adapter.fetch_sources(request)
        entries: list[ExternalResearchFetchManifestEntry] = []
        warnings: list[str] = []
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        for payload in payloads:
            if not payload.source_url.strip():
                warnings.append(f"{payload.title}: source URL is missing; skipped.")
                continue
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
            self.index.build_chunks(document.document_id)
            entries.append(
                ExternalResearchFetchManifestEntry(
                    title=document.title,
                    symbol=document.symbol,
                    source_type=document.source_type,
                    source_url=payload.source_url,
                    provider=payload.provider,
                    published_at=document.published_at,
                    fetched_at=payload.fetched_at,
                    local_path=str(path),
                    document_hash=document.document_hash,
                    document_id=document.document_id,
                )
            )

        if not entries:
            warnings.append("External fetch returned no registerable URL-backed sources.")
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
            manifest_path=str(manifest_path),
            warnings=warnings,
        )

    def _write_payload(self, payload: ExternalResearchSourcePayload) -> Path:
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


class YahooFinanceResearchAdapter:
    """Opt-in Yahoo Finance adapter for provider profile and recent news payloads."""

    provider = "yahoo_finance"
    requires_network = True

    def __init__(self, ticker_factory: Callable[[str], Any] | None = None) -> None:
        self._ticker_factory = ticker_factory

    def fetch_sources(
        self,
        request: ExternalResearchFetchRequest,
    ) -> list[ExternalResearchSourcePayload]:
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
        try:
            import yfinance as yf  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ResearchDocumentError(
                "yfinance is required for the Yahoo Finance research adapter.",
                details={"provider": self.provider},
            ) from exc
        return yf.Ticker(symbol)


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
    lines = [
        f"{label}: {_external_text_value(info.get(key))}"
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


def _external_text_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value).strip()


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
        "earnings": ("earnings", "profit", "revenue", "sales", "guidance", "決算", "業績"),
        "growth": ("growth", "expansion", "investment", "new business", "成長", "投資"),
        "shareholder_return": ("dividend", "buyback", "shareholder return", "配当", "自社株"),
        "risk": ("risk", "lawsuit", "recall", "regulation", "fraud", "リスク", "訴訟"),
        "macro": ("rate", "inflation", "fx", "yen", "macro", "金利", "為替", "インフレ"),
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
