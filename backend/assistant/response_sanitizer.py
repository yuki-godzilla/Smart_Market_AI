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

# Gateway prompts prohibit investment advice, but provider output is untrusted.
# Keep this narrow enough that an answer which merely repeats a user's question
# (for example, "買うべきかどうかは判断できません") remains usable while
# prescriptive wording is rejected at the application boundary.
_INVESTMENT_ADVICE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:買う|買った|売る|売った|保有する)(?:べき(?!か)(?:です|だ)?|ことを(?:推奨|おすすめ)|のが(?:推奨|おすすめ)|よう(?:に)?(?:してください|勧めます)|(?:方|ほう)が(?:よい|いい))",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:買い|売り|購入|売却)(?:を|は)?(?:推奨|おすすめ|してください|した方が|したほうが|検討すべき)"
    ),
    re.compile(
        r"保有(?:を)?(?:継続|開始|解消|続ける|始める|やめる).{0,8}(?:推奨|おすすめ|してください|した方が|したほうが)"
    ),
    re.compile(
        r"(?:購入|買い|売り|売却|保有).{0,18}慎重に(?:検討|判断).{0,8}(?:してください|が必要)"
    ),
    re.compile(
        r"(?:今|現時点|短期|中長期)?(?:は|なら)?(?:買い時|売り時)(?:です|だ|と(?:思います|考えます)|でしょう)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:you\s+should|you\s+ought\s+to)\s+(?:buy|sell|hold)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:recommend|suggest)(?:\s+that\s+you|\s+you)?\s+(?:buy(?:ing)?|sell(?:ing)?|hold(?:ing)?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:strong buy|strong sell|buy this|sell this|hold this)", re.IGNORECASE),
)


def is_internal_presentation_text(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    if not normalized:
        return False
    return any(pattern in normalized for pattern in FORBIDDEN_PRESENTATION_PATTERNS)


def contains_investment_advice(text: str) -> bool:
    """Return whether untrusted LLM text gives a prescriptive trading direction."""

    normalized = str(text or "").strip()
    return bool(normalized) and any(
        pattern.search(normalized) for pattern in _INVESTMENT_ADVICE_PATTERNS
    )


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
