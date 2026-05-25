from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Sequence, cast

import yaml  # type: ignore[import-untyped]
from pydantic import Field

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

RESEARCH_SCHEMA_VERSION = "research-evidence-v1"
DEFAULT_MAX_CHARS = 1200
DEFAULT_OVERLAP_CHARS = 180
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


class ResearchSearchRequest(StrictBaseModel):
    """Keyword research search request."""

    symbol: str = Field(min_length=1)
    query: str = ""
    top_k: int = Field(default=8, ge=1, le=50)
    source_types: list[ResearchSourceType] = Field(default_factory=list)
    as_of: date | None = None
    query_category: ResearchTopicCategory | None = None
    expanded_terms: list[str] = Field(default_factory=list)


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
    decision_support_note: str = "Research evidence is decision support only; not advice."


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


class ResearchRetrievalService:
    """Retrieve local research evidence with deterministic keyword scoring."""

    def __init__(self, store: ResearchInMemoryStore) -> None:
        self.store = store

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
        scored.sort(
            key=lambda row: (
                -row[0],
                -(row[1].published_at or date.min).toordinal(),
                row[1].document_id,
                row[1].chunk_index,
            )
        )
        return [
            _evidence_from_chunk(chunk, relevance_score=score)
            for score, chunk in scored[: request.top_k]
        ]


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
    ) -> None:
        self.ingestion = ingestion
        self.retrieval = retrieval
        self.query_expansion = query_expansion or ResearchQueryExpansionService()
        self.grounded_answer = grounded_answer or ResearchGroundedAnswerService()

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
        for category, label, query in topics:
            topic_category = cast(ResearchTopicCategory, category)
            expanded = self.query_expansion.expand_query(query, category=topic_category)
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

        unique_evidence = _dedupe_evidence(all_evidence)
        documents = self.ingestion.list_documents(request.symbol)
        data_quality = _research_data_quality(documents, unique_evidence, as_of=as_of)
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
        )


def _is_allowed_path(path: Path, allowed_dirs: Sequence[Path]) -> bool:
    return any(path == directory or directory in path.parents for directory in allowed_dirs)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _stable_id(prefix: str, *parts: str) -> str:
    normalized = "|".join(part.strip().lower() for part in parts)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


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
        reliability=(
            Decimal(chunk.metadata.get("reliability", "0.70"))
            if "reliability" in chunk.metadata
            else Decimal("0.70")
        ),
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
