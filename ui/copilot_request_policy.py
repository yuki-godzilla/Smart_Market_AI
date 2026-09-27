from __future__ import annotations

from dataclasses import replace

from backend.assistant import AssistantToolPlanResult
from backend.assistant.action_card_policy import is_explicit_news_refresh_request
from backend.assistant.conversation_mode import (
    AssistantConversationModeDecision,
    route_assistant_conversation_mode,
)
from ui.components.assistant import SmaiAssistantContext


def route_news_safe_conversation(message: str) -> AssistantConversationModeDecision:
    decision = route_assistant_conversation_mode(message)
    if news_update_guidance(message) is None:
        return decision
    return replace(
        decision,
        conversation_mode="normal_chat",
        intent="none",
        confidence=1.0,
        requires_research=False,
        requires_approval=False,
        reason="ニュース更新への質問・否定・複合依頼は回答のみとします。",
        symbol_query=None,
        tool_plan_enabled=False,
        matched_terms=(),
    )


def ungrounded_news_reply(
    *,
    intent: str,
    context: SmaiAssistantContext,
    tool_plan: AssistantToolPlanResult | None,
    research_choice: str,
) -> str | None:
    if intent != "news_materials" or research_choice or context.rows or tool_plan is None:
        return None
    if any(
        result.name == "resolve_symbol" and result.status == "ok" for result in tool_plan.executed
    ):
        return None
    return (
        "この会話では、個別のニュース材料をまだ参照していません。"
        "市場全体のニュースは「投資レーダー」で確認できます。"
        "銘柄ごとの強気・弱気材料を整理する場合は、銘柄名かコードを指定してください。"
    )


def news_update_guidance(message: str) -> str | None:
    """Answer non-executable news-update wording without offering an action."""

    text = "".join(str(message or "").strip().lower().split())
    if "ニュース" not in text or "更新" not in text:
        return None
    if is_explicit_news_refresh_request(text):
        return None
    if any(
        phrase in text
        for phrase in (
            "更新してほしくない",
            "更新しないで",
            "更新は不要",
            "更新しなくていい",
            "更新しないでほしい",
        )
    ):
        return "ニュースは更新しません。必要になったときに、改めて依頼してください。"
    if any(mark in text for mark in ("？", "?", "方法", "やり方", "できますか", "できる？")):
        return (
            "はい、ニュースは更新できます。投資レーダーで更新するか、"
            "ここで「ニュースを更新して」と入力してください。実行前に内容を確認できます。"
        )
    if "ニュースを更新して" in text:
        next_action = (
            "ランキングの作り直しは「銘柄ランキング」画面で条件を確認して行ってください。"
            if "ランキング" in text
            else "残りの操作は、対象と条件を分けて依頼してください。"
        )
        return (
            "ニュース更新と他の操作は、まとめて実行しません。"
            "ニュースは「ニュースを更新して」と単独で依頼できます。"
            f"{next_action}"
        )
    return (
        "ニュース更新は実行していません。更新する場合は"
        "「ニュースを更新して」と単独で入力してください。"
    )
