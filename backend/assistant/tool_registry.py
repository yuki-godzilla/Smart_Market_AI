from __future__ import annotations

from typing import Literal, Sequence

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel

AssistantActionType = Literal["navigation", "state_change", "data_fetch", "report", "explain"]


class AssistantActionSpec(StrictBaseModel):
    """Action the Assistant may propose, without executing it in Phase 30-A."""

    action_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    action_type: AssistantActionType
    requires_confirmation: bool = True
    is_destructive: bool = False
    is_external_fetch: bool = False
    enabled: bool = True
    disabled_reason: str | None = Field(default=None, min_length=1)


_ACTION_SPECS: tuple[AssistantActionSpec, ...] = (
    AssistantActionSpec(
        action_id="open_ranking",
        label="ランキングを開く",
        description="銘柄ランキングで候補比較の入口を確認します。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="create_ranking",
        label="ランキングを作成",
        description="現在の条件で比較候補を並べます。",
        action_type="state_change",
        requires_confirmation=True,
    ),
    AssistantActionSpec(
        action_id="change_ranking_policy",
        label="評価方針を見直す",
        description="AI総合、上昇気配、安定性など、目的に合う評価方針を確認します。",
        action_type="state_change",
        requires_confirmation=True,
    ),
    AssistantActionSpec(
        action_id="apply_ranking_filter",
        label="条件で絞り込む",
        description="地域、商品種別、NISA、配当、キーワードなどの条件を確認します。",
        action_type="state_change",
        requires_confirmation=True,
    ),
    AssistantActionSpec(
        action_id="clear_ranking_filters",
        label="条件をクリア",
        description="現在の絞り込み条件を外して候補範囲を広げます。",
        action_type="state_change",
        requires_confirmation=True,
    ),
    AssistantActionSpec(
        action_id="open_symbol_from_ranking",
        label="候補をコックピットで確認",
        description="ランキング上位候補を銘柄コックピットで深掘りします。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="open_cockpit",
        label="銘柄コックピットを開く",
        description="1銘柄の価格、予測、根拠資料、リスクを確認します。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="fetch_symbol_data",
        label="銘柄データを取得",
        description="選択銘柄の価格や特徴量を取得して確認します。",
        action_type="data_fetch",
        requires_confirmation=True,
        is_external_fetch=True,
    ),
    AssistantActionSpec(
        action_id="update_research",
        label="AI調査を更新",
        description="IR、開示、ニュースなどの根拠資料を確認します。",
        action_type="data_fetch",
        requires_confirmation=True,
        is_external_fetch=True,
    ),
    AssistantActionSpec(
        action_id="open_forecast_section",
        label="AI予測を確認",
        description="中心予測、予測レンジ、下振れ警戒、信頼度を確認します。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="open_research_section",
        label="根拠資料を見る",
        description="Research Evidence、IR、ニュース、出典の鮮度を確認します。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="open_ai_interpretation",
        label="AI解釈メモを見る",
        description="強材料、注意材料、未確認材料を分けて確認します。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="create_decision_report",
        label="確認レポートを作る",
        description="確認した材料と未確認項目を判断メモとして整理します。",
        action_type="report",
        requires_confirmation=True,
    ),
    AssistantActionSpec(
        action_id="download_decision_report",
        label="確認レポートを保存",
        description="作成済みの確認レポートをMarkdownやZIPで保存します。",
        action_type="report",
        requires_confirmation=True,
    ),
    AssistantActionSpec(
        action_id="open_news_radar",
        label="投資レーダーを開く",
        description="市場ニュース、カテゴリ別材料、関連銘柄を確認します。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="refresh_news",
        label="投資レーダーを更新",
        description="最新ニュースや市場テーマを取得して確認します。",
        action_type="data_fetch",
        requires_confirmation=True,
        is_external_fetch=True,
    ),
    AssistantActionSpec(
        action_id="open_macro_news",
        label="マクロニュースを見る",
        description="市場全体や政策、金利、為替などの材料を確認します。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="open_symbol_related_news",
        label="関連銘柄ニュースを見る",
        description="気になる銘柄に関係するニュースを確認します。",
        action_type="navigation",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="explain_current_page",
        label="この画面の見方",
        description="現在画面で最初に見る材料と注意点を整理します。",
        action_type="explain",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="explain_ranking_policy",
        label="評価方針を説明",
        description="ランキング評価方針の意味と読み方を整理します。",
        action_type="explain",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="explain_forecast",
        label="予測の見方を説明",
        description="AI予測インサイトと下振れ警戒の読み方を整理します。",
        action_type="explain",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="explain_research_status",
        label="根拠資料の状態を説明",
        description="取得済み資料、未取得資料、鮮度の注意点を整理します。",
        action_type="explain",
        requires_confirmation=False,
    ),
    AssistantActionSpec(
        action_id="summarize_next_checks",
        label="次の確認を整理",
        description="いまの画面から次に確認すべき順番を短く整理します。",
        action_type="explain",
        requires_confirmation=False,
    ),
)


def assistant_action_catalog() -> tuple[AssistantActionSpec, ...]:
    return _ACTION_SPECS


def assistant_action_registry() -> dict[str, AssistantActionSpec]:
    return {action.action_id: action for action in _ACTION_SPECS}


def get_assistant_action(action_id: str) -> AssistantActionSpec | None:
    return assistant_action_registry().get(action_id)


def assistant_actions_for_page(current_page: str) -> tuple[AssistantActionSpec, ...]:
    page = str(current_page or "unknown").strip().lower()
    ids_by_page = {
        "ranking": (
            "explain_current_page",
            "explain_ranking_policy",
            "change_ranking_policy",
            "apply_ranking_filter",
            "create_ranking",
            "open_symbol_from_ranking",
            "open_cockpit",
            "summarize_next_checks",
        ),
        "cockpit": (
            "explain_current_page",
            "fetch_symbol_data",
            "open_forecast_section",
            "open_ai_interpretation",
            "open_research_section",
            "update_research",
            "create_decision_report",
            "summarize_next_checks",
        ),
        "news": (
            "explain_current_page",
            "refresh_news",
            "open_macro_news",
            "open_symbol_related_news",
            "open_cockpit",
            "summarize_next_checks",
        ),
        "rebalance": (
            "explain_current_page",
            "create_decision_report",
            "summarize_next_checks",
        ),
        "assistant": (
            "explain_current_page",
            "open_ranking",
            "open_cockpit",
            "open_news_radar",
            "summarize_next_checks",
        ),
    }
    wanted = ids_by_page.get(page, ("explain_current_page", "summarize_next_checks"))
    registry = assistant_action_registry()
    return tuple(registry[action_id] for action_id in wanted if action_id in registry)


def action_ids(actions: Sequence[AssistantActionSpec]) -> set[str]:
    return {action.action_id for action in actions}
