from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from backend.assistant.intent_router import AssistantAgentIntent

AssistantActionCardLevel = Literal[0, 1, 2]


@dataclass(frozen=True)
class AssistantActionCardDecision:
    level: AssistantActionCardLevel
    reason: str

    @property
    def show_cards(self) -> bool:
        return self.level == 2


_LEVEL_ZERO_INTENTS: frozenset[AssistantAgentIntent] = frozenset(
    {
        "smalltalk",
        "self_introduction",
        "concept_explanation",
        "free_chat",
        "identity",
        "capability_help",
        "unknown",
        "unknown_or_ambiguous",
    }
)

_EXPLICIT_ACTION_TERMS = (
    "開いて",
    "調べて",
    "分析して",
    "比較して",
    "比較したい",
    "探したい",
    "候補を出して",
    "ニュースを見たい",
    "ニュースを取得",
    "レポートを作",
    "確認したい",
    "深掘りしたい",
    "詳しく見たい",
    "コックピットで",
    "ランキングで",
)


def decide_assistant_action_cards(
    message: str,
    intent: AssistantAgentIntent,
) -> AssistantActionCardDecision:
    """Apply the parent-SMAI deterministic restraint policy to action cards."""

    text = str(message or "").strip().lower()
    if intent in _LEVEL_ZERO_INTENTS:
        return AssistantActionCardDecision(
            level=0,
            reason="会話・自己紹介・用語説明・曖昧な相談では操作カードを表示しません。",
        )
    if intent in {"theme_or_sector_discovery", "market_overview", "smai_how_to_use"}:
        if not any(term in text for term in _EXPLICIT_ACTION_TERMS):
            return AssistantActionCardDecision(
                level=1,
                reason="広い相談や使い方案内では文章内の軽い提案に留めます。",
            )
    if any(term in text for term in _EXPLICIT_ACTION_TERMS):
        return AssistantActionCardDecision(
            level=2,
            reason="操作・調査・比較・作成の希望が明確なためカードを表示します。",
        )
    return AssistantActionCardDecision(
        level=1,
        reason="明確な実行希望がないため文章内の案内に留めます。",
    )
