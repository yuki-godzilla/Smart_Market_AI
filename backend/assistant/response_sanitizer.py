from __future__ import annotations

import re
from collections.abc import Iterable

FORBIDDEN_PRESENTATION_PATTERNS: tuple[str, ...] = (
    "provider raw fields",
    "debug logs",
    "full external source bodies",
    "external source bodies",
    "raw fields",
    "provider fields",
    "excluded",
    "the bundle is",
    "bundle is for explanation",
    "confirmation support",
    "not score",
    "not ranking",
    "ranking recomputation",
    "score or ranking recomputation",
    "privacy_notes",
    "safety_notes",
    "provider_notes",
    "internal_notes",
    "debug_notes",
    "tool says",
    "the tool says",
    "i need to",
    "first, i need",
    "the answer should",
    "json fields",
    "内部情報",
    "デバッグ情報",
    "provider情報",
    "raw field",
    "外部ソース本文",
    "ランキング再計算",
    "スコア再計算",
    "内部ログ",
    "開発者向け",
)

_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?.])\s+|\n+")


def is_internal_presentation_text(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    return any(pattern in normalized for pattern in FORBIDDEN_PRESENTATION_PATTERNS)


def sanitize_presentation_text(text: str) -> str:
    """Remove internal/provider/debug sentences before text reaches user-facing UI."""

    raw = str(text or "").strip()
    if not raw:
        return ""
    pieces = [piece.strip(" \t-•") for piece in _SENTENCE_BOUNDARY_RE.split(raw)]
    clean = [piece for piece in pieces if piece and not is_internal_presentation_text(piece)]
    if clean:
        separator = "\n" if "\n" in raw else " "
        return separator.join(clean).strip()
    return "" if is_internal_presentation_text(raw) else raw


def sanitize_presentation_items(items: Iterable[str], *, limit: int | None = None) -> list[str]:
    clean: list[str] = []
    seen: set[str] = set()
    for item in items:
        sanitized = sanitize_presentation_text(str(item or ""))
        if not sanitized or sanitized in seen:
            continue
        clean.append(sanitized)
        seen.add(sanitized)
        if limit is not None and len(clean) >= limit:
            break
    return clean
