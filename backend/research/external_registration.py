from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Protocol, TypeVar

from backend.research.external_contracts import (
    ExternalResearchFetchManifestEntry,
    ExternalResearchFetchRequest,
    ExternalResearchSourcePayload,
)


class RegisteredExternalDocument(Protocol):
    @property
    def document_id(self) -> str: ...

    @property
    def provider(self) -> str: ...

    @property
    def source_type(self) -> object: ...


_DocumentT = TypeVar("_DocumentT", bound=RegisteredExternalDocument)


def safe_cache_fragment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._") or "source"


def external_payload_markdown(payload: ExternalResearchSourcePayload) -> str:
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
        f"- Content digest: {external_payload_content_digest(payload)}",
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


def external_payload_content_digest(payload: ExternalResearchSourcePayload) -> str:
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


def external_research_content_summary(payload: ExternalResearchSourcePayload) -> str:
    max_chars = 1800 if payload.source_type == "provider_profile" else 360
    return _excerpt(payload.content, max_chars=max_chars)


def find_registered_external_document(
    documents: Iterable[_DocumentT],
    raw_text_by_document_id: Mapping[str, str],
    payload: ExternalResearchSourcePayload,
) -> _DocumentT | None:
    """Find an existing session document for the same fetched source content."""

    source_url = payload.source_url.strip()
    if not source_url:
        return None
    digest_marker = f"- Content digest: {external_payload_content_digest(payload)}"
    source_markers = (f"- Source URL: {source_url}", f"url: {source_url}")
    for document in documents:
        if document.provider != payload.provider or document.source_type != payload.source_type:
            continue
        text = raw_text_by_document_id.get(document.document_id, "")
        if digest_marker in text and any(marker in text for marker in source_markers):
            return document
    return None


def write_external_payload_archive(
    cache_dir: Path,
    payload: ExternalResearchSourcePayload,
) -> Path:
    markdown = external_payload_markdown(payload)
    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:12]
    path = cache_dir / (
        f"{safe_cache_fragment(payload.symbol)}_"
        f"{payload.source_type}_{safe_cache_fragment(payload.provider)}_"
        f"{payload.fetched_at:%Y%m%d%H%M%S}_{digest}.md"
    )
    path.write_text(markdown, encoding="utf-8")
    return path


def write_external_fetch_manifest(
    cache_dir: Path,
    *,
    request: ExternalResearchFetchRequest,
    provider: str,
    fetched_at: datetime,
    entries: list[ExternalResearchFetchManifestEntry],
    warnings: list[str],
) -> Path:
    manifest = {
        "schema_version": "external-research-fetch-manifest-v1",
        "symbol": _normalize_symbol(request.symbol),
        "provider": provider,
        "fetched_at": fetched_at.isoformat(),
        "allow_network": request.allow_network,
        "entry_count": len(entries),
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "warnings": warnings,
    }
    path = cache_dir / (
        f"{safe_cache_fragment(request.symbol)}_"
        f"{safe_cache_fragment(provider)}_"
        f"manifest_{fetched_at:%Y%m%d%H%M%S}.json"
    )
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _excerpt(text: str, *, max_chars: int = 220) -> str:
    single_line = re.sub(r"\s+", " ", text).strip()
    if len(single_line) <= max_chars:
        return single_line
    return f"{single_line[: max_chars - 3].rstrip()}..."
