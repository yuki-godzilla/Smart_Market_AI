"""Deterministic Research query expansion without retrieval or provider dependencies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]

from backend.research.contracts import (
    DEFAULT_RESEARCH_QUERY_TERMS,
    ResearchQueryExpansionResult,
    ResearchSearchError,
    ResearchTopicCategory,
)
from backend.research.vector_store import normalize_query_terms, query_terms


class ResearchQueryExpansionService:
    """Expand research queries with deterministic topic dictionaries."""

    def __init__(
        self,
        terms_by_category: Mapping[ResearchTopicCategory, Sequence[str]] | None = None,
    ) -> None:
        configured = terms_by_category or DEFAULT_RESEARCH_QUERY_TERMS
        self.terms_by_category = {
            category: tuple(normalize_query_terms(terms)) for category, terms in configured.items()
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
        terms = list(query_terms(query))
        if category is not None:
            terms.extend(self.terms_by_category.get(category, ()))
        return ResearchQueryExpansionResult(
            query=query,
            category=category,
            expanded_terms=normalize_query_terms(terms),
        )
