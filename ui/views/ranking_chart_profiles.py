from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RankingChartProfile:
    key: str
    title: str
    x_candidates: tuple[str, ...]
    y_candidates: tuple[str, ...]
    color_candidates: tuple[str, ...] = ()
    fallback_key: str | None = None
    description: str = ""
    how_to_read: tuple[str, ...] = ()
    caution: str = "このグラフは売買推奨ではなく、比較・確認のための補助情報です。"


@dataclass(frozen=True)
class RankingChartSelection:
    profile: RankingChartProfile
    frame: pd.DataFrame
    x_column: str
    y_column: str
    color_column: str | None
    used_fallback: bool


PROFILE_SCORE_RISK = "score_risk"
PROFILE_SCREENING_RISK = "screening_risk"
PROFILE_SCORE_FORECAST = "score_forecast"
PROFILE_SCORE_CONFIDENCE = "score_confidence"
PROFILE_DIVIDEND_STABILITY = "dividend_stability"
PROFILE_GROWTH_MOMENTUM = "growth_momentum"
PROFILE_VALUE_RISK = "value_risk"
PROFILE_STABILITY_RISK = "stability_risk"
PROFILE_MOMENTUM_FORECAST = "momentum_forecast"
PROFILE_LONG_TERM_CONFIDENCE = "long_term_confidence"
PROFILE_ETF_COST_SCORE = "etf_cost_score"
PROFILE_UPSIDE_DOWNSIDE = "upside_downside"
PROFILE_FIT_DIRECTION = "fit_direction"
PROFILE_FIT_RISK = "fit_risk"
PROFILE_CONFIDENCE_QUALITY = "confidence_quality"
PROFILE_ETF_FIT_CONFIDENCE = "etf_fit_confidence"

RANKING_CHART_PROFILES: dict[str, RankingChartProfile] = {
    PROFILE_SCORE_RISK: RankingChartProfile(
        key=PROFILE_SCORE_RISK,
        title="Score x Risk Map",
        x_candidates=("総合スコア", "Investment Score"),
        y_candidates=("Risk",),
        color_candidates=("方向感", "見方", "注意点"),
        description=(
            "スコアが高い候補の中で、リスクもあわせて確認できます。"
            "高スコアでもリスクが高い場合は、詳細確認に進むと安心です。"
        ),
        how_to_read=(
            "High score / Low risk: 深掘り優先候補",
            "High score / High risk: 魅力はあるが注意して確認",
            "Low score / Low risk: 安定だが魅力度は低め",
            "Low score / High risk: 優先度低め",
        ),
    ),
    PROFILE_SCREENING_RISK: RankingChartProfile(
        key=PROFILE_SCREENING_RISK,
        title="Screening x Risk Map",
        x_candidates=("Screening", "screening_score"),
        y_candidates=("Risk",),
        color_candidates=("データ品質", "条件適合度", "見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        description=(
            "方向データが不足する場合でも、価格・出来高・モメンタム由来のScreeningとRiskを分けて確認できます。"
        ),
        how_to_read=(
            "High screening / High risk score: 足元条件が強く、リスク面も比較しやすい候補",
            "High screening / Low risk score: 足元条件は強いが、値動きや下落耐性を確認",
            "Low screening / High risk score: 安定性はあるが、足元条件は弱め",
            "Low screening / Low risk score: 優先度低め、またはデータ確認候補",
        ),
    ),
    PROFILE_SCORE_FORECAST: RankingChartProfile(
        key=PROFILE_SCORE_FORECAST,
        title="Score x Direction Map",
        x_candidates=("総合スコア", "Investment Score"),
        y_candidates=("方向スコア", "上昇気配", "Direction Signal", "Upside Signal"),
        color_candidates=("下降警戒", "方向感", "見方", "注意点"),
        description="スコアが高い候補について、上昇気配と下降警戒をあわせた方向感を確認できます。",
        how_to_read=(
            "High score / High direction: 上向きシグナルがある深掘り候補",
            "High score / Low direction: 下降警戒や方向感の弱さを確認",
            "Low score / High direction: 上向き材料はあるが総合点は低め",
            "Low score / Low direction: 優先度低め",
        ),
    ),
    PROFILE_SCORE_CONFIDENCE: RankingChartProfile(
        key=PROFILE_SCORE_CONFIDENCE,
        title="Score x Evaluation Confidence",
        x_candidates=("総合スコア", "Investment Score"),
        y_candidates=("DB信頼度", "DB適合", "データ品質", "Evaluation Confidence"),
        color_candidates=("根拠状態", "見方", "注意点"),
        description="スコアとデータの充実度を分けて確認できます。高スコアでも信頼度が低い場合はデータ確認が先です。",
        how_to_read=(
            "High score / High confidence: 深掘りしやすい候補",
            "High score / Low confidence: データ確認が必要な候補",
            "Low score / High confidence: 評価は安定しているが総合点は低め",
            "Low score / Low confidence: 優先度低め",
        ),
        caution=(
            "Evaluation Confidence は投資魅力度ではなく、評価に使えるデータの充実度を示す補助指標です。"
        ),
    ),
    PROFILE_DIVIDEND_STABILITY: RankingChartProfile(
        key=PROFILE_DIVIDEND_STABILITY,
        title="Dividend x Stability Map",
        x_candidates=("Dividend Score", "配当スコア", "配当"),
        y_candidates=("Stability Score", "安定性", "データ品質"),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        description="配当観点の候補について、安定性もあわせて確認できます。",
        how_to_read=(
            "High dividend / High stability: 配当観点で深掘りしやすい候補",
            "High dividend / Low stability: 配当の持続性を確認",
            "Low dividend / High stability: 安定性中心で確認",
            "Low dividend / Low stability: 優先度低め",
        ),
    ),
    PROFILE_GROWTH_MOMENTUM: RankingChartProfile(
        key=PROFILE_GROWTH_MOMENTUM,
        title="Growth x Momentum Map",
        x_candidates=("Growth Score", "成長スコア", "成長"),
        y_candidates=("Momentum Score", "モメンタム", "Screening"),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_FORECAST,
        description="成長観点の候補について、足元の勢いもあわせて確認できます。",
        how_to_read=(
            "High growth / High momentum: 成長観点で深掘りしやすい候補",
            "High growth / Low momentum: 直近トレンドを確認",
            "Low growth / High momentum: 短期材料を確認",
            "Low growth / Low momentum: 優先度低め",
        ),
    ),
    PROFILE_VALUE_RISK: RankingChartProfile(
        key=PROFILE_VALUE_RISK,
        title="Valuation x Risk Map",
        x_candidates=("Valuation Score", "割安スコア", "割安"),
        y_candidates=("Risk",),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        description="割安に見える候補について、リスクもあわせて確認できます。",
        how_to_read=(
            "High valuation / Low risk: 割安観点で深掘りしやすい候補",
            "High valuation / High risk: 割安理由とリスクを確認",
            "Low valuation / Low risk: 安定性中心で確認",
            "Low valuation / High risk: 優先度低め",
        ),
    ),
    PROFILE_STABILITY_RISK: RankingChartProfile(
        key=PROFILE_STABILITY_RISK,
        title="Stability x Risk Map",
        x_candidates=("Stability Score", "安定性", "データ品質"),
        y_candidates=("Risk",),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        description="安定性を重視する候補について、リスクの強さもあわせて確認できます。",
        how_to_read=(
            "High stability / Low risk: 安定観点で深掘りしやすい候補",
            "High stability / High risk: リスク要因を確認",
            "Low stability / Low risk: データや事業特性を確認",
            "Low stability / High risk: 優先度低め",
        ),
    ),
    PROFILE_MOMENTUM_FORECAST: RankingChartProfile(
        key=PROFILE_MOMENTUM_FORECAST,
        title="Momentum x Direction Map",
        x_candidates=("Momentum Score", "モメンタム", "Screening"),
        y_candidates=("方向スコア", "上昇気配", "Direction Signal", "Upside Signal"),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_FORECAST,
        description="足元の勢いがある候補について、方向感と下降警戒もあわせて確認できます。",
        how_to_read=(
            "High momentum / High direction: トレンド観点で深掘りしやすい候補",
            "High momentum / Low direction: 上昇気配と下降警戒を確認",
            "Low momentum / High direction: 方向感はあるが足元の勢いは弱め",
            "Low momentum / Low direction: 優先度低め",
        ),
    ),
    PROFILE_LONG_TERM_CONFIDENCE: RankingChartProfile(
        key=PROFILE_LONG_TERM_CONFIDENCE,
        title="Long-term Fit x Confidence Map",
        x_candidates=("Stability Score", "安定性", "データ品質"),
        y_candidates=("DB信頼度", "DB適合", "Evaluation Confidence"),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        description="長期で確認したい候補について、安定性とデータ充実度を分けて確認できます。",
        how_to_read=(
            "High fit / High confidence: 長期観点で深掘りしやすい候補",
            "High fit / Low confidence: データ充実度を確認",
            "Low fit / High confidence: 評価は安定しているが適合度は低め",
            "Low fit / Low confidence: 優先度低め",
        ),
    ),
    PROFILE_ETF_COST_SCORE: RankingChartProfile(
        key=PROFILE_ETF_COST_SCORE,
        title="ETF Cost x Score Map",
        x_candidates=("Cost Score", "Expense Ratio", "経費率"),
        y_candidates=("総合スコア", "Investment Score"),
        color_candidates=("DB信頼度", "Risk", "見方", "注意点"),
        fallback_key=PROFILE_SCORE_CONFIDENCE,
        description="ETF候補について、コスト観点と総合スコアを分けて確認できます。",
        how_to_read=(
            "Low cost / High score: コア候補として深掘りしやすい候補",
            "Low cost / Low score: コスト以外の観点を確認",
            "High cost / High score: コストに見合う理由を確認",
            "High cost / Low score: 優先度低め",
        ),
    ),
    PROFILE_UPSIDE_DOWNSIDE: RankingChartProfile(
        key=PROFILE_UPSIDE_DOWNSIDE,
        title="Upside x Downside Watch Map",
        x_candidates=("上昇気配", "Upside Signal"),
        y_candidates=("下降警戒", "Risk", "方向スコア"),
        color_candidates=("方向スコア", "方向感", "見方", "注意点"),
        fallback_key=PROFILE_SCREENING_RISK,
        description=("上昇気配と下降警戒を分けて見ながら、差し引き後の方向感を色で確認できます。"),
        how_to_read=(
            "High upside / Low downside: 上向きシグナルが強く、警戒材料が相対的に少ない深掘り候補",
            "High upside / High downside: 上向き材料はあるが、下降警戒も先に確認",
            "Low upside / High downside: リスク確認候補",
            "Low upside / Low downside: 方向感は限定的な比較候補",
        ),
    ),
    PROFILE_FIT_DIRECTION: RankingChartProfile(
        key=PROFILE_FIT_DIRECTION,
        title="Fit x Direction Map",
        x_candidates=("条件適合度", "DB適合"),
        y_candidates=("方向スコア", "上昇気配"),
        color_candidates=("Risk", "方向感", "注意点"),
        fallback_key=PROFILE_SCORE_FORECAST,
        description="選択中の目的に合う候補について、方向感が伴っているかを確認できます。",
        how_to_read=(
            "High fit / High direction: 条件に合い、上向きシグナルもある深掘り候補",
            "High fit / Low direction: 条件には合うが、方向感や下降警戒を確認",
            "Low fit / High direction: 上向き材料はあるが、目的適合は低め",
            "Low fit / Low direction: 優先度低め",
        ),
    ),
    PROFILE_FIT_RISK: RankingChartProfile(
        key=PROFILE_FIT_RISK,
        title="Fit x Risk Map",
        x_candidates=("条件適合度", "DB適合"),
        y_candidates=("Risk",),
        color_candidates=("データ品質", "注意点", "見方"),
        fallback_key=PROFILE_SCORE_RISK,
        description="条件に合う候補について、Riskとデータ品質をあわせて確認できます。",
        how_to_read=(
            "High fit / High risk score: 条件に合い、Risk面も比較しやすい候補",
            "High fit / Low risk score: 条件には合うが、リスク要因を確認",
            "Low fit / High risk score: 安定性はあるが、目的適合は低め",
            "Low fit / Low risk score: 優先度低め",
        ),
    ),
    PROFILE_CONFIDENCE_QUALITY: RankingChartProfile(
        key=PROFILE_CONFIDENCE_QUALITY,
        title="Data Quality x Confidence Map",
        x_candidates=("DB信頼度", "Evaluation Confidence"),
        y_candidates=("データ品質",),
        color_candidates=("根拠状態", "注意点", "見方"),
        fallback_key=PROFILE_SCORE_CONFIDENCE,
        description="データ信頼度優先で見る候補について、DB信頼度と価格データ品質を分けて確認できます。",
        how_to_read=(
            "High confidence / High quality: 根拠と価格データがそろった確認しやすい候補",
            "High confidence / Low quality: DB情報はあるが、価格データ品質を確認",
            "Low confidence / High quality: 価格評価はできるが、銘柄DBや根拠を確認",
            "Low confidence / Low quality: 先にデータ確認が必要",
        ),
        caution="Data Quality と DB信頼度は投資魅力度ではなく、評価に使えるデータの充実度です。",
    ),
    PROFILE_ETF_FIT_CONFIDENCE: RankingChartProfile(
        key=PROFILE_ETF_FIT_CONFIDENCE,
        title="ETF Fit x Confidence Map",
        x_candidates=("条件適合度", "DB適合"),
        y_candidates=("DB信頼度", "データ品質"),
        color_candidates=("経費率", "Risk", "注意点"),
        fallback_key=PROFILE_SCORE_CONFIDENCE,
        description="ETF候補について、目的適合とデータ充実度を分けて確認できます。",
        how_to_read=(
            "High fit / High confidence: ETF条件に合い、確認材料もそろった候補",
            "High fit / Low confidence: 条件には合うが、指数・コスト・分配方針を確認",
            "Low fit / High confidence: データはあるが、選択目的との一致は低め",
            "Low fit / Low confidence: 先にデータ確認が必要",
        ),
    ),
}

RANKING_PURPOSE_CHART_PROFILE_KEYS: dict[str, str] = {
    "multi_factor": PROFILE_UPSIDE_DOWNSIDE,
    "upside_signal": PROFILE_UPSIDE_DOWNSIDE,
    "quality_growth": PROFILE_FIT_DIRECTION,
    "quality_value": PROFILE_FIT_RISK,
    "sustainable_income": PROFILE_FIT_RISK,
    "min_volatility": PROFILE_STABILITY_RISK,
    "momentum": PROFILE_MOMENTUM_FORECAST,
    "risk_adjusted": PROFILE_SCORE_RISK,
    "small_growth": PROFILE_FIT_DIRECTION,
    "nisa_long_term": PROFILE_LONG_TERM_CONFIDENCE,
    "data_confidence": PROFILE_CONFIDENCE_QUALITY,
    "etf_core_cost": PROFILE_ETF_COST_SCORE,
    "etf_income": PROFILE_ETF_FIT_CONFIDENCE,
    "dividend": PROFILE_FIT_RISK,
    "growth": PROFILE_FIT_DIRECTION,
    "value": PROFILE_FIT_RISK,
    "stability": PROFILE_STABILITY_RISK,
    "trend": PROFILE_MOMENTUM_FORECAST,
}


def chart_profile_for_purpose(ranking_purpose: str) -> RankingChartProfile:
    profile_key = RANKING_PURPOSE_CHART_PROFILE_KEYS.get(ranking_purpose, PROFILE_SCORE_RISK)
    return RANKING_CHART_PROFILES[profile_key]


def ranking_chart_frame(
    display_rows: list[dict[str, str]],
    profile: RankingChartProfile,
    *,
    min_rows: int = 3,
) -> RankingChartSelection | None:
    return _ranking_chart_frame(
        display_rows,
        profile,
        min_rows=min_rows,
        used_fallback=False,
        visited=set(),
    )


def _ranking_chart_frame(
    display_rows: list[dict[str, str]],
    profile: RankingChartProfile,
    *,
    min_rows: int,
    used_fallback: bool,
    visited: set[str],
) -> RankingChartSelection | None:
    if profile.key in visited:
        return None
    visited.add(profile.key)
    x_column = _first_numeric_column(display_rows, profile.x_candidates, min_rows=min_rows)
    y_column = _first_numeric_column(display_rows, profile.y_candidates, min_rows=min_rows)
    if x_column and y_column:
        color_column = _first_present_column(display_rows, profile.color_candidates)
        frame = _profile_frame(
            display_rows,
            x_column=x_column,
            y_column=y_column,
            color_column=color_column,
        )
        frame = frame.dropna(subset=["x_value", "y_value"])
        if len(frame) >= min_rows and _frame_has_profile_variation(frame, profile):
            return RankingChartSelection(
                profile=profile,
                frame=frame,
                x_column=x_column,
                y_column=y_column,
                color_column=color_column,
                used_fallback=used_fallback,
            )
    if profile.fallback_key:
        fallback = RANKING_CHART_PROFILES[profile.fallback_key]
        return _ranking_chart_frame(
            display_rows,
            fallback,
            min_rows=min_rows,
            used_fallback=True,
            visited=visited,
        )
    return None


def _frame_has_visual_variation(frame: pd.DataFrame) -> bool:
    return frame["x_value"].nunique(dropna=True) >= 2 or frame["y_value"].nunique(dropna=True) >= 2


def _frame_has_profile_variation(frame: pd.DataFrame, profile: RankingChartProfile) -> bool:
    if profile.key == PROFILE_UPSIDE_DOWNSIDE:
        return (
            frame["x_value"].nunique(dropna=True) >= 2
            and frame["y_value"].nunique(dropna=True) >= 2
        )
    return _frame_has_visual_variation(frame)


def _first_numeric_column(
    rows: list[dict[str, str]],
    candidates: tuple[str, ...],
    *,
    min_rows: int,
) -> str | None:
    for column in candidates:
        values = [_numeric_value(row.get(column, "")) for row in rows]
        if sum(value is not None for value in values) >= min_rows:
            return column
    return None


def _first_present_column(
    rows: list[dict[str, str]],
    candidates: tuple[str, ...],
) -> str | None:
    for column in candidates:
        if any(str(row.get(column, "")).strip() for row in rows):
            return column
    return None


def _profile_frame(
    rows: list[dict[str, str]],
    *,
    x_column: str,
    y_column: str,
    color_column: str | None,
) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for row in rows:
        x_value = _numeric_value(row.get(x_column, ""))
        y_value = _numeric_value(row.get(y_column, ""))
        if x_value is None or y_value is None:
            continue
        records.append(
            {
                "rank": row.get("順位", ""),
                "symbol": row.get("銘柄", ""),
                "name": row.get("銘柄名", ""),
                "x_value": x_value,
                "y_value": y_value,
                "color_value": row.get(color_column, "") if color_column else "",
                "color_numeric_value": (
                    _numeric_value(row.get(color_column, "")) if color_column else None
                ),
                "caution": row.get("注意点", ""),
            }
        )
    return pd.DataFrame.from_records(records)


def _numeric_value(value: object) -> float | None:
    text = str(value or "").replace("%", "").replace(",", "").strip()
    if not text or text in {"-", "未接続", "未登録", "未計算"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None
