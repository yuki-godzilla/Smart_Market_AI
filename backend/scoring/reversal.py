from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True)
class ReversalExpectation:
    reversal_expectation_score: Decimal
    reversal_expectation_label: str
    reversal_expectation_reason: str
    reversal_chart_shape_score: Decimal
    reversal_forecast_score: Decimal
    reversal_safety_score: Decimal
    reversal_pullback_score: Decimal
    reversal_quality_score: Decimal
    reversal_material_score: Decimal
    reversal_trap_warning: str
    reversal_chart_shape_label: str
    dividend_trap_warning: str
    dividend_safety_score: Decimal
    dividend_yield_spike_flag: bool
    dividend_sustainability_label: str
    pullback_rebound_score: Decimal
    bottoming_score: Decimal
    range_breakout_score: Decimal
    accumulation_setup_score: Decimal
    dangerous_shape_penalty: Decimal
    # v1 compatibility: consumers may still read this field.
    reversal_setup_score: Decimal

    def as_row(self) -> dict[str, str | bool]:
        return {
            key: _format(value) if isinstance(value, Decimal) else value
            for key, value in asdict(self).items()
        }


def calculate_reversal_expectation(row: Mapping[str, object]) -> ReversalExpectation:
    drawdown = abs(_number(row, "drawdown_20d", "high_20d_gap_pct", default=Decimal("0")))
    drawdown_60d = abs(_number(row, "drawdown_60d", "high_60d_gap_pct", default=drawdown))
    momentum = _number(row, "momentum_5d", "return_5d", "price_change_5d", default=Decimal("0"))
    forecast_return = _number(row, "forecast_return_pct", default=Decimal("0"))
    up_models = _number(row, "up_model_count", default=Decimal("0"))
    down_models = _number(row, "down_model_count", default=Decimal("0"))
    upside = _number(row, "upside_signal_score", default=Decimal("50"))
    downside = _number(row, "downside_signal_score", default=Decimal("50"))
    risk = _number(row, "risk_signal_score", "risk_score", default=Decimal("50"))
    data_quality = _number(row, "data_quality_score", default=Decimal("50"))

    shape_scores = _chart_shape_scores(
        row,
        drawdown=drawdown,
        momentum=momentum,
        forecast_return=forecast_return,
        downside=downside,
        risk=risk,
    )
    shape_label = _chart_shape_label(
        row,
        shape_scores=shape_scores,
        drawdown=drawdown,
        momentum=momentum,
        forecast_return=forecast_return,
        up_models=up_models,
        downside=downside,
        risk=risk,
    )
    chart_shape = _chart_shape_score(row, shape_label, shape_scores)
    pullback = _pullback_score(drawdown, momentum)
    forecast = _forecast_score(row, forecast_return, up_models, down_models, upside, data_quality)
    safety = _safety_score(row, downside, risk)
    dividend = _dividend_assessment(row, drawdown_60d)
    quality = _quality_score(row, data_quality, dividend.safety_score)
    material = _material_score(row, forecast_return, up_models, upside)

    raw = (
        chart_shape * Decimal("0.30")
        + forecast * Decimal("0.25")
        + safety * Decimal("0.20")
        + pullback * Decimal("0.10")
        + quality * Decimal("0.10")
        + material * Decimal("0.05")
    )
    caps: list[Decimal] = []
    warnings = str(row.get("warnings") or "").lower()
    if "data_quality:block" in warnings or "data quality block" in warnings:
        caps.append(Decimal("0"))
    if data_quality < 60:
        caps.append(Decimal("55"))
    if downside >= 80:
        caps.append(Decimal("45"))
    elif downside >= 70:
        caps.append(Decimal("60"))
    if risk < 40 or drawdown >= 35:
        caps.append(Decimal("45"))
    if forecast_return <= 0 or up_models <= 0:
        caps.append(Decimal("50"))
    if shape_label == "落ちるナイフ注意":
        caps.append(Decimal("45"))
    elif shape_label in {"上昇済み・兆候薄め", "反転材料弱め"}:
        caps.append(Decimal("55"))
    if dividend.score_cap is not None:
        caps.append(dividend.score_cap)

    score = _clamp(min([raw, *caps]) if caps else raw).quantize(Decimal("0.01"))
    trap_warning = _trap_warning(shape_label, downside, risk, data_quality)
    return ReversalExpectation(
        reversal_expectation_score=score,
        reversal_expectation_label=reversal_expectation_label(score),
        reversal_expectation_reason=_reason(
            shape_label, forecast_return, safety, data_quality, dividend.warning
        ),
        reversal_chart_shape_score=_rounded(chart_shape),
        reversal_forecast_score=_rounded(forecast),
        reversal_safety_score=_rounded(safety),
        reversal_pullback_score=_rounded(pullback),
        reversal_quality_score=_rounded(quality),
        reversal_material_score=_rounded(material),
        reversal_trap_warning=trap_warning,
        reversal_chart_shape_label=shape_label,
        dividend_trap_warning=dividend.warning,
        dividend_safety_score=_rounded(dividend.safety_score),
        dividend_yield_spike_flag=dividend.yield_spike,
        dividend_sustainability_label=dividend.sustainability_label,
        pullback_rebound_score=_rounded(shape_scores["押し目反発待ち"]),
        bottoming_score=_rounded(shape_scores["底打ち接近"]),
        range_breakout_score=_rounded(shape_scores["横ばい上放れ候補"]),
        accumulation_setup_score=_rounded(shape_scores["蓄積上昇準備"]),
        dangerous_shape_penalty=_rounded(shape_scores["dangerous_penalty"]),
        reversal_setup_score=_rounded(chart_shape),
    )


def reversal_expectation_label(score: Decimal) -> str:
    if score >= 80:
        return "上向き兆候 高"
    if score >= 65:
        return "上向き兆候 中"
    if score >= 50:
        return "観察候補"
    if score >= 35:
        return "反転材料弱め"
    return "上向き兆候 低"


def upward_signal_display_label(value: object) -> str:
    """Normalize labels saved before the public-name migration."""

    return str(value or "").replace("反転期待", "上向き兆候")


@dataclass(frozen=True)
class _DividendAssessment:
    safety_score: Decimal
    warning: str
    yield_spike: bool
    sustainability_label: str
    score_cap: Decimal | None


def _chart_shape_label(
    row: Mapping[str, object],
    *,
    shape_scores: Mapping[str, Decimal],
    drawdown: Decimal,
    momentum: Decimal,
    forecast_return: Decimal,
    up_models: Decimal,
    downside: Decimal,
    risk: Decimal,
) -> str:
    recent_low_break = _truthy(row, "recent_low_break", "new_low_flag")
    if (
        drawdown >= 35
        or downside >= 80
        or risk < 40
        or (recent_low_break and momentum <= -3)
        or momentum <= -8
    ):
        return "落ちるナイフ注意"
    if _data_is_insufficient(row):
        return "データ不足・要確認"
    if drawdown < 3 and momentum > 3:
        return "上昇済み・兆候薄め"
    if forecast_return <= 0 or up_models <= 0:
        return "反転材料弱め"
    if drawdown >= 20 and momentum <= 0:
        return "売られすぎ反発狙い"
    candidates = {
        label: score for label, score in shape_scores.items() if label != "dangerous_penalty"
    }
    label, best_score = max(candidates.items(), key=lambda item: item[1])
    return label if best_score >= 58 else "反転材料弱め"


def _chart_shape_scores(
    row: Mapping[str, object],
    *,
    drawdown: Decimal,
    momentum: Decimal,
    forecast_return: Decimal,
    downside: Decimal,
    risk: Decimal,
) -> dict[str, Decimal]:
    return_20d = _number(row, "return_20d", "price_change_20d", default=momentum)
    volatility = _number(row, "volatility_20d", "volatility", default=Decimal("25"))
    higher_low = _truthy(row, "higher_low_flag", "recent_higher_low")
    volume_recovery = _truthy(row, "volume_recovery_flag", "reversal_volume_confirmed")

    pullback = Decimal("30")
    if Decimal("5") <= drawdown < Decimal("18") and Decimal("-5") <= momentum <= Decimal("2"):
        pullback = Decimal("82")
    if higher_low:
        pullback += 8

    bottoming = Decimal("30")
    if drawdown >= 10 and Decimal("-3") <= momentum <= Decimal("3"):
        bottoming = Decimal("84")
    if higher_low:
        bottoming += 10
    if volume_recovery:
        bottoming += 6

    range_breakout = Decimal("30")
    if abs(return_20d) <= 5 and drawdown <= 10 and forecast_return >= 2 and downside < 65:
        range_breakout = Decimal("78")
    if volatility <= 22:
        range_breakout += 6
    if volume_recovery:
        range_breakout += 6

    accumulation = Decimal("30")
    if (
        abs(return_20d) <= 4
        and drawdown <= 8
        and volatility <= 20
        and forecast_return > 0
        and downside < 60
        and risk >= 55
    ):
        accumulation = Decimal("86")
    if higher_low:
        accumulation += 5

    dangerous = Decimal("0")
    if drawdown >= 35 or downside >= 80 or risk < 40 or momentum <= -8:
        dangerous = Decimal("45")
    elif drawdown >= 25 or downside >= 70 or momentum <= -5:
        dangerous = Decimal("20")
    return {
        "押し目反発待ち": _clamp(pullback - dangerous),
        "底打ち接近": _clamp(bottoming - dangerous),
        "横ばい上放れ候補": _clamp(range_breakout - dangerous),
        "蓄積上昇準備": _clamp(accumulation - dangerous),
        "dangerous_penalty": dangerous,
    }


def _chart_shape_score(
    row: Mapping[str, object],
    label: str,
    shape_scores: Mapping[str, Decimal],
) -> Decimal:
    base = {
        "押し目反発待ち": shape_scores["押し目反発待ち"],
        "底打ち接近": shape_scores["底打ち接近"],
        "横ばい上放れ候補": shape_scores["横ばい上放れ候補"],
        "蓄積上昇準備": shape_scores["蓄積上昇準備"],
        "売られすぎ反発狙い": Decimal("66"),
        "上昇済み・兆候薄め": Decimal("38"),
        "落ちるナイフ注意": Decimal("20"),
        "反転材料弱め": Decimal("45"),
        "データ不足・要確認": Decimal("30"),
    }[label]
    rsi = _optional_number(row, "rsi_14", "rsi")
    if rsi is not None:
        if Decimal("28") <= rsi <= Decimal("45"):
            base += 7
        elif rsi < 20 or rsi > 70:
            base -= 8
    if _truthy(row, "higher_low_flag", "recent_higher_low"):
        base += 7
    if _truthy(row, "volume_recovery_flag", "reversal_volume_confirmed"):
        base += 5
    return _clamp(base)


def _forecast_score(
    row: Mapping[str, object],
    forecast_return: Decimal,
    up_models: Decimal,
    down_models: Decimal,
    upside: Decimal,
    quality: Decimal,
) -> Decimal:
    return _clamp(
        _scale(forecast_return, Decimal("-5"), Decimal("12")) * Decimal("0.40")
        + _model_direction_score(up_models, down_models) * Decimal("0.25")
        + _number(
            row,
            "advanced_forecast_upside_score",
            default=_scale(forecast_return, Decimal("-5"), Decimal("12")),
        )
        * Decimal("0.15")
        + _number(row, "advanced_forecast_quality_score", default=quality) * Decimal("0.10")
        + upside * Decimal("0.10")
    )


def _safety_score(row: Mapping[str, object], downside: Decimal, risk: Decimal) -> Decimal:
    volatility = _number(row, "volatility_20d", "volatility", default=Decimal("25"))
    volatility_score = _clamp(Decimal("100") - max(Decimal("0"), volatility - Decimal("20")) * 2)
    return _clamp(
        (Decimal("100") - downside) * Decimal("0.45")
        + risk * Decimal("0.35")
        + volatility_score * Decimal("0.20")
    )


def _quality_score(
    row: Mapping[str, object], data_quality: Decimal, dividend_safety: Decimal
) -> Decimal:
    screening = _number(row, "screening_score", default=data_quality)
    database_fit = _number(row, "database_fit_score", default=data_quality)
    metadata = _number(row, "metadata_confidence_score", default=data_quality)
    business_quality = _clamp(
        screening * Decimal("0.35")
        + data_quality * Decimal("0.35")
        + database_fit * Decimal("0.15")
        + metadata * Decimal("0.15")
    )
    yield_pct = _yield_percent(row)
    if yield_pct < 3:
        return business_quality
    return _clamp(business_quality * Decimal("0.70") + dividend_safety * Decimal("0.30"))


def _material_score(
    row: Mapping[str, object],
    forecast_return: Decimal,
    up_models: Decimal,
    upside: Decimal,
) -> Decimal:
    explicit = _optional_number(
        row, "research_material_score", "news_material_score", "catalyst_score"
    )
    if explicit is not None:
        return _clamp(explicit)
    score = Decimal("35")
    if forecast_return > 0:
        score += 20
    if up_models >= 2:
        score += 20
    if upside >= 60:
        score += 15
    return _clamp(score)


def _dividend_assessment(row: Mapping[str, object], drawdown_60d: Decimal) -> _DividendAssessment:
    asset_type = str(row.get("asset_type") or row.get("product_type") or "").strip().lower()
    if asset_type in {"etf", "fund", "mutual_fund", "投信"}:
        return _DividendAssessment(
            Decimal("70"), "ETFには個別株の配当罠判定を適用しません", False, "対象外", None
        )
    yield_pct = _yield_percent(row)
    if yield_pct < 3:
        return _DividendAssessment(Decimal("70"), "該当なし", False, "通常", None)

    payout = _optional_number(row, "payout_ratio", "dividend_payout_ratio")
    eps_growth = _optional_number(row, "eps_growth_pct", "earnings_growth_pct")
    operating_cf = _optional_number(row, "operating_cash_flow", "operating_cf")
    free_cf = _optional_number(row, "free_cash_flow", "free_cf")
    known = [value for value in (payout, eps_growth, operating_cf, free_cf) if value is not None]
    score = Decimal("70")
    danger = False
    if not known:
        score = Decimal("45")
    if payout is not None:
        if payout > 100:
            score -= 35
            danger = True
        elif payout > 80:
            score -= 20
    if eps_growth is not None and eps_growth < 0:
        score -= 15
    if operating_cf is not None and operating_cf <= 0:
        score -= 25
        danger = True
    if free_cf is not None and free_cf <= 0:
        score -= 15
    if yield_pct >= 8:
        score -= 15

    spike = yield_pct >= 6 and drawdown_60d >= 20
    if spike:
        score -= 20
    score = _clamp(score)
    if danger:
        return _DividendAssessment(score, "減配リスク高", spike, "維持に強い注意", Decimal("45"))
    if spike:
        return _DividendAssessment(
            score, "株価下落による利回り急上昇", True, "要確認", Decimal("55")
        )
    if not known:
        return _DividendAssessment(score, "配当安全性未確認", False, "材料不足", Decimal("60"))
    if score < 55:
        return _DividendAssessment(score, "配当維持に注意", False, "要確認", Decimal("60"))
    return _DividendAssessment(score, "目立つ警告なし", False, "おおむね安定", None)


def _yield_percent(row: Mapping[str, object]) -> Decimal:
    value = _number(row, "dividend_yield_pct", "dividend_yield", default=Decimal("0"))
    if Decimal("0") < value <= Decimal("1"):
        return value * 100
    return value


def _pullback_score(drawdown: Decimal, momentum: Decimal) -> Decimal:
    if drawdown < 3:
        points = Decimal("30")
    elif drawdown < 6:
        points = Decimal("60")
    elif drawdown < 12:
        points = Decimal("90")
    elif drawdown < 18:
        points = Decimal("80")
    elif drawdown < 25:
        points = Decimal("60")
    elif drawdown < 35:
        points = Decimal("35")
    else:
        points = Decimal("20")
    if momentum <= -8:
        points -= 25
    elif momentum < 0:
        points += 5
    elif momentum > 5:
        points -= 15
    return _clamp(points)


def _model_direction_score(up: Decimal, down: Decimal) -> Decimal:
    total = up + down
    return Decimal("50") if total <= 0 else _clamp(up / total * 100)


def _trap_warning(shape_label: str, downside: Decimal, risk: Decimal, data_quality: Decimal) -> str:
    reasons: list[str] = []
    if shape_label == "落ちるナイフ注意":
        reasons.append("下落継続")
    if downside >= 70 or risk < 40:
        reasons.append("下落安全性")
    if data_quality < 60:
        reasons.append("データ品質")
    return "・".join(reasons) if reasons else "目立つ警告なし"


def _reason(
    shape_label: str,
    forecast_return: Decimal,
    safety: Decimal,
    data_quality: Decimal,
    dividend_warning: str,
) -> str:
    parts = [f"形状は「{shape_label}」"]
    parts.append("予測は上向き" if forecast_return > 0 else "予測の上向き材料は不足")
    parts.append("下落安全性を確認" if safety < 55 else "下落安全性は相対的に良好")
    if data_quality < 60:
        parts.append("データ品質が低いため上限あり")
    if dividend_warning not in {"該当なし", "目立つ警告なし"}:
        parts.append(dividend_warning)
    return (
        "。".join(parts)
        + "。上向きの確定や買い推奨ではなく、下落理由と危険度を深掘りする候補です。"
    )


def _data_is_insufficient(row: Mapping[str, object]) -> bool:
    warnings = str(row.get("warnings") or "").lower()
    data_quality = _number(row, "data_quality_score", default=Decimal("50"))
    return data_quality < 40 or "data_quality:block" in warnings or "insufficient" in warnings


def _truthy(row: Mapping[str, object], *keys: str) -> bool:
    for key in keys:
        value = row.get(key)
        if isinstance(value, bool):
            return value
        if str(value or "").strip().lower() in {"1", "true", "yes", "on", "あり", "はい"}:
            return True
    return False


def _optional_number(row: Mapping[str, object], *keys: str) -> Decimal | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            number = Decimal(str(value).replace("%", "").replace(",", "").strip())
        except (InvalidOperation, ValueError):
            continue
        if number.is_finite():
            return number
    return None


def _number(row: Mapping[str, object], *keys: str, default: Decimal) -> Decimal:
    value = _optional_number(row, *keys)
    return default if value is None else value


def _scale(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    if high == low:
        return Decimal("50")
    return _clamp((value - low) / (high - low) * 100)


def _clamp(value: Decimal) -> Decimal:
    return min(Decimal("100"), max(Decimal("0"), value))


def _rounded(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _format(value: Decimal) -> str:
    return format(value.normalize(), "f")
