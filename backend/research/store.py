"""Local deterministic document storage used by Research ingestion and retrieval."""

from __future__ import annotations

from datetime import date

from backend.research.contracts import ResearchChunk, ResearchDocument
from backend.research.normalization import normalize_symbol


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
            normalized = normalize_symbol(symbol)
            documents = [doc for doc in documents if normalize_symbol(doc.symbol) == normalized]
        return sorted(
            documents,
            key=lambda doc: (doc.symbol, doc.published_at or date.min, doc.title),
        )

    def replace_chunks(self, document_id: str, chunks: list[ResearchChunk]) -> None:
        self.chunks_by_document_id[document_id] = chunks

    def all_chunks(self, symbol: str | None = None) -> list[ResearchChunk]:
        chunks = [chunk for group in self.chunks_by_document_id.values() for chunk in group]
        if symbol:
            normalized = normalize_symbol(symbol)
            chunks = [chunk for chunk in chunks if normalize_symbol(chunk.symbol) == normalized]
        return sorted(
            chunks,
            key=lambda chunk: (chunk.symbol, chunk.document_id, chunk.chunk_index),
        )
