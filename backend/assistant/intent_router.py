from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssistantAgentIntent = Literal[
    "smalltalk",
    "self_introduction",
    "concept_explanation",
    "smai_how_to_use",
    "market_overview",
    "theme_or_sector_discovery",
    "stock_candidate_search",
    "stock_analysis",
    "news_lookup",
    "data_quality_check",
    "report_creation",
    "screen_navigation",
    "unknown_or_ambiguous",
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
        "self_introduction",
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
        "concept_explanation",
        (
            "セクターの意味",
            "セクターって何",
            "perって何",
            "pbrって何",
            "roeって何",
            "etfって何",
            "投信とetfの違い",
            "下振れ警戒って何",
            "ai予測ってどう見れば",
            "とは何",
            "どういう意味",
            "意味わかりますか",
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
        "report_creation",
        (
            "レポートにして",
            "確認レポート",
            "レポートを作",
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
            "上向き兆候",
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
        "news_lookup",
        (
            "ニュース",
            "材料を見",
            "開示",
            "tdnet",
        ),
    ),
    (
        "smai_how_to_use",
        (
            "使い方",
            "どこを見",
            "画面",
            "操作",
            "smaiでは",
            "何から見れば",
        ),
    ),
)


def detect_assistant_intent(message: str) -> AssistantIntentDecision:
    text = message.strip().lower()
    if not text:
        return AssistantIntentDecision(intent="unknown_or_ambiguous", confidence="low")

    for intent, terms in _INTENT_TERMS:
        matched = tuple(term for term in terms if term in text)
        if matched:
            return AssistantIntentDecision(
                intent=intent,
                confidence="high" if len(matched) >= 2 else "medium",
                matched_terms=matched,
            )

    if _is_broad_discovery(text):
        return AssistantIntentDecision(
            intent="theme_or_sector_discovery",
            confidence="high",
            matched_terms=("テーマ・セクター探索",),
        )

    if any(term in text for term in ("ランキングで比較", "候補銘柄", "候補を出して")):
        return AssistantIntentDecision(
            intent="stock_candidate_search",
            confidence="high",
            matched_terms=("候補探索",),
        )

    if any(term in text for term in ("コックピットで", "詳しく見たい", "深掘り")):
        return AssistantIntentDecision(
            intent="stock_analysis",
            confidence="high",
            matched_terms=("銘柄深掘り",),
        )

    if any(term in text for term in ("データがおかしい", "更新日", "取得元", "異常値")):
        return AssistantIntentDecision(
            intent="data_quality_check",
            confidence="high",
            matched_terms=("データ品質",),
        )

    if any(
        term in text
        for term in (
            "銘柄",
            "この株",
            "この会社",
            "トヨタ",
            "任天堂",
            "三菱ufj",
            "大阪ガス",
            "nvidia",
        )
    ):
        return AssistantIntentDecision(
            intent="stock_analysis",
            confidence="medium",
            matched_terms=("銘柄",),
        )

    if any(term in text for term in ("こんにちは", "こんばんは", "おはよう", "雑談")):
        return AssistantIntentDecision(intent="smalltalk", confidence="medium")
    return AssistantIntentDecision(intent="unknown_or_ambiguous", confidence="low")


def _is_broad_discovery(text: str) -> bool:
    broad_subject = any(
        term in text
        for term in (
            "銘柄やセクター",
            "注目のテーマ",
            "注目テーマ",
            "強そうな業界",
            "どのセクター",
            "投資先の候補",
        )
    )
    discovery_word = any(
        term in text for term in ("上がりそう", "良さそう", "注目", "候補", "ざっくり")
    )
    return broad_subject and discovery_word
