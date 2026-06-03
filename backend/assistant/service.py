from __future__ import annotations

from typing import Literal, Sequence

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.reporting import DECISION_SUPPORT_NOTE, DecisionReportContext, DecisionReportSection

ASSISTANT_SCHEMA_VERSION = "assistant-response-v1"

AssistantIntent = Literal[
    "overview",
    "score",
    "risk",
    "research",
    "next_steps",
    "advice_boundary",
    "unknown",
]


class AssistantCitation(StrictBaseModel):
    """Report section reference used by the deterministic assistant response."""

    section_title: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    symbol: str | None = Field(default=None, min_length=1)


class AssistantRequest(StrictBaseModel):
    """Local-first assistant request built from existing report/research context."""

    question: str = Field(min_length=1)
    report_context: DecisionReportContext | None = None
    max_points: int = Field(default=4, ge=1, le=8)


class AssistantResponse(StrictBaseModel):
    """Deterministic assistant answer with explicit non-advice boundaries."""

    schema_version: str = ASSISTANT_SCHEMA_VERSION
    intent: AssistantIntent
    answer: str = Field(min_length=1)
    reasons: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    next_checkpoints: list[str] = Field(default_factory=list)
    citations: list[AssistantCitation] = Field(default_factory=list)
    decision_support_note: str = DECISION_SUPPORT_NOTE


class TemplateAssistantService:
    """Network-free assistant that explains existing SMAI context with templates."""

    def answer(self, request: AssistantRequest) -> AssistantResponse:
        question = request.question.strip()
        intent = _detect_intent(question)
        sections = _select_sections(request.report_context, intent)
        reasons = _collect_reasons(sections, request.max_points)
        cautions = _collect_cautions(sections, intent, request.max_points)
        next_checkpoints = _build_next_checkpoints(sections, intent, request.max_points)
        citations = [_citation_from_section(section) for section in sections[: request.max_points]]

        if request.report_context is None:
            cautions = _dedupe(
                [
                    "投資判断レポートや根拠資料が未指定のため、回答は一般的な確認順に限定します。",
                    *cautions,
                ]
            )
            next_checkpoints = _dedupe(
                [
                    "銘柄コックピットまたはランキングで投資判断レポートを作成してから、同じ質問を確認します。",
                    *next_checkpoints,
                ]
            )

        return AssistantResponse(
            intent=intent,
            answer=_build_answer(question, intent, sections, bool(request.report_context)),
            reasons=reasons,
            cautions=cautions,
            next_checkpoints=next_checkpoints,
            citations=citations,
        )


def _detect_intent(question: str) -> AssistantIntent:
    normalized = question.lower()
    if any(term in normalized for term in ("買", "売", "buy", "sell", "hold", "保有")):
        return "advice_boundary"
    if any(term in normalized for term in ("research", "根拠", "資料", "ニュース", "ir", "開示")):
        return "research"
    if any(term in normalized for term in ("risk", "リスク", "注意", "警戒", "下落")):
        return "risk"
    if any(term in normalized for term in ("score", "スコア", "評価", "順位", "ランキング")):
        return "score"
    if any(term in normalized for term in ("次", "確認", "どう見る", "何を見る")):
        return "next_steps"
    if any(term in normalized for term in ("概要", "要約", "まとめ", "summary")):
        return "overview"
    return "unknown"


def _select_sections(
    report_context: DecisionReportContext | None,
    intent: AssistantIntent,
) -> list[DecisionReportSection]:
    if report_context is None:
        return []

    keywords_by_intent: dict[AssistantIntent, tuple[str, ...]] = {
        "overview": (),
        "score": ("score", "スコア", "screening", "ranking", "investment"),
        "risk": ("risk", "リスク", "warning", "注意", "警戒", "breach"),
        "research": ("research", "根拠", "資料", "news", "ニュース", "ir", "開示"),
        "next_steps": ("checkpoint", "確認", "memo", "メモ", "risk", "research"),
        "advice_boundary": ("score", "risk", "research", "checkpoint", "確認"),
        "unknown": (),
    }
    keywords = keywords_by_intent[intent]
    if not keywords:
        return list(report_context.sections)

    matched = [
        section
        for section in report_context.sections
        if _section_matches_keywords(section, keywords)
    ]
    return matched or list(report_context.sections)


def _section_matches_keywords(
    section: DecisionReportSection,
    keywords: Sequence[str],
) -> bool:
    haystack = " ".join(
        [
            section.title,
            section.source.kind,
            *section.summary.keys(),
            *section.summary.values(),
            *section.warnings,
            *section.notes,
            *[value for row in section.rows for value in row.values()],
        ]
    ).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _build_answer(
    question: str,
    intent: AssistantIntent,
    sections: Sequence[DecisionReportSection],
    has_context: bool,
) -> str:
    if intent == "advice_boundary":
        return (
            "この質問には、買う・売る・保有するといった指示では答えません。"
            "SMAI Assistant は、手元のスコア、リスク、根拠資料を整理し、"
            "判断前に確認する観点を示します。"
        )
    if not has_context:
        return (
            "まだ具体的な分析コンテキストがないため、一般的な確認順を案内します。"
            "価格データ、スコア内訳、リスク、根拠資料を同じ銘柄でそろえて確認してください。"
        )

    section_phrase = _format_section_phrase(sections)
    if intent == "score":
        return f"{section_phrase}から、スコアは候補比較の入口として読みます。単独の売買判断ではなく、内訳と警告を合わせて確認します。"
    if intent == "risk":
        return f"{section_phrase}から、注意材料とデータ不足を先に確認します。リスク表示は安全保証ではなく、追加確認の優先度を示す材料です。"
    if intent == "research":
        return f"{section_phrase}から、根拠資料・ニュース・開示の出典と鮮度を確認します。資料で読める範囲と未確認項目を分けて扱います。"
    if intent == "next_steps":
        return f"{section_phrase}をもとに、次は不足データ、スコア内訳、リスク、根拠資料の順に確認します。"
    if intent == "overview":
        return f"{section_phrase}を要約すると、現在の分析結果は比較材料、注意材料、追加確認点に分けて読むのが安全です。"
    return f"{section_phrase}を参照し、分かっている材料と未確認の材料を分けて整理します。"


def _format_section_phrase(sections: Sequence[DecisionReportSection]) -> str:
    if not sections:
        return "投資判断レポート"
    titles = [section.title for section in sections[:3]]
    if len(sections) > 3:
        titles.append("ほか")
    return " / ".join(titles)


def _collect_reasons(
    sections: Sequence[DecisionReportSection],
    max_points: int,
) -> list[str]:
    candidates: list[str] = []
    for section in sections:
        candidates.extend(_summary_points(section))
        candidates.extend(_row_points(section))
        candidates.extend(section.notes)
    return _dedupe(candidates)[:max_points]


def _collect_cautions(
    sections: Sequence[DecisionReportSection],
    intent: AssistantIntent,
    max_points: int,
) -> list[str]:
    cautions: list[str] = []
    for section in sections:
        cautions.extend(section.warnings)
    if intent in {"score", "advice_boundary"}:
        cautions.append("スコアや順位は比較・分析用の参考値であり、売買推奨ではありません。")
    if intent == "research":
        cautions.append("根拠資料は出典、公開日、未確認項目を合わせて確認してください。")
    if intent == "risk":
        cautions.append("リスク表示は損失回避や安全性を保証するものではありません。")
    if not cautions:
        cautions.append("不足している情報がある場合は、結論ではなく追加確認の対象として扱います。")
    return _dedupe(cautions)[:max_points]


def _build_next_checkpoints(
    sections: Sequence[DecisionReportSection],
    intent: AssistantIntent,
    max_points: int,
) -> list[str]:
    checkpoints = _extract_confirmation_points(sections)
    defaults_by_intent: dict[AssistantIntent, list[str]] = {
        "overview": [
            "スコア内訳、価格トレンド、データ品質、根拠資料を同じ銘柄で見比べます。",
        ],
        "score": [
            "総合スコアだけでなく、Screening、Forecast、Risk、Data Quality の内訳を確認します。",
        ],
        "risk": [
            "警告がある場合は、価格変動、保有比率、データ欠損、短期材料を分けて確認します。",
        ],
        "research": [
            "出典URL、公開日、公式資料か外部ニュースか、未確認項目を確認します。",
        ],
        "next_steps": [
            "不足しているデータと、判断に使える根拠がそろっているデータを分けます。",
        ],
        "advice_boundary": [
            "売買判断ではなく、判断材料の不足、注意材料、確認済み根拠を整理します。",
        ],
        "unknown": [
            "質問をスコア、リスク、根拠資料、次の確認観点のどれかに分けて確認します。",
        ],
    }
    return _dedupe([*checkpoints, *defaults_by_intent[intent]])[:max_points]


def _summary_points(section: DecisionReportSection) -> list[str]:
    points = []
    for key, value in section.summary.items():
        if value:
            points.append(f"{key}: {value}")
    return points


def _row_points(section: DecisionReportSection) -> list[str]:
    points = []
    for row in section.rows:
        if not row:
            continue
        compact = " / ".join(f"{key}: {value}" for key, value in row.items() if value)
        if compact:
            points.append(compact)
    return points


def _extract_confirmation_points(
    sections: Sequence[DecisionReportSection],
) -> list[str]:
    points: list[str] = []
    for section in sections:
        for row in section.rows:
            for key, value in row.items():
                if value and any(term in key.lower() for term in ("confirm", "確認", "checkpoint")):
                    points.append(value)
    return points


def _citation_from_section(section: DecisionReportSection) -> AssistantCitation:
    return AssistantCitation(
        section_title=section.title,
        source_kind=section.source.kind,
        symbol=section.source.symbol,
    )


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
