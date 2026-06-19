from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import Field

from backend.assistant.context_builder import SMAIAssistantContext
from backend.assistant.tool_registry import get_assistant_action
from backend.core.data_contracts import StrictBaseModel

ASSISTANT_GUIDED_WORKFLOW_SCHEMA_VERSION = "assistant-guided-workflow-v1"
ASSISTANT_GUIDED_WORKFLOW_SAFETY_NOTE = (
    "このフローは確認手順の案内です。最終判断は最新情報も確認して行ってください。"
)

WorkflowStepKind = Literal[
    "navigation",
    "confirmable_action",
    "review",
    "manual_check",
    "not_available",
]
WorkflowStepStatus = Literal[
    "suggested",
    "ready",
    "waiting_confirmation",
    "done",
    "skipped",
    "failed",
    "blocked",
]


class AssistantWorkflowStep(StrictBaseModel):
    step_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    kind: WorkflowStepKind
    action_id: str | None = Field(default=None, min_length=1)
    target_page: str | None = Field(default=None, min_length=1)
    symbol: str | None = Field(default=None, min_length=1)
    requires_confirmation: bool = False
    status: WorkflowStepStatus = "suggested"
    disabled_reason: str | None = Field(default=None, min_length=1)
    result_summary: str | None = Field(default=None, min_length=1)
    followup_hint: str | None = Field(default=None, min_length=1)


class AssistantGuidedWorkflow(StrictBaseModel):
    workflow_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    user_intent: str = Field(min_length=1)
    current_page: str = Field(min_length=1)
    target_symbol: str | None = Field(default=None, min_length=1)
    steps: list[AssistantWorkflowStep] = Field(default_factory=list, max_length=6)
    safety_note: str = ASSISTANT_GUIDED_WORKFLOW_SAFETY_NOTE
    generated_by: Literal["deterministic", "llm", "fallback"] = "deterministic"
    schema_version: str = ASSISTANT_GUIDED_WORKFLOW_SCHEMA_VERSION


def build_deterministic_guided_workflow(
    context: SMAIAssistantContext,
    *,
    max_steps: int = 6,
) -> AssistantGuidedWorkflow | None:
    """Build a deterministic guided workflow without executing any action."""

    intent = _workflow_intent(context)
    if intent == "none":
        return None

    target_symbol = _target_symbol(context)
    if intent == "ranking_deep_dive":
        steps = _ranking_deep_dive_steps(context=context, target_symbol=target_symbol)
        title = "ランキングから深掘りする確認フロー"
        summary = "候補を確認し、気になる銘柄をコックピットで深掘りします。"
    elif intent == "report_creation":
        steps = _report_creation_steps(context=context, target_symbol=target_symbol)
        title = "確認レポートまで進めるフロー"
        summary = "今ある材料を確認し、必要ならAI調査を更新してから確認メモに残します。"
    else:
        steps = _cockpit_deep_dive_steps(context=context, target_symbol=target_symbol)
        title = "この銘柄を詳しく見る確認フロー"
        summary = "価格・予測・根拠資料を順に確認し、必要なら確認レポートに残します。"

    return AssistantGuidedWorkflow(
        title=title,
        summary=summary,
        user_intent=_clean_text(context.user_question) or title,
        current_page=context.current_page,
        target_symbol=target_symbol,
        steps=list(steps[:max_steps]),
    )


def _ranking_deep_dive_steps(
    *,
    context: SMAIAssistantContext,
    target_symbol: str | None,
) -> tuple[AssistantWorkflowStep, ...]:
    return (
        _workflow_step(
            "ranking_candidates",
            title="候補を確認",
            summary="ランキング画面で評価方針と上位候補を確認します。ランキング作成は自動実行しません。",
            kind="navigation",
            action_id="open_ranking",
            target_page="ranking",
            followup_hint="条件を変える場合は、Ranking画面で手動で作成してください。",
        ),
        _workflow_step(
            "open_cockpit",
            title="Cockpitで深掘り",
            summary="気になる銘柄の価格・予測・リスク・根拠資料を同じ画面で確認します。",
            kind="navigation",
            action_id="open_cockpit",
            target_page="cockpit",
            symbol=target_symbol,
        ),
        _research_step(context=context, target_symbol=target_symbol),
        _report_step(target_symbol=target_symbol),
    )


def _cockpit_deep_dive_steps(
    *,
    context: SMAIAssistantContext,
    target_symbol: str | None,
) -> tuple[AssistantWorkflowStep, ...]:
    first_step = (
        _workflow_step(
            "select_symbol",
            title="銘柄を選ぶ",
            summary="まず銘柄コックピットで確認したい銘柄を選びます。",
            kind="navigation",
            action_id="open_cockpit",
            target_page="cockpit",
            followup_hint="価格取得は自動では行いません。",
        )
        if not target_symbol
        else _workflow_step(
            "review_cockpit",
            title="価格・予測を確認",
            summary="選択銘柄の価格、AI予測、下振れ警戒、スコア内訳を確認します。",
            kind="navigation",
            action_id="open_cockpit",
            target_page="cockpit",
            symbol=target_symbol,
        )
    )
    return (
        first_step,
        _research_step(context=context, target_symbol=target_symbol),
        _workflow_step(
            "review_evidence",
            title="根拠資料を確認",
            summary="取得済みのIR・ニュース・開示候補を見て、注意点と未確認材料を整理します。",
            kind="review",
            action_id="open_research_section",
            target_page="cockpit",
            symbol=target_symbol,
        ),
        _report_step(target_symbol=target_symbol),
    )


def _report_creation_steps(
    *,
    context: SMAIAssistantContext,
    target_symbol: str | None,
) -> tuple[AssistantWorkflowStep, ...]:
    return (
        _workflow_step(
            "review_materials",
            title="今ある材料を確認",
            summary="価格・予測・根拠資料・注意点がそろっているか確認します。",
            kind="review",
            action_id="summarize_next_checks",
            symbol=target_symbol,
        ),
        _research_step(context=context, target_symbol=target_symbol),
        _report_step(target_symbol=target_symbol),
        _workflow_step(
            "save_report",
            title="保存導線を確認",
            summary="作成後は既存のMarkdown / ZIP保存導線で確認メモを残します。",
            kind="manual_check",
            action_id="download_decision_report",
            symbol=target_symbol,
            status="suggested",
            followup_hint="レポート作成後に保存ボタンが表示されます。",
        ),
    )


def _research_step(
    *,
    context: SMAIAssistantContext,
    target_symbol: str | None,
) -> AssistantWorkflowStep:
    research_available = not any(
        item == "AI調査 / Research Evidence" for item in context.missing_materials
    )
    summary = (
        "取得済み資料があります。必要なら最新のニュース・開示・IR候補を確認します。"
        if research_available
        else "最新のニュース・開示・IR候補を確認します。実行前に必ず確認します。"
    )
    status: WorkflowStepStatus = "suggested" if research_available else "waiting_confirmation"
    return _workflow_step(
        "update_research",
        title="AI調査を更新",
        summary=summary,
        kind="confirmable_action",
        action_id="update_research",
        symbol=target_symbol,
        requires_confirmation=True,
        status=status,
        followup_hint="この操作だけでは、スコアや予測値は変更されません。",
    )


def _report_step(*, target_symbol: str | None) -> AssistantWorkflowStep:
    return _workflow_step(
        "create_report",
        title="確認レポートを作る",
        summary="あとから見返せる確認メモとして、材料と注意点を整理します。",
        kind="confirmable_action",
        action_id="create_decision_report",
        symbol=target_symbol,
        requires_confirmation=True,
        status="waiting_confirmation",
    )


def _workflow_step(
    step_key: str,
    *,
    title: str,
    summary: str,
    kind: WorkflowStepKind,
    action_id: str | None = None,
    target_page: str | None = None,
    symbol: str | None = None,
    requires_confirmation: bool | None = None,
    status: WorkflowStepStatus | None = None,
    followup_hint: str | None = None,
) -> AssistantWorkflowStep:
    action = get_assistant_action(action_id) if action_id else None
    action_enabled = True if action_id is None else bool(action and action.enabled)
    action_requires_confirmation = action.requires_confirmation if action else False
    confirmation = (
        action_requires_confirmation if requires_confirmation is None else requires_confirmation
    )
    step_status: WorkflowStepStatus = status or (
        "waiting_confirmation" if confirmation else "ready"
    )
    disabled_reason = None
    step_kind = kind
    if not action_enabled:
        step_status = "blocked"
        step_kind = "not_available"
        disabled_reason = "この操作は現在の画面では利用できません。"
    return AssistantWorkflowStep(
        step_id=f"workflow_{step_key}",
        title=title,
        summary=summary,
        kind=step_kind,
        action_id=action_id,
        target_page=target_page,
        symbol=symbol,
        requires_confirmation=confirmation,
        status=step_status,
        disabled_reason=disabled_reason,
        followup_hint=followup_hint,
    )


WorkflowIntent = Literal[
    "ranking_deep_dive",
    "cockpit_deep_dive",
    "report_creation",
    "none",
]


def _workflow_intent(context: SMAIAssistantContext) -> WorkflowIntent:
    question = _clean_text(context.user_question).lower()
    page = context.current_page
    if _contains_any(question, ("ランキング", "上位", "候補", "探したい", "良さそう")):
        return "ranking_deep_dive"
    if _contains_any(question, ("確認レポート", "レポート", "メモ", "見返せる", "残したい")):
        return "report_creation"
    if _contains_any(
        question,
        ("詳しく", "深掘り", "根拠", "この銘柄", "どう見れば", "ai調査", "AI調査"),
    ):
        return "cockpit_deep_dive"
    if page == "ranking" and _contains_any(question, ("確認", "次", "見る")):
        return "ranking_deep_dive"
    if page == "cockpit" and _contains_any(question, ("確認", "次", "見る")):
        return "cockpit_deep_dive"
    return "none"


def _target_symbol(context: SMAIAssistantContext) -> str | None:
    candidates = (
        context.page_state.get("active_symbol"),
        context.page_state.get("selected_symbol"),
        context.page_state.get("symbol"),
        context.material_state.get("symbol"),
    )
    for value in candidates:
        text = _clean_text(value)
        if text:
            return text
    return None


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in value for term in terms)


def _clean_text(value: object) -> str:
    return str(value or "").strip()
