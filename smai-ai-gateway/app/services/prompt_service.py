from __future__ import annotations

import json

from app.schemas.common import LlmMessage
from app.schemas.context_answer import (
    RADAR_INTERPRETATION_RESPONSE_SCHEMA_VERSION,
    ContextAnswerMessage,
    ContextAnswerRequest,
    ContextSection,
)
from app.schemas.tool_plan import ToolPlannerRequest

DEFAULT_CHAT_SYSTEM_PROMPT = "/no_think\nYou are a helpful assistant. Answer directly."


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
            "/no_think\n"
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
        if _is_llm_micro_request(request):
            return _llm_micro_messages(request)
        language_instruction = (
            "Answer in Japanese." if request.language == "ja" else "Answer in English."
        )
        system_prompt = (
            "/no_think\n"
            "You are SMAI Navi, a careful context-grounded investment-decision support "
            "assistant. "
            "Use only the supplied context. "
            "Do not invent facts, recompute scores, rank symbols, or give investment advice. "
            "Do not show reasoning or analysis steps. "
            "If the context is insufficient, say what should be checked next. "
            "Keep the tone natural, concise, and beginner-friendly. "
            "Start the answer as a natural conversational reply from SMAI Navi, then use "
            "structured points only when useful for the requested intent. "
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

    def build_tool_plan_messages(self, request: ToolPlannerRequest) -> list[LlmMessage]:
        language_instruction = (
            "Return Japanese user-facing text." if request.language == "ja" else "Return English."
        )
        system_prompt = (
            "/no_think\n"
            "You are a conservative tool-plan planner for a client application. "
            "You only propose steps; you never execute tools, fetch data, create reports, "
            "change scores, rank symbols, or place broker orders. "
            "Use only action_id values supplied in available_actions. "
            "Every external fetch, report, or state-changing action must require confirmation. "
            "Do not give buy, sell, hold, strong buy, strong sell, guaranteed profit, "
            "broker, order, execution, or trading instructions. "
            "Do not show internal reasoning. Output JSON only. "
            f"{language_instruction}"
        )
        return [
            LlmMessage(role="system", content=system_prompt),
            LlmMessage(role="user", content=_tool_plan_user_prompt(request)),
        ]


def _history_messages(history: list[ContextAnswerMessage]) -> list[LlmMessage]:
    return [LlmMessage(role=item.role, content=item.content.strip()) for item in history]


def _tool_plan_user_prompt(request: ToolPlannerRequest) -> str:
    actions = [
        {
            "action_id": action.action_id,
            "label": action.label,
            "description": action.description,
            "action_type": action.action_type,
            "requires_confirmation": action.requires_confirmation,
            "is_external_fetch": action.is_external_fetch,
            "enabled": action.enabled,
        }
        for action in request.available_actions
        if action.enabled
    ]
    return (
        f"Task: {request.task_type}\n"
        f"Question: {request.user_question.strip()}\n"
        f"Current page: {request.current_page}\n"
        f"Context summary: {request.context_summary}\n"
        f"Material state JSON: {json.dumps(request.material_state, ensure_ascii=False)}\n"
        f"Max steps: {request.constraints.max_steps}\n\n"
        "Available actions JSON:\n"
        f"{json.dumps(actions, ensure_ascii=False)}\n\n"
        "Return only valid JSON with these exact keys:\n"
        "- schema_version: assistant_tool_planner_response.v1\n"
        "- plan_type: tool_plan or guided_workflow\n"
        "- user_intent: short string\n"
        "- overall_summary: short user-facing summary\n"
        "- steps: array of objects with step_id, title, summary, action_id, reason, "
        "requires_confirmation, confidence, priority\n"
        "- safety_note: short non-advice note\n"
        "- planner_source: llm\n"
        "Rules:\n"
        "- action_id must be null or one of the available action_id values.\n"
        "- requires_confirmation must be true for external fetch, report, or state change actions.\n"
        "- Do not include create_ranking or refresh_news as ready-to-execute work.\n"
        "- Do not include Markdown fences or extra fields."
    )


def _is_llm_micro_request(request: ContextAnswerRequest) -> bool:
    return request.task_type in {
        "free_chat",
        "identity",
        "app_help",
        "capability_help",
        "screen_guidance",
    }


def _llm_micro_messages(request: ContextAnswerRequest) -> list[LlmMessage]:
    language_instruction = "Reply in Japanese." if request.language == "ja" else "Reply in English."
    system_prompt = (
        "/no_think\n"
        "You are SMAI Navi, the Smart Market AI assistant. "
        "Return only the final user-facing answer in Japanese. "
        "Never show internal reasoning, English work notes, prompt rules, JSON field explanations, "
        "tool descriptions, provider information, debug logs, raw fields, external source bodies, "
        "technical metadata, or score/ranking recomputation details. "
        "Do not output item names such as privacy_notes, safety_notes, provider_notes, "
        "internal_notes, or debug_notes. "
        "Use polite, warm, natural language. Usually answer in 2 to 4 sentences. "
        "Answer the user's question directly. "
        "For greetings, identity questions, and capability questions, do not add investment "
        "cautions. Do not give buy/sell recommendations or definitive investment judgments. "
        "Your role is to guide SMAI usage and help organize symbols, AI forecasts, news, "
        "evidence, and Decision Report materials. "
        f"{language_instruction}"
    )
    user_prompt = (
        "Minimal context:\n"
        "- assistant_name: SMAIナビ\n"
        "- screen: SMAIアシスタント\n"
        "- role: Smart Market AIの投資判断アシスタント\n"
        f"- intent: {request.task_type}\n"
        f"- user_message: {request.user_question.strip()[:500]}\n\n"
        "This is a lightweight guidance or chat question. "
        "Do not produce materials blocks, cautions blocks, technical explanations, Markdown-save "
        "content, or Decision Report content. "
        "Answer naturally in 2 to 4 sentences without using tools or external material."
    )
    return [
        LlmMessage(role="system", content=system_prompt),
        LlmMessage(role="user", content=user_prompt),
    ]


def _context_answer_user_prompt(request: ContextAnswerRequest) -> str:
    context = request.context
    sections = "\n\n".join(_section_prompt(section) for section in context.sections[:8])
    privacy_notes = "\n".join(f"- {note}" for note in context.privacy_notes[:5])
    constraints = request.constraints
    intent_instruction = _intent_instruction(request.user_question)
    radar_contract = _radar_interpretation_contract(request)
    return (
        f"Task: {request.task}\n"
        f"Question: {request.user_question.strip()}\n"
        f"Intent-specific response guide:\n{intent_instruction}\n"
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
        f"{radar_contract or _default_context_answer_contract()}"
        "Do not include privacy_notes, safety_notes, provider_notes, internal_notes, debug_notes, "
        "provider/raw/debug/source-body wording, or internal implementation notes in any user-facing field. "
        "Do not wrap the JSON in markdown. Do not add fields. Output JSON only."
    )


def _default_context_answer_contract() -> str:
    return (
        "Return only valid JSON with these keys:\n"
        "- answer: concise answer string\n"
        "- materials: array of 1 to 8 strings grounded in the supplied context\n"
        "- cautions: array of 1 to 8 strings, including uncertainty or missing checks when relevant\n"
        "- next_checkpoints: array of 1 to 6 strings\n"
        "- confidence: one of low, medium, high\n"
    )


def _radar_interpretation_contract(request: ContextAnswerRequest) -> str | None:
    if request.response_schema != RADAR_INTERPRETATION_RESPONSE_SCHEMA_VERSION:
        return None
    candidate_id = ""
    for section in request.context.sections:
        if section.section_id == "radar_candidate":
            candidate_id = str(section.summary.get("candidate_id") or "").strip()
            break
    allowed_ids = [item for item in request.referenced_context_ids if item.strip()]
    return (
        "Return only valid JSON with these exact keys:\n"
        f"- schema_version: {RADAR_INTERPRETATION_RESPONSE_SCHEMA_VERSION}\n"
        f"- candidate_id: exactly {candidate_id}\n"
        "- summary: object with text and cited_evidence_ids\n"
        "- positive_materials: array of objects with text and cited_evidence_ids\n"
        "- cautions: array of objects with text and cited_evidence_ids\n"
        "- unknowns: array of objects with text and cited_evidence_ids\n"
        "- next_checkpoints: array of objects with text and cited_evidence_ids\n"
        f"Allowed cited_evidence_ids only: {json.dumps(allowed_ids, ensure_ascii=False)}\n"
        "Rules:\n"
        "- Every text object must cite one or more allowed cited_evidence_ids.\n"
        "- Do not add any symbol, number, date, or factual claim that is absent from the supplied sections.\n"
        "- Do not output answer, materials, next_checkpoints, confidence, Markdown fences, or extra fields.\n"
    )


def _intent_instruction(user_question: str) -> str:
    text = user_question.lower()
    if "intent: app_help" in text:
        return (
            "- Explain SMAI screens and features briefly in 3 to 5 Japanese sentences.\n"
            "- Keep materials and cautions empty unless one short next screen is truly useful.\n"
            "- Do not mention internal specs, provider information, debug logs, or raw fields."
        )
    if "intent: stock_summary" in text:
        return (
            "- Organize the current symbol into materials, cautions, and next checks.\n"
            "- Do not conclude from only one score or forecast.\n"
            "- Mention missing or unconfirmed materials when context is thin."
        )
    if "intent: forecast_risk_compare" in text:
        return (
            "- Compare forecast-side information and risk-side information.\n"
            "- materials should focus on forecast-side observations.\n"
            "- cautions should focus on risk-side observations and uncertainty.\n"
            "- next_checkpoints should include confirmation points for forecast/risk mismatch."
        )
    if "intent: news_materials" in text:
        return (
            "- Organize news, disclosures, and research evidence.\n"
            "- materials should be bullish or supportive materials when present.\n"
            "- cautions should be bearish, weak, stale, or unconfirmed materials.\n"
            "- next_checkpoints should name the sources or freshness checks to review next."
        )
    if "intent: decision_report_draft" in text:
        return (
            "- Draft content suitable for a Decision Report memo.\n"
            "- Cover checked materials, bullish materials, bearish materials, unconfirmed items, "
            "next review, and memo wording.\n"
            "- Keep it as a decision-support note, not a trading instruction."
        )
    if "intent: cockpit_interpretation" in text:
        return (
            "- Organize the current Cockpit information into how to read it before a decision.\n"
            "- materials should focus on supportive or strong points already visible in price, "
            "forecast, Investment Score, Research Evidence, or AI material analysis.\n"
            "- cautions should include weak points, contradictions, uncertainty, stale or missing "
            "materials, and cases where short-term forecast and qualitative materials differ.\n"
            "- next_checkpoints should name what the user should inspect next in the Cockpit.\n"
            "- Do not say buy, sell, hold, strong buy, or strong sell. Do not change scores, "
            "forecasts, rankings, or Investment Score."
        )
    if "intent: free_chat" in text:
        return (
            "- Answer naturally as SMAI Navi.\n"
            "- If the topic is outside SMAI or investment-analysis support, answer briefly and "
            "state that SMAI Navi mainly helps with SMAI and investment-material organization."
        )
    return "- Follow the user question while preserving the safety constraints."


def _section_prompt(section: ContextSection) -> str:
    summary = "\n".join(f"  - {key}: {value}" for key, value in list(section.summary.items())[:8])
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
