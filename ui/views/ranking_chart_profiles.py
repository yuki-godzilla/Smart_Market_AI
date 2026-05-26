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
PROFILE_SCORE_FORECAST = "score_forecast"
PROFILE_SCORE_CONFIDENCE = "score_confidence"
PROFILE_DIVIDEND_STABILITY = "dividend_stability"
PROFILE_GROWTH_MOMENTUM = "growth_momentum"
PROFILE_VALUE_RISK = "value_risk"
PROFILE_STABILITY_RISK = "stability_risk"
PROFILE_MOMENTUM_FORECAST = "momentum_forecast"
PROFILE_LONG_TERM_CONFIDENCE = "long_term_confidence"
PROFILE_ETF_COST_SCORE = "etf_cost_score"

RANKING_CHART_PROFILES: dict[str, RankingChartProfile] = {
    PROFILE_SCORE_RISK: RankingChartProfile(
        key=PROFILE_SCORE_RISK,
        title="Score x Risk Map",
        x_candidates=("総合スコア", "Investment Score"),
        y_candidates=("Risk",),
        color_candidates=("見方", "注意点"),
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
    PROFILE_SCORE_FORECAST: RankingChartProfile(
        key=PROFILE_SCORE_FORECAST,
        title="Score x Direction Map",
        x_candidates=("総合スコア", "Investment Score"),
        y_candidates=("方向スコア", "上昇気配", "Direction Signal", "Upside Signal"),
        color_candidates=("見方", "注意点"),
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
        color_candidates=("見方", "注意点"),
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
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_CONFIDENCE,
        description="ETF候補について、コスト観点と総合スコアを分けて確認できます。",
        how_to_read=(
            "Low cost / High score: コア候補として深掘りしやすい候補",
            "Low cost / Low score: コスト以外の観点を確認",
            "High cost / High score: コストに見合う理由を確認",
            "High cost / Low score: 優先度低め",
        ),
    ),
}

RANKING_PURPOSE_CHART_PROFILE_KEYS: dict[str, str] = {
    "multi_factor": PROFILE_SCORE_RISK,
    "quality_growth": PROFILE_GROWTH_MOMENTUM,
    "quality_value": PROFILE_VALUE_RISK,
    "sustainable_income": PROFILE_DIVIDEND_STABILITY,
    "min_volatility": PROFILE_STABILITY_RISK,
    "momentum": PROFILE_MOMENTUM_FORECAST,
    "risk_adjusted": PROFILE_STABILITY_RISK,
    "small_growth": PROFILE_GROWTH_MOMENTUM,
    "nisa_long_term": PROFILE_LONG_TERM_CONFIDENCE,
    "data_confidence": PROFILE_SCORE_CONFIDENCE,
    "etf_core_cost": PROFILE_ETF_COST_SCORE,
    "etf_income": PROFILE_DIVIDEND_STABILITY,
    "dividend": PROFILE_DIVIDEND_STABILITY,
    "growth": PROFILE_GROWTH_MOMENTUM,
    "value": PROFILE_VALUE_RISK,
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
        if len(frame) >= min_rows:
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
