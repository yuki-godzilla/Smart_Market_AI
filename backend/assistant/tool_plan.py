from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from pydantic import Field

from backend.assistant.context_builder import SMAIAssistantContext
from backend.assistant.conversation_mode import (
    AssistantConversationModeDecision,
    AssistantResearchIntent,
    route_assistant_conversation_mode,
)
from backend.assistant.tool_registry import get_assistant_action
from backend.core.data_contracts import StrictBaseModel

ASSISTANT_TOOL_PLAN_SCHEMA_VERSION = "assistant-tool-plan-v1"
ASSISTANT_TOOL_PLAN_PROMPT_VERSION = "assistant_tool_plan_mvp.v1"
ASSISTANT_TOOL_PLAN_SAFETY_NOTE = (
    "この提案はSMAI上で確認すべき操作の整理です。売買推奨ではありません。"
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
    company_name: str | None
    requires_approval: bool
    approval_reason: str
    tools: tuple[AssistantResearchTool, ...]

    @property
    def has_external_tools(self) -> bool:
        return any(tool.external for tool in self.tools)


class AssistantToolPlanStep(StrictBaseModel):
    step_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    action_id: str | None = Field(default=None, min_length=1)
    reason: str = Field(min_length=1)
    requires_confirmation: bool = True
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["suggested", "blocked", "ready", "done"] = "suggested"
    disabled_reason: str | None = Field(default=None, min_length=1)


class AssistantToolPlan(StrictBaseModel):
    plan_id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    user_intent: str = Field(min_length=1)
    current_page: str = Field(min_length=1)
    overall_summary: str = Field(min_length=1)
    steps: list[AssistantToolPlanStep] = Field(default_factory=list, max_length=5)
    missing_materials: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety_note: str = ASSISTANT_TOOL_PLAN_SAFETY_NOTE
    generated_by: Literal["deterministic", "llm", "fallback"] = "deterministic"
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    prompt_version: str = ASSISTANT_TOOL_PLAN_PROMPT_VERSION
    schema_version: str = ASSISTANT_TOOL_PLAN_SCHEMA_VERSION


def build_deterministic_assistant_tool_plan(
    context: SMAIAssistantContext,
    *,
    max_steps: int = 5,
) -> AssistantToolPlan:
    """Build a safe read-only proposal plan from the current SMAI page context."""

    steps = _steps_for_context(context)[:max_steps]
    if not steps:
        steps = (
            _step(
                "current_page",
                title="この画面の見方を確認",
                summary="現在画面で最初に見る材料と不足材料を整理します。",
                action_id="explain_current_page",
                reason="画面状態が不足していても、安全な確認順を示せるためです。",
                priority="medium",
            ),
        )
    return AssistantToolPlan(
        user_intent=_user_intent(context),
        current_page=context.current_page,
        overall_summary=_overall_summary(context),
        steps=list(steps),
        missing_materials=context.missing_materials[:5],
        warnings=context.warnings[:5],
    )


def _steps_for_context(context: SMAIAssistantContext) -> tuple[AssistantToolPlanStep, ...]:
    page = context.current_page
    question = str(context.user_question or "").lower()
    if page == "ranking":
        return _ranking_steps(context, question)
    if page == "cockpit":
        return _cockpit_steps(context)
    if page == "news":
        return _news_steps(context)
    if page == "rebalance":
        return (
            _step(
                "rebalance_review",
                title="配分のズレを確認",
                summary="現在比率、目標比率、ズレ幅、リスク警告を順に確認します。",
                action_id="explain_current_page",
                reason="リバランスは提案取引の前に、配分差と注意点を分けて読む必要があります。",
                priority="high",
                requires_confirmation=False,
            ),
            _step(
                "rebalance_report",
                title="確認レポートに残す",
                summary="配分見直しの材料を判断メモとして整理します。",
                action_id="create_decision_report",
                reason="後で見返せる形にすると、取引指示と確認メモを分けやすくなります。",
                priority="medium",
            ),
        )
    if page == "assistant":
        return (
            _step(
                "choose_workflow",
                title="確認したい画面を選ぶ",
                summary="ランキング、コックピット、投資レーダーのどこから見るかを決めます。",
                action_id="summarize_next_checks",
                reason="質問の目的に合わせて、最初に開く画面を分けると確認が進めやすくなります。",
                priority="high",
                requires_confirmation=False,
            ),
            _step(
                "open_ranking",
                title="候補探しならランキングへ",
                summary="条件に合う銘柄候補を比較する入口としてランキングを使います。",
                action_id="open_ranking",
                reason="複数候補を比べたい相談では、ランキングが最初の整理に向いています。",
                priority="medium",
                requires_confirmation=False,
            ),
            _step(
                "open_cockpit",
                title="1銘柄の深掘りならコックピットへ",
                summary="価格、予測、根拠資料、確認レポートを1銘柄で確認します。",
                action_id="open_cockpit",
                reason="特定銘柄の相談では、材料を同じ画面でそろえる方が安全です。",
                priority="medium",
                requires_confirmation=False,
            ),
        )
    return ()


def _ranking_steps(
    context: SMAIAssistantContext,
    question: str,
) -> tuple[AssistantToolPlanStep, ...]:
    steps: list[AssistantToolPlanStep] = []
    if any(term in question for term in ("上がり", "探", "候補", "ランキング", "成長")):
        steps.append(
            _step(
                "ranking_policy",
                title="評価方針を目的に合わせる",
                summary="AI総合、小型・成長探索、上昇気配重視などの方針を確認します。",
                action_id="change_ranking_policy",
                reason="候補探しでは、評価方針によって上位に出る理由が変わるためです。",
                priority="high",
            )
        )
    else:
        steps.append(
            _step(
                "ranking_scope",
                title="ランキング条件を確認",
                summary="対象地域、商品種別、取得期間、絞り込み条件を確認します。",
                action_id="apply_ranking_filter",
                reason="比較対象が目的とズレると、順位の意味も変わります。",
                priority="high",
            )
        )
    steps.extend(
        [
            _step(
                "create_ranking",
                title="ランキングを作成",
                summary="現在条件で候補を並べ、上位候補と注意材料を見ます。",
                action_id="create_ranking",
                reason="順位は投資対象の確定ではなく、深掘り候補の確認順として使います。",
                priority="high",
            ),
            _step(
                "open_top_symbol",
                title="上位候補をコックピットで確認",
                summary="気になる候補の価格、予測、リスク、根拠資料を深掘りします。",
                action_id="open_symbol_from_ranking",
                reason="ランキングだけで結論にせず、1銘柄画面で材料をそろえるためです。",
                priority="medium",
                requires_confirmation=False,
            ),
        ]
    )
    if "AI調査 / Research Evidence" in context.missing_materials:
        steps.append(_research_update_step(priority="medium"))
    return tuple(steps)


def _cockpit_steps(context: SMAIAssistantContext) -> tuple[AssistantToolPlanStep, ...]:
    steps: list[AssistantToolPlanStep] = []
    if "価格データ" in context.missing_materials:
        steps.append(
            _step(
                "fetch_symbol_data",
                title="価格データを取得",
                summary="選択銘柄の価格と特徴量を確認できる状態にします。",
                action_id="fetch_symbol_data",
                reason="価格データがないと、予測やリスクの読み方をそろえにくいためです。",
                priority="high",
            )
        )
    else:
        steps.append(
            _step(
                "check_forecast",
                title="価格とAI予測を確認",
                summary="価格チャート、中心予測、予測レンジ、下振れ警戒を見ます。",
                action_id="open_forecast_section",
                reason="まず定量材料をそろえて、上向き材料と注意材料を分けるためです。",
                priority="high",
                requires_confirmation=False,
            )
        )
    steps.append(
        _step(
            "check_interpretation",
            title="AI解釈メモを確認",
            summary="強材料、注意材料、未確認材料を短く整理します。",
            action_id="open_ai_interpretation",
            reason="予測値だけでなく、材料の向きと不足を分けて確認するためです。",
            priority="medium",
            requires_confirmation=False,
        )
    )
    if "AI調査 / Research Evidence" in context.missing_materials:
        steps.append(_research_update_step(priority="high"))
    else:
        steps.append(
            _step(
                "open_research",
                title="根拠資料を確認",
                summary="IR、ニュース、Research Evidenceの出典と鮮度を確認します。",
                action_id="open_research_section",
                reason="資料の有無と鮮度を確認して、未確認材料を残すためです。",
                priority="medium",
                requires_confirmation=False,
            )
        )
    steps.append(
        _step(
            "create_report",
            title="確認レポートを作る",
            summary="確認済み材料、注意点、未確認事項を判断メモとして整理します。",
            action_id="create_decision_report",
            reason="後から見返せる形にすると、確認材料と判断を分けやすくなります。",
            priority="low",
        )
    )
    return tuple(steps)


def _news_steps(context: SMAIAssistantContext) -> tuple[AssistantToolPlanStep, ...]:
    first = (
        _step(
            "refresh_news",
            title="投資レーダーを更新",
            summary="最新ニュースと市場テーマを確認します。",
            action_id="refresh_news",
            reason="ニュースは鮮度が重要なため、必要なら更新前提で確認します。",
            priority="high",
        )
        if "投資レーダーのニュース" in context.missing_materials
        else _step(
            "open_macro_news",
            title="市場全体の材料を見る",
            summary="マクロ、政策、決算、セクター材料を分けて確認します。",
            action_id="open_macro_news",
            reason="個別銘柄を見る前に、市場全体のテーマをつかむためです。",
            priority="high",
            requires_confirmation=False,
        )
    )
    return (
        first,
        _step(
            "related_news",
            title="関連銘柄のニュースを見る",
            summary="ニュース本文に出た銘柄とSMAI推測候補を分けて確認します。",
            action_id="open_symbol_related_news",
            reason="関連候補は深掘り入口であり、ニュースだけで結論にしないためです。",
            priority="medium",
            requires_confirmation=False,
        ),
        _step(
            "open_cockpit_from_news",
            title="気になる銘柄をコックピットで確認",
            summary="価格、予測、根拠資料を同じ銘柄で確認します。",
            action_id="open_cockpit",
            reason="ニュース材料を、定量材料や根拠資料と合わせて読むためです。",
            priority="medium",
            requires_confirmation=False,
        ),
    )


def _research_update_step(
    *,
    priority: Literal["high", "medium", "low"],
) -> AssistantToolPlanStep:
    return _step(
        "update_research",
        title="AI調査を更新",
        summary="IR、開示、ニュースなどの根拠資料を確認します。",
        action_id="update_research",
        reason="根拠資料が未取得の場合、出典と鮮度を確認してから読みを補強するためです。",
        priority=priority,
    )


def _step(
    step_key: str,
    *,
    title: str,
    summary: str,
    action_id: str,
    reason: str,
    priority: Literal["high", "medium", "low"],
    requires_confirmation: bool | None = None,
) -> AssistantToolPlanStep:
    action = get_assistant_action(action_id)
    action_requires_confirmation = action.requires_confirmation if action else True
    action_enabled = action.enabled if action else False
    return AssistantToolPlanStep(
        step_id=f"step_{step_key}",
        title=title,
        summary=summary,
        action_id=action_id,
        reason=reason,
        requires_confirmation=(
            action_requires_confirmation
            if requires_confirmation is None
            else requires_confirmation or action_requires_confirmation
        ),
        priority=priority,
        status="suggested" if action_enabled else "blocked",
        disabled_reason=None if action_enabled else "この操作は現在の画面では利用できません。",
    )


def _user_intent(context: SMAIAssistantContext) -> str:
    return str(context.user_question or "現在画面で次に確認することを整理する").strip()


def _overall_summary(context: SMAIAssistantContext) -> str:
    if context.summary:
        return context.summary
    return "現在画面と取得済み材料をもとに、次の確認順を提案します。"


def build_assistant_research_tool_plan(
    user_question: str,
    decision: AssistantConversationModeDecision | None = None,
) -> AssistantResearchToolPlan | None:
    decision = decision or route_assistant_conversation_mode(user_question)
    if decision.conversation_mode != "research_plan":
        return None

    symbol_query = decision.symbol_query
    symbol = _symbol_for_query(symbol_query)
    company_name = _company_name_for_symbol_or_query(symbol=symbol, symbol_query=symbol_query)
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
        company_name=company_name,
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
                label="銘柄を特定",
                reason="入力された銘柄名から、対象銘柄を確認します。",
                external=False,
                required=True,
            ),
            AssistantResearchTool(
                name="price_fetch",
                label="価格の動き",
                reason="直近の価格推移や変動を確認します。",
                external=True,
                required=True,
            ),
            AssistantResearchTool(
                name="forecast_fetch",
                label="AI予測・下振れ警戒",
                reason="AI予測の方向感と、下振れリスクを確認します。",
                external=False,
                required=True,
            ),
            AssistantResearchTool(
                name="news_fetch",
                label="最新ニュース",
                reason="直近ニュースや開示材料を確認します。",
                external=True,
                required=False,
            ),
            AssistantResearchTool(
                name="research_fetch",
                label="根拠資料 / Research Evidence",
                reason="根拠資料や外部参照ソースを確認します。",
                external=True,
                required=False,
            ),
        )
    if intent in {"news_research", "investment_material_scan"}:
        return (
            AssistantResearchTool(
                name="news_fetch",
                label="最新ニュース",
                reason="直近ニュースや開示材料を確認します。",
                external=True,
                required=True,
            ),
            AssistantResearchTool(
                name="research_fetch",
                label="根拠資料 / Research Evidence",
                reason="根拠資料や外部参照ソースを確認します。",
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
        return "最新のニュース・開示・IR候補を確認するため、実行前に確認します。"
    return "SMAI内の材料を確認して整理するため、実行前に確認します。"


def _symbol_for_query(symbol_query: str | None) -> str | None:
    if not symbol_query:
        return None
    aliases = {
        "トヨタ": "7203.T",
        "toyota": "7203.T",
        "ソニー": "6758.T",
        "sony": "6758.T",
        "任天堂": "7974.T",
        "ntt": "9432.T",
        "三菱ufj": "8306.T",
        "三菱商事": "8058.T",
        "大阪ガス": "9532.T",
        "nvidia": "NVDA",
        "microsoft": "MSFT",
        "apple": "AAPL",
        "tesla": "TSLA",
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


def _company_name_for_symbol_or_query(
    *,
    symbol: str | None,
    symbol_query: str | None,
) -> str | None:
    aliases = {
        "7203.T": "トヨタ自動車",
        "6758.T": "ソニーグループ",
        "7974.T": "任天堂",
        "9432.T": "日本電信電話",
        "8306.T": "三菱UFJフィナンシャル・グループ",
        "8058.T": "三菱商事",
        "9532.T": "大阪ガス",
        "NVDA": "NVIDIA",
        "MSFT": "Microsoft",
        "AAPL": "Apple",
        "TSLA": "Tesla",
        "トヨタ": "トヨタ自動車",
        "toyota": "トヨタ自動車",
        "ソニー": "ソニーグループ",
        "sony": "ソニーグループ",
        "任天堂": "任天堂",
        "ntt": "日本電信電話",
        "三菱ufj": "三菱UFJフィナンシャル・グループ",
        "三菱商事": "三菱商事",
        "大阪ガス": "大阪ガス",
        "nvidia": "NVIDIA",
        "microsoft": "Microsoft",
        "apple": "Apple",
        "tesla": "Tesla",
    }
    if symbol and symbol in aliases:
        return aliases[symbol]
    query = str(symbol_query or "").strip()
    if query and query.lower() in aliases:
        return aliases[query.lower()]
    if query and query in aliases:
        return aliases[query]
    return None
