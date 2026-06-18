from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class IRCategoryRule:
    """Rule for assigning one source candidate to an IR summary category."""

    document_type: str
    ir_document_type: str
    allowed_source_types: tuple[str, ...]
    required_keywords: tuple[str, ...] = ()
    optional_keywords: tuple[str, ...] = ()
    exclude_keywords: tuple[str, ...] = ()
    preferred_source_types: tuple[str, ...] = ()
    source_types_without_keyword: tuple[str, ...] = ()
    priority: int = 100
    max_items: int = 1
    allow_tdnet_without_keyword: bool = False


@dataclass(frozen=True)
class IRDocumentCandidate:
    """Source candidate consumed by the rule-based IR classifier."""

    title: str
    source_type: str
    summary: str = ""
    body: str = ""
    source_url: str | None = None
    source_id: str | None = None
    source_title: str | None = None


@dataclass(frozen=True)
class IRCategoryMatch:
    """Selected match for one category."""

    rule: IRCategoryRule
    candidate: IRDocumentCandidate
    matched_keywords: tuple[str, ...]
    classification_confidence: float
    classification_reason: str

    @property
    def source_key(self) -> str:
        return ir_candidate_source_key(self.candidate)


def normalize_ir_text(value: str | None) -> str:
    """Normalize Japanese / English IR titles for keyword checks."""

    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    normalized = normalized.replace("・", " ")
    normalized = re.sub(r"[\s\u3000]+", " ", normalized)
    return normalized.strip()


def ir_candidate_source_key(candidate: IRDocumentCandidate) -> str:
    if candidate.source_url:
        return "url:" + normalize_ir_text(candidate.source_url).rstrip("/")
    if candidate.source_id:
        return "id:" + normalize_ir_text(candidate.source_id)
    return "title:" + normalize_ir_text(candidate.title)


def match_ir_category_rule(
    candidate: IRDocumentCandidate,
    rule: IRCategoryRule,
) -> IRCategoryMatch | None:
    source_type = normalize_ir_text(candidate.source_type)
    if source_type not in rule.allowed_source_types:
        return None
    candidate_text = normalize_ir_text(
        " ".join(
            part
            for part in (
                candidate.title,
                candidate.summary,
                candidate.body,
                candidate.source_title or "",
            )
            if part
        )
    )
    if _matched_keywords(candidate_text, rule.exclude_keywords):
        return None
    required_matches = _matched_keywords(candidate_text, rule.required_keywords)
    optional_matches = _matched_keywords(candidate_text, rule.optional_keywords)
    matched_keywords = tuple(dict.fromkeys((*required_matches, *optional_matches)))

    if rule.required_keywords and not required_matches:
        if source_type in rule.source_types_without_keyword:
            return _source_only_match(candidate, rule)
        if source_type == "tdnet" and rule.allow_tdnet_without_keyword:
            return IRCategoryMatch(
                rule=rule,
                candidate=candidate,
                matched_keywords=(),
                classification_confidence=0.45,
                classification_reason="tdnet_generic_disclosure",
            )
        return None

    if not rule.required_keywords and not matched_keywords:
        if source_type in rule.source_types_without_keyword:
            return _source_only_match(candidate, rule)
        if source_type == "tdnet" and rule.allow_tdnet_without_keyword:
            return IRCategoryMatch(
                rule=rule,
                candidate=candidate,
                matched_keywords=(),
                classification_confidence=0.45,
                classification_reason="tdnet_generic_disclosure",
            )
        return None

    confidence = 0.9 if required_matches else 0.7
    if source_type in rule.preferred_source_types:
        confidence = min(1.0, confidence + 0.05)
    if candidate.source_url:
        confidence = min(1.0, confidence + 0.02)
    return IRCategoryMatch(
        rule=rule,
        candidate=candidate,
        matched_keywords=matched_keywords,
        classification_confidence=confidence,
        classification_reason=(
            "specific_required_keyword_match" if required_matches else "optional_keyword_match"
        ),
    )


def classify_ir_document_candidates(
    candidates: Sequence[IRDocumentCandidate],
    rules: Sequence[IRCategoryRule] = (),
) -> dict[str, IRCategoryMatch]:
    """Classify candidates and suppress duplicate use of the same source."""

    active_rules = tuple(rules or DEFAULT_IR_CATEGORY_RULES)
    matches: list[IRCategoryMatch] = []
    for candidate in candidates:
        for rule in active_rules:
            match = match_ir_category_rule(candidate, rule)
            if match is not None:
                matches.append(match)
    matches.sort(
        key=lambda match: (
            match.rule.priority,
            -match.classification_confidence,
            0 if match.candidate.source_url else 1,
            normalize_ir_text(match.candidate.title),
        )
    )
    selected: dict[str, IRCategoryMatch] = {}
    used_source_keys: set[str] = set()
    for match in matches:
        document_type = match.rule.document_type
        if document_type in selected:
            continue
        if match.source_key in used_source_keys:
            continue
        selected[document_type] = match
        used_source_keys.add(match.source_key)
    return selected


def _matched_keywords(text: str, keywords: Sequence[str]) -> tuple[str, ...]:
    matches: list[str] = []
    for keyword in keywords:
        normalized_keyword = normalize_ir_text(keyword)
        if normalized_keyword and normalized_keyword in text:
            matches.append(keyword)
    return tuple(matches)


def _source_only_match(
    candidate: IRDocumentCandidate,
    rule: IRCategoryRule,
) -> IRCategoryMatch:
    source_type = normalize_ir_text(candidate.source_type)
    confidence = 0.6 if rule.document_type == "公式IRサイト" else 0.7
    if source_type in rule.preferred_source_types:
        confidence = min(1.0, confidence + 0.05)
    return IRCategoryMatch(
        rule=rule,
        candidate=candidate,
        matched_keywords=(),
        classification_confidence=confidence,
        classification_reason="source_type_match",
    )


DEFAULT_IR_CATEGORY_RULES: tuple[IRCategoryRule, ...] = (
    IRCategoryRule(
        document_type="決算短信",
        ir_document_type="earnings_summary",
        allowed_source_types=("earnings_report", "tdnet", "company_ir", "user_note"),
        required_keywords=(
            "決算短信",
            "四半期決算短信",
            "通期決算短信",
            "第1四半期決算短信",
            "第2四半期決算短信",
            "第3四半期決算短信",
            "期末決算短信",
            "Consolidated Financial Results",
            "Financial Results",
        ),
        exclude_keywords=(
            "決算説明資料",
            "決算説明会",
            "説明会資料",
            "Presentation",
            "Briefing",
        ),
        preferred_source_types=("earnings_report",),
        source_types_without_keyword=("earnings_report",),
        priority=10,
    ),
    IRCategoryRule(
        document_type="決算説明資料",
        ir_document_type="earnings_presentation",
        allowed_source_types=("earnings_presentation", "tdnet", "company_ir", "user_note"),
        required_keywords=(
            "決算説明資料",
            "決算説明",
            "決算説明会",
            "決算プレゼン",
            "説明会資料",
            "Financial Results Presentation",
            "Earnings Presentation",
            "Results Briefing",
        ),
        preferred_source_types=("earnings_presentation",),
        source_types_without_keyword=("earnings_presentation",),
        priority=20,
    ),
    IRCategoryRule(
        document_type="有価証券報告書",
        ir_document_type="annual_report",
        allowed_source_types=(
            "annual_report",
            "integrated_report",
            "tdnet",
            "company_ir",
            "user_note",
        ),
        required_keywords=(
            "有価証券報告書",
            "四半期報告書",
            "半期報告書",
            "訂正報告書",
            "Annual Securities Report",
            "Quarterly Securities Report",
            "Annual Report",
        ),
        preferred_source_types=("annual_report", "integrated_report"),
        source_types_without_keyword=("annual_report", "integrated_report"),
        priority=30,
    ),
    IRCategoryRule(
        document_type="業績予想修正",
        ir_document_type="forecast_revision",
        allowed_source_types=("tdnet", "earnings_report", "company_ir", "user_note"),
        required_keywords=(
            "業績予想",
            "業績予想の修正",
            "通期業績予想",
            "連結業績予想",
            "個別業績予想",
            "上方修正",
            "下方修正",
            "業績見通し",
            "売上予想",
            "利益予想",
            "営業利益予想",
            "経常利益予想",
            "forecast revision",
            "earnings forecast",
            "revision of earnings forecast",
        ),
        preferred_source_types=("tdnet", "earnings_report"),
        priority=40,
    ),
    IRCategoryRule(
        document_type="配当・自社株買い",
        ir_document_type="shareholder_return",
        allowed_source_types=("tdnet", "earnings_report", "company_ir", "user_note"),
        required_keywords=(
            "配当",
            "剰余金の配当",
            "配当予想",
            "増配",
            "減配",
            "記念配当",
            "特別配当",
            "自己株式取得",
            "自己株式の取得",
            "自社株買い",
            "自己株式取得状況",
            "自己株式取得終了",
            "自己株式の消却",
            "株式消却",
            "share repurchase",
            "buyback",
            "dividend",
        ),
        exclude_keywords=(
            "自己株式処分",
            "第三者割当",
            "譲渡制限付株式",
            "リストリクテッド ストック",
            "リストリクテッド・ストック",
            "RSU",
            "ストック ユニット",
            "ストック・ユニット",
            "株式報酬",
            "役員報酬",
            "払込完了",
            "処分価額",
            "restricted stock",
            "stock unit",
            "stock compensation",
        ),
        preferred_source_types=("tdnet", "earnings_report"),
        priority=50,
    ),
    IRCategoryRule(
        document_type="中期経営計画",
        ir_document_type="medium_term_plan",
        allowed_source_types=("medium_term_plan", "tdnet", "company_ir", "user_note"),
        required_keywords=(
            "中期経営計画",
            "中期計画",
            "中計",
            "経営計画",
            "中期経営方針",
            "Medium-term Management Plan",
            "Medium Term Management Plan",
            "Management Plan",
        ),
        preferred_source_types=("medium_term_plan",),
        source_types_without_keyword=("medium_term_plan",),
        priority=60,
    ),
    IRCategoryRule(
        document_type="公式IRサイト",
        ir_document_type="other",
        allowed_source_types=("company_ir",),
        optional_keywords=("IR", "investor relations", "投資家", "株主"),
        preferred_source_types=("company_ir",),
        source_types_without_keyword=("company_ir",),
        priority=70,
    ),
    IRCategoryRule(
        document_type="適時開示",
        ir_document_type="timely_disclosure",
        allowed_source_types=("tdnet",),
        optional_keywords=("適時開示", "TDnet", "timely disclosure"),
        preferred_source_types=("tdnet",),
        priority=80,
        allow_tdnet_without_keyword=True,
    ),
)
