from __future__ import annotations

from dataclasses import dataclass

from backend.assistant.conversation_mode import AssistantResearchIntent


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
    company_name: str | None
    requires_approval: bool
    approval_reason: str
    tools: tuple[AssistantResearchTool, ...]

    @property
    def has_external_tools(self) -> bool:
        return any(tool.external for tool in self.tools)
