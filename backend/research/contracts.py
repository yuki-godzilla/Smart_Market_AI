from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import Field

from backend.core.data_contracts import DataQuality, StrictBaseModel
from backend.core.errors import AppError
from backend.research.external_contracts import ResearchSourceType, StockNewsFreshnessStatus

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
    classification_reason: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    classification_confidence: float | None = Field(default=None, ge=0, le=1)
    source_category: str | None = None

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


class ExternalStockNewsAdapter(Protocol):
    """Adapter protocol for selected-symbol external news fetches."""

    provider: str
    requires_network: bool

    def fetch_news(self, request: StockNewsRequest) -> list[StockNewsEvidence]: ...
