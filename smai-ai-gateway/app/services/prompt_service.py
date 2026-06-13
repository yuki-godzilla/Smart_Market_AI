from __future__ import annotations

from app.schemas.common import LlmMessage
from app.schemas.context_answer import ContextAnswerMessage, ContextAnswerRequest, ContextSection

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

    def build_context_answer_messages(self, request: ContextAnswerRequest) -> list[LlmMessage]:
        language_instruction = (
            "Answer in Japanese." if request.language == "ja" else "Answer in English."
        )
        system_prompt = (
            "You are a careful context-grounded assistant. "
            "Use only the supplied context. "
            "Do not invent facts, recompute scores, rank symbols, or give investment advice. "
            "If the context is insufficient, say what should be checked next. "
            f"{language_instruction}"
        )
        messages = [LlmMessage(role="system", content=system_prompt)]
        messages.extend(_history_messages(request.message_history[-6:]))
        messages.append(
            LlmMessage(
                role="user",
                content=_context_answer_user_prompt(request),
            )
        )
        return messages


def _history_messages(history: list[ContextAnswerMessage]) -> list[LlmMessage]:
    return [LlmMessage(role=item.role, content=item.content.strip()) for item in history]


def _context_answer_user_prompt(request: ContextAnswerRequest) -> str:
    context = request.context
    sections = "\n\n".join(_section_prompt(section) for section in context.sections[:8])
    privacy_notes = "\n".join(f"- {note}" for note in context.privacy_notes[:5])
    constraints = request.constraints
    return (
        f"Task: {request.task}\n"
        f"Question: {request.user_question.strip()}\n"
        f"Context title: {context.title}\n"
        f"Context source: {context.source}\n"
        f"Tags: {', '.join(context.tags[:8]) if context.tags else 'none'}\n\n"
        "Safety constraints:\n"
        f"- no_investment_advice: {constraints.no_investment_advice}\n"
        f"- do_not_change_scores: {constraints.do_not_change_scores}\n"
        f"- do_not_rank_symbols: {constraints.do_not_rank_symbols}\n"
        f"- answer_format: {constraints.answer_format}\n\n"
        f"Privacy notes:\n{privacy_notes or '- none'}\n\n"
        "Context sections:\n"
        f"{sections}\n\n"
        "Return only valid JSON with these keys:\n"
        "- answer: concise answer string\n"
        "- materials: array of 1 to 8 strings grounded in the supplied context\n"
        "- cautions: array of 1 to 8 strings, including uncertainty or missing checks when relevant\n"
        "- next_checkpoints: array of 1 to 6 strings\n"
        "- confidence: one of low, medium, high\n"
        "Do not wrap the JSON in markdown. Do not add fields."
    )


def _section_prompt(section: ContextSection) -> str:
    summary = "\n".join(
        f"  - {key}: {value}" for key, value in list(section.summary.items())[:8]
    )
    rows = "\n".join(
        "  - " + "; ".join(f"{key}: {value}" for key, value in row.items())
        for row in section.rows[:4]
    )
    warnings = "\n".join(f"  - {item}" for item in section.warnings[:5])
    notes = "\n".join(f"  - {item}" for item in section.notes[:5])
    return (
        f"[{section.section_id}] {section.title} ({section.source_kind})\n"
        f"Summary:\n{summary or '  - none'}\n"
        f"Rows:\n{rows or '  - none'}\n"
        f"Warnings:\n{warnings or '  - none'}\n"
        f"Notes:\n{notes or '  - none'}"
    )
