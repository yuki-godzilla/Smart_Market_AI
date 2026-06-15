from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssistantAgentIntent = Literal[
    "app_help",
    "identity",
    "capability_help",
    "stock_summary",
    "forecast_check",
    "forecast_risk_compare",
    "chart_check",
    "news_materials",
    "rag_search",
    "decision_report_draft",
    "file_export",
    "free_chat",
    "unknown",
]


@dataclass(frozen=True)
class AssistantIntentDecision:
    intent: AssistantAgentIntent
    confidence: str
    matched_terms: tuple[str, ...] = ()


_INTENT_TERMS: tuple[tuple[AssistantAgentIntent, tuple[str, ...]], ...] = (
    (
        "identity",
        (
            "あなたの名前",
            "あなたのなまえ",
            "あなたは誰",
            "あなたはだれ",
            "君の名前",
            "君は誰",
            "名前は",
            "名前を教えて",
            "お名前",
            "なまえ",
            "だれ",
            "誰",
            "who are you",
            "your name",
        ),
    ),
    (
        "capability_help",
        (
            "何ができる",
            "なにができる",
            "できること",
            "何を相談",
            "何を聞ける",
            "どう使える",
            "どんなことができる",
            "help",
            "capability",
        ),
    ),
    (
        "file_export",
        (
            "ファイルに出して",
            "markdownで保存",
            "mdで出力",
            "メモとして保存",
            "レポートを保存",
            "保存して",
        ),
    ),
    (
        "decision_report_draft",
        (
            "レポートにして",
            "decision report",
            "判断メモ",
            "メモにまとめて",
            "整理して",
            "下書き",
        ),
    ),
    (
        "forecast_risk_compare",
        (
            "予測とリスク",
            "予測もリスク",
            "下振れ警戒",
            "比べて",
            "比較して",
        ),
    ),
    (
        "forecast_check",
        (
            "予測を確認",
            "予測を",
            "予測も",
            "予測確認",
            "ai予測",
            "上昇気配",
            "予測はどう",
            "forecast",
        ),
    ),
    (
        "chart_check",
        (
            "チャート",
            "株価チャート",
            "価格推移",
            "トレンド",
            "値動き",
        ),
    ),
    (
        "rag_search",
        (
            "rag",
            "根拠資料",
            "根拠を探",
            "irを見",
            "開示を探",
            "research evidence",
        ),
    ),
    (
        "news_materials",
        (
            "ニュース",
            "材料を見",
            "開示",
            "tdnet",
        ),
    ),
    (
        "app_help",
        (
            "使い方",
            "どこを見",
            "画面",
            "操作",
            "smaiでは",
        ),
    ),
)


def detect_assistant_intent(message: str) -> AssistantIntentDecision:
    text = message.strip().lower()
    if not text:
        return AssistantIntentDecision(intent="unknown", confidence="low")

    for intent, terms in _INTENT_TERMS:
        matched = tuple(term for term in terms if term in text)
        if matched:
            return AssistantIntentDecision(
                intent=intent,
                confidence="high" if len(matched) >= 2 else "medium",
                matched_terms=matched,
            )

    if any(term in text for term in ("銘柄", "この株", "この会社", "トヨタ", "大阪ガス")):
        return AssistantIntentDecision(
            intent="stock_summary",
            confidence="medium",
            matched_terms=("銘柄",),
        )

    return AssistantIntentDecision(intent="free_chat", confidence="low")
