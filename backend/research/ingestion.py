"""Local Research document ingestion and deterministic text indexing."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from backend.core.errors import AppError, ValidationAppError
from backend.research.contracts import (
    DEFAULT_MAX_CHARS,
    DEFAULT_OVERLAP_CHARS,
    ResearchChunk,
    ResearchDocument,
    ResearchDocumentRegisterRequest,
    ResearchIndexSummary,
    ResearchLanguage,
    ResearchParseError,
)
from backend.research.errors import ResearchDocumentError
from backend.research.external_contracts import ResearchSourceType
from backend.research.external_registration import safe_cache_fragment
from backend.research.normalization import normalize_symbol
from backend.research.store import ResearchInMemoryStore


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
                    "document_dirs": [str(directory) for directory in self.document_dirs],
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
            symbol=normalize_symbol(request.symbol),
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
            symbol=normalize_symbol(symbol),
            title=title.strip(),
            source_type=source_type,
            company_name=company_name.strip() if company_name else None,
            published_at=published_at,
            collected_at=datetime.now(UTC),
            local_path=(
                f"external://{safe_cache_fragment(provider)}/"
                f"{safe_cache_fragment(normalize_symbol(symbol))}/"
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
            symbols=sorted({normalize_symbol(document.symbol) for document in documents}),
            warnings=warnings,
        )


def _is_allowed_path(path: Path, allowed_dirs: Sequence[Path]) -> bool:
    return any(path == directory or directory in path.parents for directory in allowed_dirs)


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
                "research-chunk",
                document.document_id,
                str(chunk_index),
                piece[:80],
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
            current = paragraph
        else:
            pieces.append(current.strip())
            current = paragraph
    if current:
        pieces.append(current.strip())
    return pieces


def _split_long_text(text: str, *, max_chars: int) -> list[str]:
    return [text[index : index + max_chars].strip() for index in range(0, len(text), max_chars)]
