from __future__ import annotations

from collections.abc import Sequence

from backend.assistant import (
    AssistantGatewayTaskType,
    AssistantMessage,
    AssistantResponse,
)
from backend.core.config import Settings
from ui.components.assistant import SmaiAssistantContext, assistant_response_for_context

NEWS_REFRESH_CONFIRMATION_MESSAGE = "ニュースを更新できます。内容を確認してから実行してください。"


def copilot_response_for_request(
    context: SmaiAssistantContext,
    question: str,
    *,
    direct_news_refresh: bool,
    conversation_id: str,
    message_history: Sequence[AssistantMessage],
    referenced_context_ids: Sequence[str],
    gateway_task_type: AssistantGatewayTaskType,
    settings: Settings,
) -> AssistantResponse:
    if direct_news_refresh:
        return AssistantResponse(
            intent="research",
            answer=NEWS_REFRESH_CONFIRMATION_MESSAGE,
            response_source="deterministic",
        )
    return assistant_response_for_context(
        context,
        question,
        conversation_id=conversation_id,
        message_history=message_history,
        referenced_context_ids=referenced_context_ids,
        gateway_task_type=gateway_task_type,
        settings=settings,
    )
