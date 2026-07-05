from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True)
class ReversalExpectation:
    reversal_expectation_score: Decimal
    reversal_expectation_label: str
    reversal_expectation_reason: str
    reversal_pullback_score: Decimal
    reversal_forecast_score: Decimal
    reversal_safety_score: Decimal
    reversal_quality_score: Decimal
    reversal_setup_score: Decimal

    def as_row(self) -> dict[str, str]:
        return {
            key: _format(value) if isinstance(value, Decimal) else value
            for key, value in asdict(self).items()
        }


def calculate_reversal_expectation(row: Mapping[str, object]) -> ReversalExpectation:
    drawdown = abs(_number(row, "drawdown_20d", "high_20d_gap_pct", default=Decimal("0")))
    momentum = _number(row, "momentum_5d", "return_5d", "price_change_5d", default=Decimal("0"))
    forecast_return = _number(row, "forecast_return_pct", default=Decimal("0"))
    up_models = _number(row, "up_model_count", default=Decimal("0"))
    down_models = _number(row, "down_model_count", default=Decimal("0"))
    upside = _number(row, "upside_signal_score", default=Decimal("50"))
    downside = _number(row, "downside_signal_score", default=Decimal("50"))
    risk = _number(row, "risk_signal_score", default=Decimal("50"))
    quality = _number(row, "data_quality_score", default=Decimal("50"))

    pullback = _pullback_score(drawdown, momentum)
    forecast = _clamp(
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
    volatility = _number(row, "volatility_20d", "volatility", default=Decimal("25"))
    volatility_score = _clamp(Decimal("100") - max(Decimal("0"), volatility - Decimal("20")) * 2)
    safety = _clamp(
        (Decimal("100") - downside) * Decimal("0.45")
        + risk * Decimal("0.35")
        + volatility_score * Decimal("0.20")
    )
    screening = _number(row, "screening_score", default=quality)
    database_fit = _number(row, "database_fit_score", default=quality)
    metadata = _number(row, "metadata_confidence_score", default=quality)
    quality_score = _clamp(
        screening * Decimal("0.35")
        + quality * Decimal("0.35")
        + database_fit * Decimal("0.15")
        + metadata * Decimal("0.15")
    )
    setup = _setup_score(momentum, downside, drawdown)
    raw = (
        pullback * Decimal("0.30")
        + forecast * Decimal("0.30")
        + safety * Decimal("0.20")
        + quality_score * Decimal("0.10")
        + setup * Decimal("0.10")
    )

    caps: list[Decimal] = []
    warnings = str(row.get("warnings") or "").lower()
    if "data_quality:block" in warnings or "data quality block" in warnings:
        caps.append(Decimal("0"))
    if quality < 60:
        caps.append(Decimal("55"))
    if downside >= 80:
        caps.append(Decimal("45"))
    elif downside >= 70:
        caps.append(Decimal("60"))
    if risk < 40:
        caps.append(Decimal("55"))
    if drawdown >= 35:
        caps.append(Decimal("45"))
    if forecast_return <= 0:
        caps.append(Decimal("50"))
    if up_models <= 0:
        caps.append(Decimal("50"))
    if momentum <= -8:
        caps.append(Decimal("55"))
    if drawdown < 3 and momentum > 3:
        caps.append(Decimal("55"))
    score = _clamp(min([raw, *caps]) if caps else raw).quantize(Decimal("0.01"))
    label = reversal_expectation_label(score)
    reason = _reason(drawdown, forecast_return, downside, quality, score)
    return ReversalExpectation(
        reversal_expectation_score=score,
        reversal_expectation_label=label,
        reversal_expectation_reason=reason,
        reversal_pullback_score=pullback.quantize(Decimal("0.01")),
        reversal_forecast_score=forecast.quantize(Decimal("0.01")),
        reversal_safety_score=safety.quantize(Decimal("0.01")),
        reversal_quality_score=quality_score.quantize(Decimal("0.01")),
        reversal_setup_score=setup.quantize(Decimal("0.01")),
    )


def reversal_expectation_label(score: Decimal) -> str:
    if score >= 80:
        return "反転期待 高"
    if score >= 65:
        return "反転期待 中"
    if score >= 50:
        return "観察候補"
    if score >= 35:
        return "反転材料弱め"
    return "反転期待低め"


def _pullback_score(drawdown: Decimal, momentum: Decimal) -> Decimal:
    points = (
        Decimal("30")
        if drawdown < 3
        else (
            Decimal("60")
            if drawdown < 6
            else (
                Decimal("90")
                if drawdown < 12
                else (
                    Decimal("80")
                    if drawdown < 18
                    else (
                        Decimal("60")
                        if drawdown < 25
                        else Decimal("35") if drawdown < 35 else Decimal("20")
                    )
                )
            )
        )
    )
    if momentum <= -8:
        points -= 25
    elif momentum < 0:
        points += 5
    elif momentum > 5:
        points -= 15
    return _clamp(points)


def _setup_score(momentum: Decimal, downside: Decimal, drawdown: Decimal) -> Decimal:
    score = Decimal("50")
    if drawdown >= 3:
        score += 15
    if Decimal("-3") <= momentum <= Decimal("2"):
        score += 20
    elif momentum <= -8:
        score -= 30
    elif momentum > 5:
        score -= 10
    score += (Decimal("60") - downside) * Decimal("0.25")
    return _clamp(score)


def _model_direction_score(up: Decimal, down: Decimal) -> Decimal:
    total = up + down
    return Decimal("50") if total <= 0 else _clamp(up / total * 100)


def _reason(
    drawdown: Decimal,
    forecast_return: Decimal,
    downside: Decimal,
    quality: Decimal,
    score: Decimal,
) -> str:
    if quality < 60:
        return "データ信頼度が低いため上限を設けています。追加確認が必要です。"
    if downside >= 70:
        return "戻り材料はありますが、下降警戒が高いため下落理由の確認を優先します。"
    if drawdown >= 3 and forecast_return > 0 and score >= 50:
        return "直近は調整中ですが予測方向は上向きです。下落理由を確認します。"
    return "押し目状態、予測余地、安全性を合わせた深掘り確認の優先度です。"


def _number(row: Mapping[str, object], *keys: str, default: Decimal) -> Decimal:
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
    return default


def _scale(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    if high == low:
        return Decimal("50")
    return _clamp((value - low) / (high - low) * 100)


def _clamp(value: Decimal) -> Decimal:
    return min(Decimal("100"), max(Decimal("0"), value))


def _format(value: Decimal) -> str:
    return format(value.normalize(), "f")
