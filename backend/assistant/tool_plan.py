from __future__ import annotations

from dataclasses import dataclass

from backend.assistant.conversation_mode import (
    AssistantConversationModeDecision,
    AssistantResearchIntent,
    route_assistant_conversation_mode,
)


@dataclass(frozen=True)
class AssistantResearchTool:
    name: str
    label: str
    reason: str
    external: bool
    required: bool


@dataclass(frozen=True)
class AssistantResearchToolPlan:
    intent: AssistantResearchIntent
    user_question: str
    symbol_query: str | None
    symbol: str | None
    requires_approval: bool
    approval_reason: str
    tools: tuple[AssistantResearchTool, ...]

    @property
    def has_external_tools(self) -> bool:
        return any(tool.external for tool in self.tools)


def build_assistant_research_tool_plan(
    user_question: str,
    decision: AssistantConversationModeDecision | None = None,
) -> AssistantResearchToolPlan | None:
    decision = decision or route_assistant_conversation_mode(user_question)
    if decision.conversation_mode != "research_plan":
        return None

    symbol_query = decision.symbol_query
    symbol = _symbol_for_query(symbol_query)
    intent = decision.intent
    tools = _tools_for_intent(intent, symbol_query=symbol_query, symbol=symbol)
    approval_reason = _approval_reason_for_intent(
        intent, has_external=any(t.external for t in tools)
    )
    return AssistantResearchToolPlan(
        intent=intent,
        user_question=user_question.strip(),
        symbol_query=symbol_query,
        symbol=symbol,
        requires_approval=decision.requires_approval,
        approval_reason=approval_reason,
        tools=tools,
    )


def _tools_for_intent(
    intent: AssistantResearchIntent,
    *,
    symbol_query: str | None,
    symbol: str | None,
) -> tuple[AssistantResearchTool, ...]:
    if intent == "stock_forward_view":
        return (
            AssistantResearchTool(
                name="symbol_resolve",
                label="銘柄特定",
                reason=f"{symbol_query or '入力内容'}を銘柄コードに変換します。",
                external=False,
                required=True,
            ),
            AssistantResearchTool(
                name="price_fetch",
                label="価格データ",
                reason="直近の価格推移と変動を確認します。",
                external=True,
                required=True,
            ),
            AssistantResearchTool(
                name="forecast_fetch",
                label="AI予測",
                reason="AI予測インサイトと下振れ警戒を確認します。",
                external=False,
                required=True,
            ),
            AssistantResearchTool(
                name="news_fetch",
                label="ニュース",
                reason="最新ニュースや開示材料を確認します。",
                external=True,
                required=False,
            ),
            AssistantResearchTool(
                name="research_fetch",
                label="Research Evidence",
                reason="根拠資料や外部参照ソースを確認します。",
                external=True,
                required=False,
            ),
        )
    if intent in {"news_research", "investment_material_scan"}:
        return (
            AssistantResearchTool(
                name="news_fetch",
                label="ニュース",
                reason="最新ニュースや市場動向を取得して分類します。",
                external=True,
                required=True,
            ),
            AssistantResearchTool(
                name="research_fetch",
                label="Research Evidence",
                reason="関連する開示・IR・根拠資料を確認します。",
                external=True,
                required=False,
            ),
            AssistantResearchTool(
                name="symbol_resolve",
                label="関連銘柄の特定",
                reason="ニュース内の関連銘柄やテーマを整理します。",
                external=False,
                required=False,
            ),
        )
    if intent == "decision_report_request":
        return (
            AssistantResearchTool(
                name="decision_report_draft",
                label="Decision Report下書き",
                reason="現在の会話と取得済み材料を判断メモ向けに整理します。",
                external=False,
                required=True,
            ),
        )
    if intent == "theme_stock_discovery":
        return (
            AssistantResearchTool(
                name="symbol_resolve",
                label="テーマ抽出",
                reason="テーマや条件を候補検索用の条件に変換します。",
                external=False,
                required=True,
            ),
            AssistantResearchTool(
                name="ranking_query",
                label="ランキング確認",
                reason="候補銘柄を安定性・上昇気配・下振れ警戒で比較します。",
                external=False,
                required=False,
            ),
        )
    if intent == "ranking_query":
        return (
            AssistantResearchTool(
                name="ranking_query",
                label="ランキング確認",
                reason="現在のランキング条件や候補スコアを確認します。",
                external=False,
                required=True,
            ),
        )
    if intent == "market_radar_query":
        return (
            AssistantResearchTool(
                name="news_fetch",
                label="市場ニュース",
                reason="市場全体やセクターの材料を確認します。",
                external=True,
                required=True,
            ),
        )
    return ()


def _approval_reason_for_intent(intent: AssistantResearchIntent, *, has_external: bool) -> str:
    if intent == "decision_report_request":
        return "Decision Report下書きを作る前に、保存・整理する内容を確認します。"
    if has_external:
        return "価格・ニュース・根拠資料などの外部取得が含まれるため、実行前に確認します。"
    return "SMAI内の材料を確認して整理するため、実行前に確認します。"


def _symbol_for_query(symbol_query: str | None) -> str | None:
    if not symbol_query:
        return None
    aliases = {
        "トヨタ": "7203.T",
        "toyota": "7203.T",
        "ソニー": "6758.T",
        "sony": "6758.T",
        "ntt": "9432.T",
        "三菱商事": "8058.T",
        "大阪ガス": "9532.T",
    }
    lowered = symbol_query.lower()
    if lowered in aliases:
        return aliases[lowered]
    cleaned = symbol_query.strip().upper()
    if cleaned.endswith(".T") and cleaned[:-2].isdigit():
        return cleaned
    if cleaned.isascii() and cleaned.isalnum() and 1 <= len(cleaned) <= 5:
        return cleaned
    return None
