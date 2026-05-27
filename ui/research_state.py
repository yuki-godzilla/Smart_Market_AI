from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import streamlit as st

from backend.research import (
    CompanyResearchReport,
    CompanyResearchRequest,
    ExternalResearchFetchRequest,
    ExternalResearchFetchResult,
    ExternalResearchFetchService,
    ExternalResearchSourceAdapter,
    ResearchAnalysisService,
    ResearchDocumentRegisterRequest,
    ResearchIndexService,
    ResearchIngestionService,
    ResearchInMemoryStore,
    ResearchRetrievalService,
    ResearchSourceType,
    StockNewsAnalysisService,
    StockNewsReport,
    StockNewsRequest,
    YahooFinanceResearchAdapter,
)

RESEARCH_STORE_STATE_KEY = "research_local_store"
RESEARCH_AUTOLOAD_STATE_KEY = "research_local_autoloaded_files"
RESEARCH_DOC_DIR = Path("data/research_docs")
RESEARCH_UPLOAD_DIR = RESEARCH_DOC_DIR / "uploads"


def research_store() -> ResearchInMemoryStore:
    store = st.session_state.get(RESEARCH_STORE_STATE_KEY)
    if isinstance(store, ResearchInMemoryStore):
        return store
    store = ResearchInMemoryStore()
    st.session_state[RESEARCH_STORE_STATE_KEY] = store
    return store


def research_document_dirs() -> list[Path]:
    RESEARCH_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return [RESEARCH_DOC_DIR]


def autoload_local_research_documents() -> int:
    """Register local research docs from data/research_docs for the current Streamlit session."""

    RESEARCH_DOC_DIR.mkdir(parents=True, exist_ok=True)
    loaded_files = st.session_state.get(RESEARCH_AUTOLOAD_STATE_KEY)
    if not isinstance(loaded_files, set):
        loaded_files = set()
        st.session_state[RESEARCH_AUTOLOAD_STATE_KEY] = loaded_files

    store = research_store()
    ingestion = ResearchIngestionService(store, document_dirs=research_document_dirs())
    index = ResearchIndexService(store)
    loaded_count = 0
    for path in sorted(RESEARCH_DOC_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".md", ".txt", ".csv"}:
            continue
        resolved = str(path.resolve())
        if resolved in loaded_files:
            continue
        symbol = _symbol_from_research_filename(path)
        if not symbol:
            continue
        document = ingestion.register_document(
            ResearchDocumentRegisterRequest(
                symbol=symbol,
                title=_title_from_research_filename(path),
                local_path=str(path),
                source_type=_source_type_from_research_filename(path),
                published_at=_date_from_research_filename(path),
            )
        )
        index.build_chunks(document.document_id)
        loaded_files.add(resolved)
        loaded_count += 1
    return loaded_count


def register_uploaded_research_document(
    *,
    symbol: str,
    title: str,
    content: bytes,
    file_name: str,
    source_type: str,
    published_at: date | None,
) -> tuple[str, int]:
    upload_path = _uploaded_document_path(symbol=symbol, title=title, file_name=file_name)
    upload_path.write_bytes(content)
    store = research_store()
    ingestion = ResearchIngestionService(store, document_dirs=research_document_dirs())
    document = ingestion.register_document(
        ResearchDocumentRegisterRequest(
            symbol=symbol,
            title=title,
            local_path=str(upload_path),
            source_type=source_type,  # type: ignore[arg-type]
            published_at=published_at,
        )
    )
    chunks = ResearchIndexService(store).build_chunks(document.document_id)
    return document.document_id, len(chunks)


def analyze_research_for_symbol(symbol: str, *, as_of: date | None = None) -> CompanyResearchReport:
    autoload_local_research_documents()
    store = research_store()
    return ResearchAnalysisService(
        ResearchIngestionService(store, document_dirs=research_document_dirs()),
        ResearchRetrievalService(store),
    ).analyze_company(CompanyResearchRequest(symbol=symbol, as_of=as_of))


def fetch_external_research_for_symbol(
    symbol: str,
    *,
    company_name: str | None = None,
    related_keywords: list[str] | None = None,
    as_of: date | None = None,
    allow_network: bool,
    adapter: ExternalResearchSourceAdapter | None = None,
) -> ExternalResearchFetchResult:
    """Fetch opt-in external sources and register them in the session-local RAG store."""

    autoload_local_research_documents()
    store = research_store()
    ingestion = ResearchIngestionService(store, document_dirs=research_document_dirs())
    index = ResearchIndexService(store)
    source_adapter = adapter or YahooFinanceResearchAdapter()
    result = ExternalResearchFetchService(
        source_adapter,
        ingestion,
        index,
    ).fetch_register_sources(
        ExternalResearchFetchRequest(
            symbol=symbol,
            company_name=company_name,
            related_keywords=related_keywords or [],
            provider=source_adapter.provider,
            as_of=as_of,
            allow_network=allow_network,
        )
    )
    return result


def analyze_stock_news_for_symbol(
    symbol: str,
    *,
    company_name: str | None = None,
    related_keywords: list[str] | None = None,
    as_of: date | None = None,
) -> StockNewsReport:
    autoload_local_research_documents()
    store = research_store()
    return StockNewsAnalysisService(
        ResearchIngestionService(store, document_dirs=research_document_dirs())
    ).analyze_symbol_news(
        StockNewsRequest(
            symbol=symbol,
            company_name=company_name,
            related_keywords=related_keywords or [],
            as_of=as_of,
        )
    )


def research_document_summary_rows() -> list[dict[str, str]]:
    autoload_local_research_documents()
    rows = []
    for document in research_store().list_documents():
        rows.append(
            {
                "symbol": document.symbol,
                "title": document.title,
                "source_type": document.source_type,
                "published_at": document.published_at.isoformat() if document.published_at else "",
                "chunks": str(
                    len(research_store().chunks_by_document_id.get(document.document_id, []))
                ),
                "document_id": document.document_id,
            }
        )
    return rows


def _uploaded_document_path(*, symbol: str, title: str, file_name: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    safe_symbol = _safe_filename(symbol.upper())
    safe_title = _safe_filename(title)[:48]
    suffix = Path(file_name).suffix.lower() or ".txt"
    return RESEARCH_UPLOAD_DIR / f"{safe_symbol}_{timestamp}_{safe_title}{suffix}"


def _safe_filename(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return normalized.strip("._") or "research_doc"


def _symbol_from_research_filename(path: Path) -> str:
    stem = path.stem.upper()
    jp_match = re.match(r"^(\d{4})(?:[._]T)(?:_|$)", stem)
    if jp_match:
        return f"{jp_match.group(1)}.T"
    us_match = re.match(r"^([A-Z]{1,6})(?:_|$)", stem)
    if us_match:
        return us_match.group(1)
    return ""


def _title_from_research_filename(path: Path) -> str:
    return path.stem.replace("_", " ").strip() or path.name


def _source_type_from_research_filename(path: Path) -> ResearchSourceType:
    stem = path.stem.lower()
    for source_type in (
        "annual_report",
        "earnings_report",
        "earnings_presentation",
        "medium_term_plan",
        "integrated_report",
        "provider_profile",
        "tdnet",
        "news",
    ):
        if source_type in stem:
            return cast(ResearchSourceType, source_type)
    return "user_note"


def _date_from_research_filename(path: Path) -> date | None:
    match = re.search(r"(20\d{6})", path.stem)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None
