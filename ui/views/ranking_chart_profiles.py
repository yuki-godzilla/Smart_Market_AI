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
    size_candidates: tuple[str, ...] = ()
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
    size_column: str | None
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
PROFILE_REVERSAL_EXPECTATION = "reversal_expectation"

REVERSAL_EVIDENCE_COMPONENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("総合", ("上向き兆候", "reversal_expectation_score")),
    ("形状", ("reversal_chart_shape_score", "チャート形状評価")),
    ("予測余地", ("reversal_forecast_score", "上向き余地")),
    ("下落安全", ("reversal_safety_score", "下落安全性")),
    ("押し目", ("reversal_pullback_score", "調整度スコア")),
    ("補助品質", ("reversal_quality_score",)),
    ("上向き材料", ("reversal_material_score",)),
)

RANKING_CHART_PROFILES: dict[str, RankingChartProfile] = {
    PROFILE_REVERSAL_EXPECTATION: RankingChartProfile(
        key=PROFILE_REVERSAL_EXPECTATION,
        x_candidates=(
            "チャート形状評価",
            "reversal_chart_shape_score",
            "調整度スコア",
            "reversal_pullback_score",
            "調整/安定度",
            "20日高値乖離",
        ),
        y_candidates=("上向き余地", "reversal_forecast_score", "上向き兆候"),
        color_candidates=("下落安全性", "reversal_safety_score"),
        size_candidates=("データ品質", "data_quality_score"),
        fallback_key=PROFILE_UPSIDE_DOWNSIDE,
        **RANKING_CHART_PROFILE_TEXTS[PROFILE_REVERSAL_EXPECTATION],
    ),
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
    "reversal_expectation": PROFILE_REVERSAL_EXPECTATION,
    "multi_factor": PROFILE_UPSIDE_DOWNSIDE,
    "upside_signal": PROFILE_UPSIDE_DOWNSIDE,
    "downside_signal": PROFILE_UPSIDE_DOWNSIDE,
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


def ranking_reversal_evidence_frame(
    display_rows: list[dict[str, str]],
    *,
    max_rows: int = 10,
) -> pd.DataFrame:
    """Return a long-form evidence map for the top upward-signal candidates.

    Data quality is deliberately represented as an evaluation gate attached to
    each candidate, not as a score axis, bubble size, or attractiveness cell.
    """

    ordered_rows = sorted(
        enumerate(display_rows),
        key=lambda item: (_rank_value(item[1].get("順位", ""), item[0]), item[0]),
    )[: max(0, max_rows)]
    records: list[dict[str, object]] = []
    for source_index, row in ordered_rows:
        rank_order = _rank_value(row.get("順位", ""), source_index)
        rank = str(row.get("順位", "")).strip() or str(rank_order)
        symbol = str(row.get("銘柄", "")).strip() or "銘柄未設定"
        quality_status = ranking_data_quality_gate(row)
        candidate_label = f"{rank}. {symbol}｜{quality_status}"
        candidate_has_score = any(
            _first_numeric_value(row, candidates) is not None
            for _, candidates in REVERSAL_EVIDENCE_COMPONENTS
        )
        if not candidate_has_score:
            continue
        for component_order, (component, candidates) in enumerate(REVERSAL_EVIDENCE_COMPONENTS):
            score = _first_numeric_value(row, candidates)
            if score is None:
                continue
            records.append(
                {
                    "rank": rank,
                    "rank_order": rank_order,
                    "symbol": symbol,
                    "name": row.get("銘柄名", ""),
                    "candidate_label": candidate_label,
                    "component": component,
                    "component_order": component_order,
                    "score": score,
                    "score_label": _score_label(score),
                    "quality_status": quality_status,
                    "data_quality": row.get("データ品質", "") or row.get("data_quality_score", ""),
                    "shape_label": row.get("チャート形状", "")
                    or row.get("reversal_chart_shape_label", ""),
                    "signal_reason": row.get("上向き兆候理由", "")
                    or row.get("reversal_expectation_reason", ""),
                    "trap_warning": row.get("reversal_trap_warning", ""),
                    "pullback_rebound": row.get("pullback_rebound_score", ""),
                    "bottoming": row.get("bottoming_score", ""),
                    "range_breakout": row.get("range_breakout_score", ""),
                    "accumulation": row.get("accumulation_setup_score", ""),
                }
            )
    return pd.DataFrame.from_records(records)


def ranking_data_quality_gate(row: dict[str, str]) -> str:
    warning_text = " ".join(
        str(row.get(key, ""))
        for key in (
            "warnings_raw",
            "warnings",
            "注意点",
            "reversal_trap_warning",
        )
    ).lower()
    expectation_label = str(
        row.get("reversal_expectation_label", "") or row.get("上向き兆候ラベル", "")
    ).strip()
    block_tokens = (
        "data_quality:block",
        "price_data:block",
        "price_history:block",
        "insufficient_ohlcv_rows",
        "insufficient_price_history",
        "データ不足が大きい",
        "評価材料不足",
    )
    if expectation_label == "未評価" or any(token in warning_text for token in block_tokens):
        return "評価対象外"

    quality = _first_numeric_value(row, ("データ品質", "data_quality_score"))
    warn_tokens = ("data_quality:warn", "データ品質に注意")
    if quality is None or quality < 60 or any(token in warning_text for token in warn_tokens):
        return "要確認"
    return "評価可能"


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
    color_column = _first_present_column(display_rows, profile.color_candidates)
    size_column = _first_numeric_column(display_rows, profile.size_candidates, min_rows=min_rows)
    for x_column in _numeric_columns(display_rows, profile.x_candidates, min_rows=min_rows):
        for y_column in _numeric_columns(display_rows, profile.y_candidates, min_rows=min_rows):
            frame = _profile_frame(
                display_rows,
                x_column=x_column,
                y_column=y_column,
                color_column=color_column,
                size_column=size_column,
            )
            frame = frame.dropna(subset=["x_value", "y_value"])
            if len(frame) >= min_rows and _frame_has_profile_variation(frame, profile):
                return RankingChartSelection(
                    profile=profile,
                    frame=frame,
                    x_column=x_column,
                    y_column=y_column,
                    color_column=color_column,
                    size_column=size_column,
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
    _ = profile
    # A scatter map with a fixed axis is a misleading line rather than a
    # two-dimensional comparison. Require both axes to carry information, then
    # try the profile's next candidates or its purpose-specific fallback.
    return frame["x_value"].nunique(dropna=True) >= 2 and frame["y_value"].nunique(dropna=True) >= 2


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


def _numeric_columns(
    rows: list[dict[str, str]],
    candidates: tuple[str, ...],
    *,
    min_rows: int,
) -> tuple[str, ...]:
    return tuple(
        column
        for column in candidates
        if sum(_numeric_value(row.get(column, "")) is not None for row in rows) >= min_rows
    )


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
    size_column: str | None,
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
                "size_value": (_numeric_value(row.get(size_column, "")) if size_column else None),
                "caution": row.get("注意点", ""),
                "upward_signal": row.get("上向き兆候", ""),
                "shape_label": row.get("チャート形状", ""),
                "adjustment_stability": row.get("調整/安定度", ""),
                "upward_potential": row.get("上向き余地", ""),
                "downside_safety": row.get("下落安全性", ""),
                "downside_warning": row.get("下降警戒", ""),
                "dividend_trap": row.get("配当罠警戒", ""),
                "signal_reason": row.get("上向き兆候理由", ""),
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


def _first_numeric_value(row: dict[str, str], candidates: tuple[str, ...]) -> float | None:
    for candidate in candidates:
        value = _numeric_value(row.get(candidate, ""))
        if value is not None:
            return value
    return None


def _rank_value(value: object, fallback_index: int) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return fallback_index + 1


def _score_label(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")
