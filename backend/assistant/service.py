from __future__ import annotations

from typing import Literal, Sequence

from pydantic import Field

from backend.core.data_contracts import StrictBaseModel
from backend.reporting import (
    DECISION_SUPPORT_NOTE,
    DecisionReportContext,
    DecisionReportSection,
)

ASSISTANT_SCHEMA_VERSION = "assistant-response-v1"

AssistantIntent = Literal[
    "overview",
    "score",
    "forecast",
    "direction",
    "ranking",
    "risk",
    "research",
    "next_steps",
    "advice_boundary",
    "unknown",
]
AssistantGatewayTaskType = Literal[
    "free_chat",
    "app_help",
    "stock_summary",
    "forecast_risk_compare",
    "news_materials",
    "rag_summary",
    "decision_report_draft",
    "llm_factor_generation",
    "report_export_summary",
]


class AssistantMessage(StrictBaseModel):
    """Optional chat history item for future Gateway-backed assistant sessions."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class AssistantCitation(StrictBaseModel):
    """Report section reference used by the deterministic assistant response."""

    section_title: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    symbol: str | None = Field(default=None, min_length=1)


class AssistantRequest(StrictBaseModel):
    """Local-first assistant request built from existing report/research context."""

    question: str = Field(min_length=1)
    report_context: DecisionReportContext | None = None
    max_points: int = Field(default=4, ge=1, le=8)
    conversation_id: str | None = Field(default=None, min_length=1)
    message_history: list[AssistantMessage] = Field(default_factory=list)
    active_context_id: str | None = Field(default=None, min_length=1)
    referenced_context_ids: list[str] = Field(default_factory=list)
    gateway_task_type: AssistantGatewayTaskType = "free_chat"


class AssistantResponse(StrictBaseModel):
    """Deterministic assistant answer with explicit non-advice boundaries."""

    schema_version: str = ASSISTANT_SCHEMA_VERSION
    intent: AssistantIntent
    answer: str = Field(min_length=1)
    reasons: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    next_checkpoints: list[str] = Field(default_factory=list)
    citations: list[AssistantCitation] = Field(default_factory=list)
    response_source: Literal[
        "deterministic",
        "llm",
        "deterministic_fallback",
        "gateway",
        "fallback",
    ] = "deterministic"
    model: str | None = Field(default=None, min_length=1)
    provider: str | None = Field(default=None, min_length=1)
    profile: str | None = Field(default=None, min_length=1)
    latency_ms: int | None = Field(default=None, ge=0)
    gateway_status: str | None = Field(default=None, min_length=1)
    fallback_reason: str | None = Field(default=None, min_length=1)
    request_id: str | None = Field(default=None, min_length=1)
    timeout_sec: float | None = Field(default=None, ge=0)
    context_tokens_estimate: int | None = Field(default=None, ge=0)
    prompt_chars: int | None = Field(default=None, ge=0)
    response_chars: int | None = Field(default=None, ge=0)
    tool_execution_ms: int | None = Field(default=None, ge=0)
    llm_generation_ms: int | None = Field(default=None, ge=0)
    total_elapsed_ms: int | None = Field(default=None, ge=0)
    decision_support_note: str = DECISION_SUPPORT_NOTE


class TemplateAssistantService:
    """Network-free assistant that explains existing SMAI context with templates."""

    def answer(self, request: AssistantRequest) -> AssistantResponse:
        question = request.question.strip()
        intent = _detect_intent(question)
        sections = _select_sections(request.report_context, intent)
        reasons = _collect_reasons(sections, intent, question, request.max_points)
        cautions = _collect_cautions(sections, intent, question, request.max_points)
        next_checkpoints = _build_next_checkpoints(
            sections,
            intent,
            question,
            request.max_points,
        )
        citations = [_citation_from_section(section) for section in sections[: request.max_points]]

        if request.report_context is None:
            cautions = _dedupe(
                [
                    "投資判断レポートや根拠資料が未指定のため、回答は一般的な確認順に限定します。",
                    *cautions,
                ]
            )
            next_checkpoints = _dedupe(
                [
                    "銘柄コックピットまたはランキングで投資判断レポートを作成してから、同じ質問を確認します。",
                    *next_checkpoints,
                ]
            )

        return AssistantResponse(
            intent=intent,
            answer=_build_answer(question, intent, sections, bool(request.report_context)),
            reasons=reasons,
            cautions=cautions,
            next_checkpoints=next_checkpoints,
            citations=citations,
        )


def _detect_intent(question: str) -> AssistantIntent:
    normalized = question.lower()
    if any(term in normalized for term in ("買", "売", "buy", "sell", "hold", "保有")):
        return "advice_boundary"
    if any(
        term in normalized
        for term in (
            "ai予測",
            "予測インサイト",
            "中心予測",
            "下振れ",
            "上振れ",
            "forecast",
            "予測",
            "モデル",
        )
    ):
        return "forecast"
    if any(term in normalized for term in ("上昇気配", "下降警戒", "方向", "シグナル", "signal")):
        return "direction"
    if any(term in normalized for term in ("ランキング", "順位", "上位", "候補", "深掘り", "比較")):
        return "ranking"
    if any(term in normalized for term in ("research", "根拠", "資料", "ニュース", "ir", "開示")):
        return "research"
    if any(term in normalized for term in ("risk", "リスク", "注意", "警戒", "下落")):
        return "risk"
    if any(term in normalized for term in ("score", "スコア", "評価", "順位", "ランキング")):
        return "score"
    if any(
        term in normalized
        for term in (
            "次",
            "確認",
            "どう見る",
            "どう読む",
            "どう選ぶ",
            "どう決める",
            "何を見る",
            "何に使う",
            "まず見る",
            "まずどの",
            "見る点",
            "使い方",
            "取得期間",
            "データ取得元",
            "キャッシュ",
            "関連銘柄",
            "ズレ",
            "提案取引",
            "目標比率",
            "現在比率",
            "配分",
        )
    ):
        return "next_steps"
    if any(term in normalized for term in ("概要", "要約", "まとめ", "summary")):
        return "overview"
    return "unknown"


def _select_sections(
    report_context: DecisionReportContext | None,
    intent: AssistantIntent,
) -> list[DecisionReportSection]:
    if report_context is None:
        return []

    keywords_by_intent: dict[AssistantIntent, tuple[str, ...]] = {
        "overview": (),
        "score": ("score", "スコア", "screening", "ranking", "investment"),
        "forecast": (
            "forecast",
            "予測",
            "ai予測",
            "中心予測",
            "下振れ",
            "上振れ",
            "model",
            "モデル",
        ),
        "direction": (
            "上昇気配",
            "下降警戒",
            "direction",
            "signal",
            "シグナル",
            "警戒",
        ),
        "ranking": ("ranking", "ランキング", "順位", "候補", "深掘り", "比較", "score"),
        "risk": ("risk", "リスク", "warning", "注意", "警戒", "breach"),
        "research": ("research", "根拠", "資料", "news", "ニュース", "ir", "開示"),
        "next_steps": ("checkpoint", "確認", "memo", "メモ", "risk", "research"),
        "advice_boundary": ("score", "risk", "research", "checkpoint", "確認"),
        "unknown": (),
    }
    keywords = keywords_by_intent[intent]
    if not keywords:
        return list(report_context.sections)

    matched = [
        section
        for section in report_context.sections
        if _section_matches_keywords(section, keywords)
    ]
    return matched or list(report_context.sections)


def _section_matches_keywords(
    section: DecisionReportSection,
    keywords: Sequence[str],
) -> bool:
    haystack = " ".join(
        [
            section.title,
            section.source.kind,
            *section.summary.keys(),
            *section.summary.values(),
            *section.warnings,
            *section.notes,
            *[value for row in section.rows for value in row.values()],
        ]
    ).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _build_answer(
    question: str,
    intent: AssistantIntent,
    sections: Sequence[DecisionReportSection],
    has_context: bool,
) -> str:
    if intent == "advice_boundary":
        return (
            "この質問には、買う・売る・保有するといった指示では答えません。"
            "SMAI Assistant は、手元のスコア、リスク、根拠資料を整理し、"
            "判断前に確認する観点を示します。"
        )
    if not has_context:
        return (
            "まだ具体的な分析コンテキストがないため、一般的な確認順を案内します。"
            "価格データ、スコア内訳、リスク、根拠資料を同じ銘柄でそろえて確認してください。"
        )

    section_phrase = _format_section_phrase(sections)
    context_hint = _context_hint(sections)
    focused_answer = _focused_answer(question, context_hint, section_phrase)
    if focused_answer:
        return focused_answer
    if intent == "score":
        if context_hint == "ranking":
            return (
                f"{section_phrase}では、評価方針を深掘りしたい目的として選びます。"
                "順位は候補の確認順であり、上位理由、下降警戒、データ信頼度を合わせて見ます。"
            )
        return f"{section_phrase}から、スコアは候補比較の入口として読みます。単独の売買判断ではなく、内訳と警告を合わせて確認します。"
    if intent == "forecast":
        return (
            f"{section_phrase}から、予測は中心予測、下振れ、上振れ、信頼度の順に読みます。"
            "将来の保証ではなく、モデル間の見方と不確実性を整理する材料です。"
        )
    if intent == "direction":
        return (
            f"{section_phrase}から、上昇気配と下降警戒を分けて確認します。"
            "どちらか一方を結論にせず、価格トレンド、AI予測インサイト、データ信頼度を合わせて見ます。"
        )
    if intent == "ranking":
        return (
            f"{section_phrase}から、順位は深掘り候補の並びとして読みます。"
            "上位候補ほど先に確認しやすい一方で、下降警戒やデータ不足があれば読みを控えめにします。"
        )
    if intent == "risk":
        return f"{section_phrase}から、注意材料とデータ不足を先に確認します。リスク表示は安全保証ではなく、追加確認の優先度を示す材料です。"
    if intent == "research":
        if context_hint == "news":
            return (
                f"{section_phrase}では、ニュースの流れ、カテゴリ、関連銘柄、"
                "出典と鮮度を分けて確認します。関連銘柄は深掘り入口であり、"
                "ニュースだけで結論にしません。"
            )
        if context_hint == "settings":
            return (
                f"{section_phrase}では、ローカル資料を根拠表示やレポート補助に使います。"
                "資料の鮮度、出典、対象銘柄との関係を確認してから参照します。"
            )
        return f"{section_phrase}から、根拠資料・ニュース・開示の出典と鮮度を確認します。資料で読める範囲と未確認項目を分けて扱います。"
    if intent == "next_steps":
        if context_hint == "news":
            return (
                f"{section_phrase}をもとに、まずニュースの流れ、カテゴリ別材料、"
                "関連銘柄、出典と鮮度の順に確認します。"
            )
        if context_hint == "rebalance":
            return (
                f"{section_phrase}をもとに、まず現在比率と目標比率のズレ、"
                "提案取引、リスク警告、実行前の確認点を順に見ます。"
            )
        if context_hint == "settings":
            return (
                f"{section_phrase}をもとに、まずデータ取得元、ローカル資料、"
                "キャッシュや更新状態を確認します。"
            )
        if context_hint == "ranking":
            return (
                f"{section_phrase}をもとに、まず評価方針、上位候補、"
                "下降警戒、データ信頼度、AI予測インサイトを見比べます。"
            )
        return f"{section_phrase}をもとに、次は不足データ、スコア内訳、リスク、根拠資料の順に確認します。"
    if intent == "overview":
        return f"{section_phrase}を要約すると、現在の分析結果は比較材料、注意材料、追加確認点に分けて読むのが安全です。"
    if context_hint == "news":
        return (
            f"{section_phrase}を参照し、ニュースで分かる材料、関連銘柄、"
            "未確認の公式情報を分けて整理します。"
        )
    if context_hint == "rebalance":
        return (
            f"{section_phrase}を参照し、配分のズレ、提案取引、"
            "リスク警告、実行前に確認する点を分けて整理します。"
        )
    if context_hint == "settings":
        return (
            f"{section_phrase}を参照し、データ取得元、ローカル資料、"
            "キャッシュ状態、更新が必要な項目を分けて整理します。"
        )
    if context_hint == "ranking":
        return (
            f"{section_phrase}を参照し、評価方針、比較対象、"
            "上位候補、注意材料を分けて整理します。"
        )
    return f"{section_phrase}を参照し、分かっている材料と未確認の材料を分けて整理します。"


def _format_section_phrase(sections: Sequence[DecisionReportSection]) -> str:
    if not sections:
        return "投資判断レポート"
    titles = [section.title for section in sections[:3]]
    if len(sections) > 3:
        titles.append("ほか")
    return " / ".join(titles)


def _context_hint(sections: Sequence[DecisionReportSection]) -> str:
    parts: list[str] = []
    for section in sections:
        parts.extend(
            [
                section.title,
                section.source.kind,
                *section.summary.keys(),
                *section.summary.values(),
                *section.notes,
            ]
        )
    haystack = " ".join(parts).lower()
    if any(term in haystack for term in ("投資レーダー", "ニュース")):
        return "news"
    if any(term in haystack for term in ("リバランス", "配分", "目標比率")):
        return "rebalance"
    if any(term in haystack for term in ("設定", "データ取得元", "キャッシュ", "settings")):
        return "settings"
    if any(term in haystack for term in ("ランキング", "順位", "候補")):
        return "ranking"
    if any(term in haystack for term in ("銘柄コックピット", "cockpit", "価格・予測")):
        return "cockpit"
    if len(sections) != 1:
        return ""
    source_kind = sections[0].source.kind
    if source_kind == "cockpit":
        return "cockpit"
    if source_kind == "rebalance":
        return "rebalance"
    if source_kind == "ranking":
        return "ranking"
    return ""


def _question_focus(question: str, context_hint: str) -> str:
    normalized = question.lower()

    def has(*terms: str) -> bool:
        return any(term.lower() in normalized for term in terms)

    if context_hint == "news":
        if has("関連銘柄", "関連"):
            return "news_related"
        if has("出典", "鮮度", "ソース", "公開", "公式"):
            return "news_source"
        if has("ニュース", "どこ", "流れ", "まず", "見る"):
            return "news_flow"
    if context_hint == "ranking":
        if has("低信頼", "信頼", "データ"):
            return "ranking_confidence"
        if has("ai総合", "上昇気配", "下降警戒", "読み分け", "違い"):
            return "ranking_signals"
        if has("深掘り", "比較", "比べ"):
            return "ranking_compare"
        if has("対象", "期間", "作成", "何銘柄"):
            return "ranking_scope"
        if has("上位", "候補", "なぜ", "理由"):
            return "ranking_reason"
    if context_hint == "rebalance":
        if has("提案取引", "取引", "売却", "買付", "売買"):
            return "rebalance_trade"
        if has("リスク", "警告", "注意"):
            return "rebalance_risk"
        if has("ズレ", "現在比率", "目標比率", "配分", "まず"):
            return "rebalance_drift"
    if context_hint == "settings":
        if has("取得元", "provider", "yahoo", "mock", "csv"):
            return "settings_provider"
        if has("ローカル資料", "資料", "根拠", "レポート"):
            return "settings_documents"
        if has("キャッシュ", "更新", "古い"):
            return "settings_cache"
    if context_hint == "cockpit":
        if has("予測", "ai予測", "中心予測", "下振れ", "上振れ"):
            return "cockpit_forecast"
        if has("上昇気配", "下降警戒", "方向"):
            return "cockpit_direction"
        if has("decision", "report", "残す", "確認ポイント"):
            return "cockpit_report"
        if has("まず", "見る", "銘柄"):
            return "cockpit_first"
    return ""


def _focused_answer(question: str, context_hint: str, section_phrase: str) -> str:
    focus = _question_focus(question, context_hint)
    answers = {
        "news_flow": (
            f"{section_phrase}では、まずニュースの流れをつかみ、"
            "カテゴリ別材料で論点を分け、気になる銘柄だけ深掘りします。"
        ),
        "news_related": (
            f"{section_phrase}では、関連銘柄を「本文で直接出た銘柄」と"
            "「テーマから広がる候補」に分けて読みます。ニュース反応の入口であり、"
            "銘柄単体の結論ではありません。"
        ),
        "news_source": (
            f"{section_phrase}では、出典、公開日、公式性、更新の新しさを見て、"
            "ニュースをどれくらい重く扱うかを決めます。"
        ),
        "ranking_reason": (
            f"{section_phrase}では、上位理由をAI総合、上昇気配、下降警戒、"
            "データ信頼度の組み合わせで読みます。順位は確認順です。"
        ),
        "ranking_compare": (
            f"{section_phrase}では、深掘り候補を同じ評価軸で横並びにし、"
            "強み、弱み、不確実性の違いを見ます。"
        ),
        "ranking_signals": (
            f"{section_phrase}では、AI総合を入口、上昇気配を上向き材料、"
            "下降警戒をブレーキ材料として分けて読みます。"
        ),
        "ranking_confidence": (
            f"{section_phrase}では、低信頼データは順位の確定材料ではなく、"
            "追加確認が必要な候補として扱います。"
        ),
        "ranking_scope": (
            f"{section_phrase}では、ランキングの作成対象、取得期間、"
            "評価方針が目的に合っているかを先に確認します。"
        ),
        "rebalance_drift": (
            f"{section_phrase}では、現在比率と目標比率のズレが大きい順に見て、"
            "調整が必要そうな箇所を絞ります。"
        ),
        "rebalance_trade": (
            f"{section_phrase}では、提案取引をそのまま実行案にせず、"
            "金額、比率の変化、コスト、実行タイミングを分けて確認します。"
        ),
        "rebalance_risk": (
            f"{section_phrase}では、リスク警告を先に読み、"
            "配分変更で別の偏りが増えないかを確認します。"
        ),
        "settings_provider": (
            f"{section_phrase}では、データ取得元を用途で選びます。"
            "通常確認はlocal/mock、ライブ確認はyahoo、手元データはCSVを使います。"
        ),
        "settings_documents": (
            f"{section_phrase}では、ローカル資料を根拠表示とDecision Reportの補助に使います。"
            "出典、対象銘柄、資料の新しさを合わせて確認します。"
        ),
        "settings_cache": (
            f"{section_phrase}では、キャッシュの最終更新、欠損、古さを見て、"
            "再取得が必要かを判断します。"
        ),
        "cockpit_first": (
            f"{section_phrase}では、価格の流れ、AI予測インサイト、"
            "上昇気配/下降警戒、根拠資料の順に確認します。"
        ),
        "cockpit_forecast": (
            f"{section_phrase}では、中心予測を主役にし、"
            "下振れ、上振れ、信頼度、モデル合意度で読みの強さを確認します。"
        ),
        "cockpit_direction": (
            f"{section_phrase}では、上昇気配を攻めの材料、下降警戒を慎重材料として分け、"
            "AI予測と価格トレンドで裏取りします。"
        ),
        "cockpit_report": (
            f"{section_phrase}では、Decision Reportに価格・予測・リスク・根拠資料の"
            "確認結果を残し、後から判断理由を追えるようにします。"
        ),
    }
    return answers.get(focus, "")


def _focused_reasons(
    sections: Sequence[DecisionReportSection],
    intent: AssistantIntent,
    question: str,
) -> list[str]:
    focus = _question_focus(question, _context_hint(sections))
    reasons_by_focus = {
        "news_flow": [
            "市場全体の見出し",
            "カテゴリ別材料",
            "新着・最新ラベル",
            "気になる銘柄への深掘り導線",
        ],
        "news_related": [
            "本文に直接出た銘柄",
            "テーマから広がる関連候補",
            "ニュースとの距離感",
            "銘柄コックピットでの価格・予測確認",
        ],
        "news_source": [
            "出典メディア・公式資料",
            "公開日と更新の新しさ",
            "一次情報か二次情報か",
            "未確認の推測表現",
        ],
        "ranking_reason": [
            "AI総合スコア",
            "上昇気配と下降警戒の差",
            "高度予測の方向感",
            "データ信頼度",
        ],
        "ranking_compare": [
            "同じ評価軸でのスコア差",
            "上位候補ごとの強み",
            "下降警戒とリスクの違い",
            "深掘りに進む優先順位",
        ],
        "ranking_signals": [
            "AI総合: 候補の総合評価",
            "上昇気配: 上向き材料の強さ",
            "下降警戒: 慎重に見る材料",
            "高度予測と方向一致の有無",
        ],
        "ranking_confidence": [
            "データ信頼度",
            "欠損や古い価格データ",
            "根拠資料の有無",
            "低信頼時のスコア控えめ判定",
        ],
        "ranking_scope": [
            "ランキング作成対象",
            "取得期間",
            "評価方針",
            "除外・フィルター条件",
        ],
        "rebalance_drift": [
            "現在比率",
            "目標比率",
            "ズレ幅",
            "許容範囲を超えた資産",
        ],
        "rebalance_trade": [
            "提案売買の方向",
            "調整後の比率",
            "想定金額",
            "コストと実行タイミング",
        ],
        "rebalance_risk": [
            "集中リスク",
            "価格変動リスク",
            "データ不足",
            "調整後に増える偏り",
        ],
        "settings_provider": [
            "local/mock/yahoo/csv の用途",
            "ライブデータ利用の明示切替",
            "通常確認の再現性",
            "取得失敗時の扱い",
        ],
        "settings_documents": [
            "資料の出典",
            "対象銘柄との関係",
            "資料の更新日",
            "レポートに残す根拠",
        ],
        "settings_cache": [
            "最終更新日時",
            "欠損・古さの警告",
            "再取得キュー",
            "分析前に更新すべきデータ",
        ],
        "cockpit_first": [
            "価格チャート",
            "AI予測インサイト",
            "上昇気配/下降警戒",
            "根拠資料とデータ信頼度",
        ],
        "cockpit_forecast": [
            "中心予測",
            "下振れ予測",
            "上振れ予測",
            "信頼度とモデル合意度",
        ],
        "cockpit_direction": [
            "上昇気配スコア",
            "下降警戒スコア",
            "高度予測の方向一致",
            "価格トレンドの裏取り",
        ],
        "cockpit_report": [
            "価格と予測の結論",
            "注意材料",
            "確認した根拠資料",
            "未確認として残す項目",
        ],
    }
    return reasons_by_focus.get(focus, [])


def _focused_cautions(
    sections: Sequence[DecisionReportSection],
    intent: AssistantIntent,
    question: str,
) -> list[str]:
    focus = _question_focus(question, _context_hint(sections))
    cautions_by_focus = {
        "news_flow": [
            "見出しだけで判断せず、カテゴリ、本文、出典を分けて確認します。",
        ],
        "news_related": [
            "関連銘柄はニュース反応の入口であり、直接の投資結論ではありません。",
            "本文で直接言及された銘柄と、SMAIが広げた関連候補を混ぜないでください。",
        ],
        "news_source": [
            "古い記事、再配信、二次情報は強い根拠として扱いすぎないでください。",
        ],
        "ranking_reason": [
            "ランキング上位は確認順の候補であり、投資対象の確定ではありません。",
        ],
        "ranking_compare": [
            "順位差が小さい候補は、スコア差よりも理由とリスクの違いを優先します。",
        ],
        "ranking_signals": [
            "AI総合、上昇気配、下降警戒を同じ意味のスコアとして読まないでください。",
        ],
        "ranking_confidence": [
            "低信頼データは、スコアが高くても結論を控えめに扱います。",
        ],
        "ranking_scope": [
            "比較対象や取得期間が目的とズレると、順位の意味も変わります。",
        ],
        "rebalance_drift": [
            "ズレが大きいだけで取引が必要とは限らず、リスクとコストも見ます。",
        ],
        "rebalance_trade": [
            "提案取引は注文指示ではなく、配分見直しの検討材料です。",
        ],
        "rebalance_risk": [
            "リスク警告は損失回避を保証せず、確認優先度を示す材料です。",
        ],
        "settings_provider": [
            "ライブ取得は外部 provider の状態に左右されるため、通常確認とは分けます。",
        ],
        "settings_documents": [
            "資料は出典、公開日、対象銘柄との関係を確認してから根拠にします。",
        ],
        "settings_cache": [
            "古いキャッシュは便利な再利用材料ですが、最新判断の根拠には不足します。",
        ],
        "cockpit_first": [
            "価格、予測、スコアの一部だけで結論にしないでください。",
        ],
        "cockpit_forecast": [
            "予測は将来価格の保証ではなく、不確実性を読む参考情報です。",
        ],
        "cockpit_direction": [
            "上昇気配や下降警戒は売買方向ではなく、深掘り優先度の材料です。",
        ],
        "cockpit_report": [
            "Decision Reportは判断補助の記録であり、売買指示ではありません。",
        ],
    }
    if focus in cautions_by_focus:
        return cautions_by_focus[focus]
    if intent == "unknown" and _context_hint(sections) in {
        "news",
        "rebalance",
        "settings",
        "ranking",
    }:
        return ["この回答は画面内の確認順を整理するもので、結論を代替しません。"]
    return []


def _focused_checkpoints(
    sections: Sequence[DecisionReportSection],
    intent: AssistantIntent,
    question: str,
) -> list[str]:
    focus = _question_focus(question, _context_hint(sections))
    checkpoints_by_focus = {
        "news_flow": [
            "まず市場全体の見出しで、今日のテーマをつかみます。",
            "カテゴリ別材料で、決算、政策、需給などの論点を分けます。",
            "気になるニュースだけ、関連銘柄と出典の鮮度を開きます。",
        ],
        "news_related": [
            "本文に銘柄名が直接出ているかを確認します。",
            "関連候補はテーマとの距離が近い順に見ます。",
            "気になる銘柄は銘柄コックピットで価格・予測・根拠を確認します。",
        ],
        "news_source": [
            "公開日と更新時刻を確認します。",
            "公式資料、報道、二次情報を分けます。",
            "古い材料や未確認情報はDecision Reportに注意点として残します。",
        ],
        "ranking_reason": [
            "上位理由がAI総合、上昇気配、下降警戒のどこに出ているか見ます。",
            "スコアが高くても、下降警戒や低信頼データがないか確認します。",
            "深掘り候補はランキング順に確認し、理由が弱い候補は保留します。",
        ],
        "ranking_compare": [
            "候補同士を同じ取得期間と評価方針で比べます。",
            "上昇材料、警戒材料、データ信頼度の差を横並びで見ます。",
            "同点に近い候補は、根拠資料と価格チャートで差を確認します。",
        ],
        "ranking_signals": [
            "AI総合で候補の総合力を見ます。",
            "上昇気配で上向き材料の強さを確認します。",
            "下降警戒で読みを弱める材料がないか確認します。",
        ],
        "ranking_confidence": [
            "データ欠損、価格取得期間、根拠資料の不足を確認します。",
            "低信頼なら順位よりも確認タスクとして扱います。",
            "銘柄コックピットで価格・予測・根拠を再確認します。",
        ],
        "ranking_scope": [
            "比較対象の銘柄群が目的に合っているか確認します。",
            "取得期間と予測期間が意図した検証に合うか見ます。",
            "評価方針を変更したら、上位理由も読み直します。",
        ],
        "rebalance_drift": [
            "ズレ幅が大きい資産から確認します。",
            "目標比率に戻す必要性と許容範囲を分けて見ます。",
            "価格変動で一時的にズレていないか確認します。",
        ],
        "rebalance_trade": [
            "提案売買で調整後比率がどう変わるか確認します。",
            "手数料、税金、最小取引単位などの実行条件を確認します。",
            "一度に調整するか、段階的に見るかを分けます。",
        ],
        "rebalance_risk": [
            "集中リスクや価格変動リスクが増えないか見ます。",
            "提案取引後に別の資産が偏らないか確認します。",
            "データ不足がある場合は実行判断から切り離します。",
        ],
        "settings_provider": [
            "通常確認ならlocal/mock、実データ確認ならyahooを選びます。",
            "手元のCSVを使う場合は列名、日付、通貨を確認します。",
            "取得失敗時はprovider、期間、銘柄コードを切り分けます。",
        ],
        "settings_documents": [
            "資料の出典と更新日を確認します。",
            "対象銘柄に直接関係する資料かを分けます。",
            "Decision Reportに残す根拠として使えるか確認します。",
        ],
        "settings_cache": [
            "最終更新日時を見ます。",
            "古いキャッシュや失敗キューが残っていないか確認します。",
            "分析前に更新したいデータだけ再取得します。",
        ],
        "cockpit_first": [
            "価格チャートで直近の流れを見ます。",
            "AI予測インサイトで中心予測とレンジを確認します。",
            "根拠資料とリスク警告で読みを補強します。",
        ],
        "cockpit_forecast": [
            "中心予測を確認します。",
            "予測レンジ、下振れ、上振れの幅を見ます。",
            "信頼度とモデル合意度が低い場合は判断を控えめにします。",
        ],
        "cockpit_direction": [
            "上昇気配と下降警戒のどちらが強いか見ます。",
            "方向一致と価格トレンドで裏取りします。",
            "理由が割れている場合は根拠資料を確認します。",
        ],
        "cockpit_report": [
            "結論ではなく、確認した材料を短く残します。",
            "注意点と未確認項目を分けます。",
            "後でランキングやリバランスと見比べられる形にします。",
        ],
    }
    if focus in checkpoints_by_focus:
        return checkpoints_by_focus[focus]
    if intent == "unknown" and _context_hint(sections) in {
        "news",
        "rebalance",
        "settings",
        "ranking",
    }:
        return ["質問チップを切り替えて、確認したい観点ごとに材料を分けます。"]
    return []


def _collect_reasons(
    sections: Sequence[DecisionReportSection],
    intent: AssistantIntent,
    question: str,
    max_points: int,
) -> list[str]:
    candidates: list[str] = _focused_reasons(sections, intent, question)
    for section in sections:
        candidates.extend(_summary_points(section))
        candidates.extend(_row_points(section))
        candidates.extend(section.notes)
    return _dedupe(candidates)[:max_points]


def _collect_cautions(
    sections: Sequence[DecisionReportSection],
    intent: AssistantIntent,
    question: str,
    max_points: int,
) -> list[str]:
    cautions: list[str] = _focused_cautions(sections, intent, question)
    for section in sections:
        cautions.extend(section.warnings)
    if intent in {"score", "advice_boundary"}:
        cautions.append("スコアや順位は比較・分析用の参考値であり、売買推奨ではありません。")
    if intent == "forecast":
        cautions.append(
            "予測は将来価格の保証ではなく、モデルの見方と予測レンジを確認する参考情報です。"
        )
    if intent == "direction":
        cautions.append(
            "上昇気配や下降警戒は売買方向ではなく、深掘りの優先度を整理する補助指標です。"
        )
    if intent == "ranking":
        cautions.append("ランキング上位は確認順の候補であり、投資対象の確定ではありません。")
    if intent == "research":
        cautions.append("根拠資料は出典、公開日、未確認項目を合わせて確認してください。")
    if intent == "risk":
        cautions.append("リスク表示は損失回避や安全性を保証するものではありません。")
    if not cautions:
        cautions.append("不足している情報がある場合は、結論ではなく追加確認の対象として扱います。")
    return _dedupe(cautions)[:max_points]


def _build_next_checkpoints(
    sections: Sequence[DecisionReportSection],
    intent: AssistantIntent,
    question: str,
    max_points: int,
) -> list[str]:
    checkpoints = _dedupe(
        [
            *_focused_checkpoints(sections, intent, question),
            *_extract_confirmation_points(sections),
        ]
    )
    context_hint = _context_hint(sections)
    context_checkpoints: list[str] = []
    if context_hint == "news" and intent in {"next_steps", "unknown", "research"}:
        context_checkpoints.extend(
            [
                "ニュースのカテゴリ、関連銘柄、出典、公開タイミングを分けて確認します。",
                "気になる銘柄は銘柄コックピットで価格・予測・根拠を確認します。",
            ]
        )
    if context_hint == "rebalance" and intent in {"next_steps", "unknown", "risk"}:
        context_checkpoints.extend(
            [
                "現在比率と目標比率の差が大きい資産から確認します。",
                "提案取引はリスク警告と手数料・実行タイミングを分けて確認します。",
            ]
        )
    if context_hint == "settings" and intent in {"next_steps", "unknown", "research"}:
        context_checkpoints.extend(
            [
                "データ取得元、ローカル資料、キャッシュ更新状態を確認します。",
                "古い資料やキャッシュは、分析前に更新要否を確認します。",
            ]
        )
    if context_hint == "ranking" and intent in {"next_steps", "unknown", "ranking", "score"}:
        context_checkpoints.extend(
            [
                "評価方針と比較対象が目的に合っているか確認します。",
                "上位候補は総合スコア、下降警戒、データ信頼度を合わせて見ます。",
            ]
        )
    if context_checkpoints:
        return _dedupe([*checkpoints, *context_checkpoints])[:max_points]
    defaults_by_intent: dict[AssistantIntent, list[str]] = {
        "overview": [
            "スコア内訳、価格トレンド、データ品質、根拠資料を同じ銘柄で見比べます。",
        ],
        "score": [
            "総合スコアだけでなく、Screening、Forecast、Risk、Data Quality の内訳を確認します。",
        ],
        "forecast": [
            "中心予測、予測レンジ、信頼度、モデル合意度を見て、強く読める予測かを確認します。",
        ],
        "direction": [
            "上昇気配と下降警戒の差、AI予測インサイト、直近価格トレンドを同じ画面で確認します。",
        ],
        "ranking": [
            "1位だけで閉じず、上位候補の下降警戒、データ信頼度、AI予測インサイトを見比べます。",
        ],
        "risk": [
            "警告がある場合は、価格変動、保有比率、データ欠損、短期材料を分けて確認します。",
        ],
        "research": [
            "出典URL、公開日、公式資料か外部ニュースか、未確認項目を確認します。",
        ],
        "next_steps": [
            "不足しているデータと、判断に使える根拠がそろっているデータを分けます。",
        ],
        "advice_boundary": [
            "売買判断ではなく、判断材料の不足、注意材料、確認済み根拠を整理します。",
        ],
        "unknown": [
            "質問をスコア、リスク、根拠資料、次の確認観点のどれかに分けて確認します。",
        ],
    }
    return _dedupe([*checkpoints, *defaults_by_intent[intent]])[:max_points]


def _summary_points(section: DecisionReportSection) -> list[str]:
    points = []
    for key, value in section.summary.items():
        if value:
            points.append(f"{key}: {value}")
    return points


def _row_points(section: DecisionReportSection) -> list[str]:
    points = []
    for row in section.rows:
        if not row:
            continue
        compact = " / ".join(f"{key}: {value}" for key, value in row.items() if value)
        if compact:
            points.append(compact)
    return points


def _extract_confirmation_points(
    sections: Sequence[DecisionReportSection],
) -> list[str]:
    points: list[str] = []
    for section in sections:
        for row in section.rows:
            for key, value in row.items():
                if value and any(term in key.lower() for term in ("confirm", "確認", "checkpoint")):
                    points.append(value)
    return points


def _citation_from_section(section: DecisionReportSection) -> AssistantCitation:
    return AssistantCitation(
        section_title=section.title,
        source_kind=section.source.kind,
        symbol=section.source.symbol,
    )


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
