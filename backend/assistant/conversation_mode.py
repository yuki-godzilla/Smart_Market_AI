from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AssistantConversationMode = Literal[
    "normal_chat",
    "soft_research_suggestion",
    "research_plan",
]

AssistantResearchIntent = Literal[
    "none",
    "stock_forward_view",
    "news_research",
    "investment_material_scan",
    "decision_report_request",
    "theme_stock_discovery",
    "ranking_query",
    "market_radar_query",
]


@dataclass(frozen=True)
class AssistantConversationModeDecision:
    conversation_mode: AssistantConversationMode
    intent: AssistantResearchIntent
    confidence: float
    requires_research: bool
    requires_approval: bool
    reason: str
    symbol_query: str | None = None
    tool_plan_enabled: bool = False
    matched_terms: tuple[str, ...] = ()


_NORMAL_CHAT_TERMS = (
    "こんにちは",
    "こんばんは",
    "おはよう",
    "ありがとう",
    "使い方",
    "何ができる",
    "なにができる",
    "できること",
    "あなたの名前",
    "あなたは誰",
    "強気と弱気",
    "違いは",
    "とは",
    "どういう意味",
    "銘柄コックピットって何",
    "ランキング画面",
)

_KNOWN_SYMBOL_ALIASES = (
    "トヨタ",
    "ソニー",
    "任天堂",
    "ntt",
    "三菱ufj",
    "三菱商事",
    "大阪ガス",
    "nvidia",
    "microsoft",
    "apple",
    "tesla",
    "toyota",
    "sony",
)

_FUND_PRODUCT_TERMS = (
    "emaxis slim 米国株式",
    "sbi・v・s&p500",
    "maxis米国株式",
)

_AMBIGUOUS_FUND_TERMS = ("s&p 500 maxim", "s&p500 maxim")

_THEME_TERMS = (
    "半導体",
    "ai関連",
    "高配当",
    "ディフェンシブ",
    "日本株",
    "米国株",
    "グロース",
)

_FORWARD_VIEW_TERMS = (
    "今後",
    "見たい",
    "確認したい",
    "高配当目線",
    "おかしくない",
    "上がる",
    "上昇",
    "伸びそう",
    "買って",
    "買うべき",
    "売った方",
    "大丈夫",
    "見る価値",
)

_NEWS_RESEARCH_TERMS = (
    "最新ニュース",
    "ニュースを見",
    "ニュース材料",
    "市場動向",
    "投資判断に影響",
    "気にした方がいいニュース",
    "注意する材料",
)

_REPORT_TERMS = (
    "decision report",
    "判断メモ",
    "reportに",
    "レポートに",
    "保存したい",
    "まとめて",
    "未確認事項",
    "確認レポート",
    "レポートを作",
)

_RANKING_TERMS = (
    "ランキング",
    "上位",
    "上昇気配",
    "下振れリスク",
    "候補銘柄",
)

_RADAR_TERMS = (
    "地合い",
    "市場全体",
    "セクター",
    "投資レーダー",
)


def route_assistant_conversation_mode(message: str) -> AssistantConversationModeDecision:
    text = str(message or "").strip()
    normalized = text.lower()
    if not normalized:
        return AssistantConversationModeDecision(
            conversation_mode="normal_chat",
            intent="none",
            confidence=0.0,
            requires_research=False,
            requires_approval=False,
            reason="空の発話のため通常会話として扱います。",
        )

    normal_matches = _matched_terms(normalized, _NORMAL_CHAT_TERMS)
    if _is_clear_normal_chat(normalized, normal_matches):
        return AssistantConversationModeDecision(
            conversation_mode="normal_chat",
            intent="none",
            confidence=0.9,
            requires_research=False,
            requires_approval=False,
            reason="挨拶、使い方、用語説明、画面説明に近いため通常会話で回答します。",
            matched_terms=normal_matches,
        )

    ambiguous_fund_matches = _matched_terms(normalized, _AMBIGUOUS_FUND_TERMS)
    if ambiguous_fund_matches:
        return AssistantConversationModeDecision(
            conversation_mode="soft_research_suggestion",
            intent="investment_material_scan",
            confidence=0.9,
            requires_research=False,
            requires_approval=False,
            reason="商品名が曖昧なため、外部取得前に投資信託・ETFの候補確認が必要です。",
            matched_terms=ambiguous_fund_matches,
        )

    symbol_query = _extract_symbol_or_theme_query(text)
    report_matches = _matched_terms(normalized, _REPORT_TERMS)
    if report_matches:
        return _research_plan_decision(
            intent="decision_report_request",
            reason="Decision Reportや判断メモへの整理依頼のため、下書き作成前に確認します。",
            symbol_query=symbol_query,
            matched_terms=report_matches,
            confidence=0.86,
        )

    news_matches = _matched_terms(normalized, _NEWS_RESEARCH_TERMS)
    if news_matches:
        return _research_plan_decision(
            intent="news_research",
            reason="最新ニュースや市場動向の確認意図が明確なため、取得前に承認を取ります。",
            symbol_query=symbol_query,
            matched_terms=news_matches,
            confidence=0.86,
        )

    ranking_matches = _matched_terms(normalized, _RANKING_TERMS)
    if ranking_matches and _has_research_action_word(normalized):
        return _research_plan_decision(
            intent="ranking_query",
            reason="ランキングや候補比較の確認意図が明確なため、実行前に承認を取ります。",
            symbol_query=symbol_query,
            matched_terms=ranking_matches,
            confidence=0.8,
        )

    radar_matches = _matched_terms(normalized, _RADAR_TERMS)
    if radar_matches and _has_research_action_word(normalized):
        return _research_plan_decision(
            intent="market_radar_query",
            reason="市場全体やセクター材料の確認意図があるため、調査計画を提示します。",
            symbol_query=symbol_query,
            matched_terms=radar_matches,
            confidence=0.78,
        )

    theme_matches = _matched_terms(normalized, _THEME_TERMS)
    if theme_matches and any(term in normalized for term in ("どれ", "銘柄", "探", "候補")):
        return _research_plan_decision(
            intent="theme_stock_discovery",
            reason="テーマや条件から候補を探す依頼のため、ランキングや銘柄DB利用前に承認を取ります。",
            symbol_query=symbol_query,
            matched_terms=theme_matches,
            confidence=0.82,
        )

    forward_matches = _matched_terms(normalized, _FORWARD_VIEW_TERMS)
    if symbol_query and forward_matches:
        return _research_plan_decision(
            intent="stock_forward_view",
            reason="特定銘柄と将来見通しの質問であり、価格・予測・ニュース確認が有効なため。",
            symbol_query=symbol_query,
            matched_terms=forward_matches,
            confidence=0.84,
        )

    if symbol_query or theme_matches or any(term in normalized for term in ("どう", "何を見")):
        return AssistantConversationModeDecision(
            conversation_mode="soft_research_suggestion",
            intent="stock_forward_view" if symbol_query else "investment_material_scan",
            confidence=0.58,
            requires_research=True,
            requires_approval=False,
            reason="対象や意図が少し曖昧なため、すぐ取得せず調査できることだけ提案します。",
            symbol_query=symbol_query,
            tool_plan_enabled=False,
            matched_terms=tuple(term for term in (symbol_query, *theme_matches) if term),
        )

    return AssistantConversationModeDecision(
        conversation_mode="normal_chat",
        intent="none",
        confidence=0.45,
        requires_research=False,
        requires_approval=False,
        reason="調査や材料取得の意図が明確ではないため通常会話で回答します。",
    )


def _research_plan_decision(
    *,
    intent: AssistantResearchIntent,
    reason: str,
    symbol_query: str | None,
    matched_terms: tuple[str, ...],
    confidence: float,
) -> AssistantConversationModeDecision:
    return AssistantConversationModeDecision(
        conversation_mode="research_plan",
        intent=intent,
        confidence=confidence,
        requires_research=True,
        requires_approval=True,
        reason=reason,
        symbol_query=symbol_query,
        tool_plan_enabled=True,
        matched_terms=matched_terms,
    )


def _matched_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term.lower() in text)


def _is_clear_normal_chat(text: str, matches: tuple[str, ...]) -> bool:
    if not matches:
        return False
    if any(term in text for term in ("上がる", "買って", "最新ニュース", "投資判断")):
        return False
    if text in {"こんにちは", "こんばんは", "おはよう", "ありがとう"}:
        return True
    return any(
        term in text
        for term in (
            "使い方",
            "何ができる",
            "なにができる",
            "できること",
            "あなたの名前",
            "あなたは誰",
            "違い",
            "とは",
            "どういう意味",
            "って何",
        )
    )


def _has_research_action_word(text: str) -> bool:
    return any(
        term in text
        for term in (
            "教えて",
            "見て",
            "確認",
            "整理",
            "探",
            "どれ",
            "良さそう",
            "気にした",
            "注意",
        )
    )


def _extract_symbol_or_theme_query(message: str) -> str | None:
    normalized = message.lower()
    for product in _FUND_PRODUCT_TERMS:
        if product in normalized:
            return product
    for alias in _KNOWN_SYMBOL_ALIASES:
        if alias.lower() in normalized:
            return alias
    for theme in _THEME_TERMS:
        if theme.lower() in normalized:
            return theme
    for token in message.replace("。", " ").replace("？", " ").replace("?", " ").split():
        cleaned = token.strip().upper()
        if cleaned.endswith(".T") and cleaned[:-2].isdigit():
            return cleaned
        if cleaned.isascii() and cleaned.isalnum() and 1 <= len(cleaned) <= 5:
            return cleaned
    return None
