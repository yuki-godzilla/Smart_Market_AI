from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ui.content.ranking_texts import RANKING_CHART_PROFILE_TEXTS


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
        x_candidates=("総合スコア", "Investment Score"),
        y_candidates=("Risk",),
        color_candidates=("見方", "注意点"),
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_SCORE_RISK],
    ),
    PROFILE_SCREENING_RISK: RankingChartProfile(
        key=PROFILE_SCREENING_RISK,
        x_candidates=("Screening", "screening_score"),
        y_candidates=("Risk",),
        color_candidates=("データ品質", "条件適合度", "見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_SCREENING_RISK],
    ),
    PROFILE_SCORE_FORECAST: RankingChartProfile(
        key=PROFILE_SCORE_FORECAST,
        x_candidates=("総合スコア", "Investment Score"),
        y_candidates=("上昇気配", "Upside Signal", "下降警戒"),
        color_candidates=("下降警戒", "見方", "注意点"),
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_SCORE_FORECAST],
    ),
    PROFILE_SCORE_CONFIDENCE: RankingChartProfile(
        key=PROFILE_SCORE_CONFIDENCE,
        x_candidates=("総合スコア", "Investment Score"),
        y_candidates=("DB信頼度", "DB適合", "データ品質", "Evaluation Confidence"),
        color_candidates=("根拠状態", "見方", "注意点"),
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_SCORE_CONFIDENCE],
    ),
    PROFILE_DIVIDEND_STABILITY: RankingChartProfile(
        key=PROFILE_DIVIDEND_STABILITY,
        x_candidates=("Dividend Score", "配当スコア", "配当"),
        y_candidates=("Stability Score", "安定性", "データ品質"),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_DIVIDEND_STABILITY],
    ),
    PROFILE_GROWTH_MOMENTUM: RankingChartProfile(
        key=PROFILE_GROWTH_MOMENTUM,
        x_candidates=("Growth Score", "成長スコア", "成長"),
        y_candidates=("Momentum Score", "モメンタム", "Screening"),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_FORECAST,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_GROWTH_MOMENTUM],
    ),
    PROFILE_VALUE_RISK: RankingChartProfile(
        key=PROFILE_VALUE_RISK,
        x_candidates=("Valuation Score", "割安スコア", "割安"),
        y_candidates=("Risk",),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_VALUE_RISK],
    ),
    PROFILE_STABILITY_RISK: RankingChartProfile(
        key=PROFILE_STABILITY_RISK,
        x_candidates=("Stability Score", "安定性", "データ品質"),
        y_candidates=("Risk",),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_STABILITY_RISK],
    ),
    PROFILE_MOMENTUM_FORECAST: RankingChartProfile(
        key=PROFILE_MOMENTUM_FORECAST,
        x_candidates=("Momentum Score", "モメンタム", "Screening"),
        y_candidates=("上昇気配", "Upside Signal", "下降警戒"),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_FORECAST,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_MOMENTUM_FORECAST],
    ),
    PROFILE_LONG_TERM_CONFIDENCE: RankingChartProfile(
        key=PROFILE_LONG_TERM_CONFIDENCE,
        x_candidates=("Stability Score", "安定性", "データ品質"),
        y_candidates=("DB信頼度", "DB適合", "Evaluation Confidence"),
        color_candidates=("見方", "注意点"),
        fallback_key=PROFILE_SCORE_RISK,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_LONG_TERM_CONFIDENCE],
    ),
    PROFILE_ETF_COST_SCORE: RankingChartProfile(
        key=PROFILE_ETF_COST_SCORE,
        x_candidates=("Cost Score", "Expense Ratio", "経費率"),
        y_candidates=("総合スコア", "Investment Score"),
        color_candidates=("DB信頼度", "Risk", "見方", "注意点"),
        fallback_key=PROFILE_SCORE_CONFIDENCE,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_ETF_COST_SCORE],
    ),
    PROFILE_UPSIDE_DOWNSIDE: RankingChartProfile(
        key=PROFILE_UPSIDE_DOWNSIDE,
        x_candidates=("上昇気配", "Upside Signal"),
        y_candidates=("下降警戒", "Risk"),
        color_candidates=("Risk", "見方", "注意点"),
        fallback_key=PROFILE_SCREENING_RISK,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_UPSIDE_DOWNSIDE],
    ),
    PROFILE_FIT_DIRECTION: RankingChartProfile(
        key=PROFILE_FIT_DIRECTION,
        x_candidates=("条件適合度", "DB適合"),
        y_candidates=("上昇気配", "下降警戒"),
        color_candidates=("Risk", "注意点"),
        fallback_key=PROFILE_SCORE_FORECAST,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_FIT_DIRECTION],
    ),
    PROFILE_FIT_RISK: RankingChartProfile(
        key=PROFILE_FIT_RISK,
        x_candidates=("条件適合度", "DB適合"),
        y_candidates=("Risk",),
        color_candidates=("データ品質", "注意点", "見方"),
        fallback_key=PROFILE_SCORE_RISK,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_FIT_RISK],
    ),
    PROFILE_CONFIDENCE_QUALITY: RankingChartProfile(
        key=PROFILE_CONFIDENCE_QUALITY,
        x_candidates=("DB信頼度", "Evaluation Confidence"),
        y_candidates=("データ品質",),
        color_candidates=("根拠状態", "注意点", "見方"),
        fallback_key=PROFILE_SCORE_CONFIDENCE,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_CONFIDENCE_QUALITY],
    ),
    PROFILE_ETF_FIT_CONFIDENCE: RankingChartProfile(
        key=PROFILE_ETF_FIT_CONFIDENCE,
        x_candidates=("条件適合度", "DB適合"),
        y_candidates=("DB信頼度", "データ品質"),
        color_candidates=("経費率", "Risk", "注意点"),
        fallback_key=PROFILE_SCORE_CONFIDENCE,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_ETF_FIT_CONFIDENCE],
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
