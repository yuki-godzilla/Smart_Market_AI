from __future__ import annotations

from app.schemas.common import LlmMessage

DEFAULT_CHAT_SYSTEM_PROMPT = "You are a helpful assistant."


class PromptService:
    """Build prompt messages without coupling API handlers to provider details."""

    def build_chat_messages(self, *, message: str, system_prompt: str | None) -> list[LlmMessage]:
        system = (system_prompt or DEFAULT_CHAT_SYSTEM_PROMPT).strip()
        return [
            LlmMessage(role="system", content=system),
            LlmMessage(role="user", content=message.strip()),
        ]

    def build_summarize_messages(self, *, text: str, purpose: str | None) -> list[LlmMessage]:
        normalized_purpose = (purpose or "general").strip()
        system_prompt = (
            "You summarize text clearly and conservatively. "
            "Do not add facts that are not present in the input."
        )
        user_prompt = (
            f"Purpose: {normalized_purpose}\n\n"
            "Summarize the following text in a concise, structured way:\n\n"
            f"{text.strip()}"
        )
        return [
            LlmMessage(role="system", content=system_prompt),
            LlmMessage(role="user", content=user_prompt),
        ]
