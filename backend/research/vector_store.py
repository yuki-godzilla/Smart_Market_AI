"""Optional local vector retrieval stores and deterministic vector primitives."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from backend.research.contracts import (
    ResearchEmbedding,
    ResearchRetrievalCandidate,
    ResearchRetrievalQuality,
    ResearchSearchError,
    ResearchSearchRequest,
)
from backend.research.normalization import normalize_symbol


def query_terms(query: str) -> list[str]:
    normalized = query.lower()
    terms = re.findall(r"[a-z0-9_]+|[一-龥ぁ-んァ-ンー]{2,}", normalized)
    return sorted(set(terms))


def normalize_query_terms(terms: Sequence[str]) -> list[str]:
    normalized: set[str] = set()
    for term in terms:
        normalized.update(query_terms(term))
    return sorted(normalized)


def local_embedding_vector(text: str, *, dimensions: int) -> list[float]:
    terms = query_terms(text)
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


def cosine_similarity(query_vector: Sequence[float], candidate_vector: Sequence[float]) -> Decimal:
    if not query_vector or not candidate_vector or len(query_vector) != len(candidate_vector):
        return Decimal("0")
    query_norm = math.sqrt(sum(value * value for value in query_vector))
    candidate_norm = math.sqrt(sum(value * value for value in candidate_vector))
    if query_norm == 0 or candidate_norm == 0:
        return Decimal("0")
    dot = sum(left * right for left, right in zip(query_vector, candidate_vector, strict=True))
    score = max(0.0, min(1.0, dot / (query_norm * candidate_norm)))
    return Decimal(str(score)).quantize(Decimal("0.0001"))


def validate_vector_entry(
    candidate: ResearchRetrievalCandidate,
    embedding: ResearchEmbedding,
    *,
    cache_path: Path | None = None,
) -> None:
    if candidate.chunk_id == embedding.chunk_id:
        return
    details: dict[str, object] = {
        "candidate_chunk_id": candidate.chunk_id,
        "embedding_chunk_id": embedding.chunk_id,
    }
    if cache_path is not None:
        details["cache_path"] = str(cache_path)
    raise ResearchSearchError(
        message="Research vector candidate and embedding chunk_id do not match.",
        details=details,
    )


def search_vector_entries(
    entries: Mapping[str, tuple[ResearchRetrievalCandidate, ResearchEmbedding]],
    request: ResearchSearchRequest,
) -> list[ResearchRetrievalCandidate]:
    if not request.query_vector:
        return []
    source_types = set(request.source_types)
    scored: list[ResearchRetrievalCandidate] = []
    for candidate, embedding in entries.values():
        if candidate.symbol != normalize_symbol(request.symbol):
            continue
        if source_types and candidate.source_type not in source_types:
            continue
        vector_score = cosine_similarity(request.query_vector, embedding.vector)
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


def build_vector_retrieval_quality(
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
        expanded_terms=normalize_query_terms(expanded_terms or request.expanded_terms),
        candidate_count=candidate_count,
        evidence_count=candidate_count,
        warnings=warnings,
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
            expanded_terms=normalize_query_terms(expanded_terms or request.expanded_terms),
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
        validate_vector_entry(candidate, embedding)
        self._entries[candidate.chunk_id] = (candidate, embedding)

    def upsert_many(
        self,
        entries: Sequence[tuple[ResearchRetrievalCandidate, ResearchEmbedding]],
        *,
        replace_symbol: str | None = None,
        replace_all: bool = False,
    ) -> None:
        for candidate, embedding in entries:
            validate_vector_entry(candidate, embedding)
        if replace_all:
            self._entries = {}
        elif replace_symbol is not None:
            normalized_symbol = normalize_symbol(replace_symbol)
            self._entries = {
                chunk_id: value
                for chunk_id, value in self._entries.items()
                if value[0].symbol != normalized_symbol
            }
        self._entries.update(
            {candidate.chunk_id: (candidate, embedding) for candidate, embedding in entries}
        )

    def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]:
        return search_vector_entries(self._entries, request)

    def retrieval_quality(
        self,
        request: ResearchSearchRequest,
        *,
        expanded_terms: Sequence[str] | None = None,
    ) -> ResearchRetrievalQuality:
        candidates = self.search(request)
        return build_vector_retrieval_quality(
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
        validate_vector_entry(candidate, embedding, cache_path=self.cache_path)
        self._entries[candidate.chunk_id] = (candidate, embedding)
        self._write_entries()

    def upsert_many(
        self,
        entries: Sequence[tuple[ResearchRetrievalCandidate, ResearchEmbedding]],
        *,
        replace_symbol: str | None = None,
        replace_all: bool = False,
    ) -> None:
        for candidate, embedding in entries:
            validate_vector_entry(candidate, embedding, cache_path=self.cache_path)
        if replace_all:
            self._entries = {}
        elif replace_symbol is not None:
            normalized_symbol = normalize_symbol(replace_symbol)
            self._entries = {
                chunk_id: value
                for chunk_id, value in self._entries.items()
                if value[0].symbol != normalized_symbol
            }
        self._entries.update(
            {candidate.chunk_id: (candidate, embedding) for candidate, embedding in entries}
        )
        self._write_entries()

    def search(self, request: ResearchSearchRequest) -> list[ResearchRetrievalCandidate]:
        return search_vector_entries(self._entries, request)

    def retrieval_quality(
        self,
        request: ResearchSearchRequest,
        *,
        expanded_terms: Sequence[str] | None = None,
    ) -> ResearchRetrievalQuality:
        candidates = self.search(request)
        return build_vector_retrieval_quality(
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

    def upsert_many(
        self,
        entries: Sequence[tuple[ResearchRetrievalCandidate, ResearchEmbedding]],
        *,
        replace_symbol: str | None = None,
        replace_all: bool = False,
    ) -> None: ...
