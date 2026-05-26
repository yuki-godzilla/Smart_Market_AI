from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field

from backend.core.config import ScoringWeightsConfig
from backend.core.data_contracts import StrictBaseModel
from backend.forecast import ForecastConsensus
from backend.screening import ScreeningScore

InvestmentScoreBand = Literal["STRONG", "BALANCED", "CAUTION", "REVIEW"]


class InvestmentScoreBreakdown(StrictBaseModel):
    """Contribution from one deterministic input signal."""

    component: str = Field(min_length=1)
    input_score: Decimal = Field(ge=0, le=100)
    weight: Decimal = Field(ge=0, le=1)
    contribution: Decimal = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class InvestmentScoreInput(StrictBaseModel):
    """Inputs used to compute a Phase 15 investment-support score."""

    screening_score: ScreeningScore
    forecast_consensus: ForecastConsensus | None = None
    risk_signal_score: Decimal | None = Field(default=None, ge=0, le=100)


class InvestmentScore(StrictBaseModel):
    """Overall investment-support score for one symbol.

    This contract organizes decision-support signals. It is not a buy/sell
    recommendation and does not send orders.
    """

    rank: int = Field(ge=1)
    symbol: str = Field(min_length=1)
    total_score: Decimal = Field(ge=0, le=100)
    score_band: InvestmentScoreBand
    screening_score: Decimal = Field(ge=0, le=100)
    forecast_agreement_score: Decimal = Field(ge=0, le=100)
    upside_signal_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    downside_signal_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    direction_net_score: Decimal = Field(default=Decimal("50"), ge=0, le=100)
    direction_signal_label: str = "UNKNOWN"
    forecast_return_pct: Decimal = Decimal("0")
    up_model_count: int = Field(default=0, ge=0)
    down_model_count: int = Field(default=0, ge=0)
    flat_model_count: int = Field(default=0, ge=0)
    data_quality_score: Decimal = Field(ge=0, le=100)
    risk_signal_score: Decimal | None = Field(default=None, ge=0, le=100)
    forecast_agreement: str = ""
    data_quality: str = Field(min_length=1)
    breakdown: list[InvestmentScoreBreakdown]
    warnings: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    decision_support_note: str = "Decision-support score only; not a buy/sell recommendation."


class InvestmentScoringService:
    """Combine screening, forecast, data quality, and future risk signals."""

    def __init__(self, weights: ScoringWeightsConfig | None = None) -> None:
        self.weights = weights or ScoringWeightsConfig()

    def score(
        self,
        screening_scores: list[ScreeningScore],
        *,
        forecast_consensus_by_symbol: dict[str, ForecastConsensus] | None = None,
        risk_signal_score_by_symbol: dict[str, Decimal] | None = None,
    ) -> list[InvestmentScore]:
        """Return ranked investment-support scores without changing ScreeningScore."""

        forecasts = forecast_consensus_by_symbol or {}
        risk_scores = risk_signal_score_by_symbol or {}
        scored = [
            _score_input(
                InvestmentScoreInput(
                    screening_score=screening_score,
                    forecast_consensus=forecasts.get(screening_score.symbol),
                    risk_signal_score=risk_scores.get(
                        screening_score.symbol,
                        screening_score.risk_score,
                    ),
                ),
                weights=self.weights,
            )
            for screening_score in screening_scores
        ]
        ranked = sorted(scored, key=lambda row: (-row.total_score, row.symbol))
        return [row.model_copy(update={"rank": rank}) for rank, row in enumerate(ranked, start=1)]


def _score_input(
    score_input: InvestmentScoreInput,
    *,
    weights: ScoringWeightsConfig,
) -> InvestmentScore:
    screening = score_input.screening_score
    forecast_agreement = _forecast_agreement(score_input)
    forecast_score = _forecast_agreement_score(forecast_agreement)
    direction_signal = _direction_signal_values(score_input.forecast_consensus)
    data_quality_score = screening.data_quality_score
    risk_signal_score = score_input.risk_signal_score

    components = [
        _component(
            "screening",
            screening.total_score,
            _weight_decimal(weights.screening),
            _screening_reasons(screening),
        ),
        _component(
            "forecast_agreement",
            forecast_score,
            _weight_decimal(weights.forecast_agreement),
            _forecast_reasons(forecast_agreement, score_input.forecast_consensus),
        ),
        _component(
            "data_quality",
            data_quality_score,
            _weight_decimal(weights.data_quality),
            _data_quality_reasons(screening),
        ),
        _component(
            "risk_signal",
            risk_signal_score if risk_signal_score is not None else Decimal("50"),
            _weight_decimal(weights.risk_signal),
            _risk_reasons(risk_signal_score),
        ),
    ]
    total_score = _round_score(
        sum((component.contribution for component in components), Decimal("0"))
    )
    reasons = [reason for component in components for reason in component.reasons]
    warnings = _warnings(reasons)

    return InvestmentScore(
        rank=1,
        symbol=screening.symbol,
        total_score=total_score,
        score_band=_score_band(total_score, warnings),
        screening_score=screening.total_score,
        forecast_agreement_score=forecast_score,
        upside_signal_score=direction_signal["upside_signal_score"],
        downside_signal_score=direction_signal["downside_signal_score"],
        direction_net_score=direction_signal["direction_net_score"],
        direction_signal_label=str(direction_signal["direction_signal_label"]),
        forecast_return_pct=direction_signal["forecast_return_pct"],
        up_model_count=int(direction_signal["up_model_count"]),
        down_model_count=int(direction_signal["down_model_count"]),
        flat_model_count=int(direction_signal["flat_model_count"]),
        data_quality_score=data_quality_score,
        risk_signal_score=risk_signal_score,
        forecast_agreement=forecast_agreement,
        data_quality=screening.data_quality,
        breakdown=components,
        warnings=warnings,
        reasons=reasons,
    )


def _component(
    component: str,
    input_score: Decimal,
    weight: Decimal,
    reasons: list[str],
) -> InvestmentScoreBreakdown:
    return InvestmentScoreBreakdown(
        component=component,
        input_score=_round_score(input_score),
        weight=weight,
        contribution=_round_score(input_score * weight),
        reasons=reasons,
    )


def _forecast_agreement(score_input: InvestmentScoreInput) -> str:
    if score_input.forecast_consensus is not None:
        return score_input.forecast_consensus.agreement
    if score_input.screening_score.forecast_agreement:
        return score_input.screening_score.forecast_agreement
    return "UNKNOWN"


def _forecast_agreement_score(agreement: str) -> Decimal:
    scores = {
        "HIGH": Decimal("90"),
        "MEDIUM": Decimal("70"),
        "LOW": Decimal("40"),
        "UNKNOWN": Decimal("50"),
    }
    return scores.get(agreement, Decimal("50"))


def _direction_signal_values(
    forecast_consensus: ForecastConsensus | None,
) -> dict[str, Decimal | int | str]:
    if forecast_consensus is None:
        return {
            "upside_signal_score": Decimal("50"),
            "downside_signal_score": Decimal("50"),
            "direction_net_score": Decimal("50"),
            "direction_signal_label": "UNKNOWN",
            "forecast_return_pct": Decimal("0"),
            "up_model_count": 0,
            "down_model_count": 0,
            "flat_model_count": 0,
        }
    return {
        "upside_signal_score": getattr(forecast_consensus, "upside_signal_score", Decimal("50")),
        "downside_signal_score": getattr(
            forecast_consensus, "downside_signal_score", Decimal("50")
        ),
        "direction_net_score": getattr(forecast_consensus, "direction_net_score", Decimal("50")),
        "direction_signal_label": getattr(forecast_consensus, "direction_signal_label", "UNKNOWN"),
        "forecast_return_pct": getattr(forecast_consensus, "forecast_return_pct", Decimal("0")),
        "up_model_count": getattr(forecast_consensus, "up_model_count", 0),
        "down_model_count": getattr(forecast_consensus, "down_model_count", 0),
        "flat_model_count": getattr(forecast_consensus, "flat_model_count", 0),
    }


def _screening_reasons(screening: ScreeningScore) -> list[str]:
    if screening.total_score >= Decimal("70"):
        return ["screening:positive"]
    if screening.total_score >= Decimal("50"):
        return ["screening:neutral"]
    return ["screening:weak"]


def _forecast_reasons(
    agreement: str,
    forecast_consensus: ForecastConsensus | None,
) -> list[str]:
    reasons = [f"forecast_agreement:{agreement.lower()}"]
    if agreement == "LOW":
        reasons.append("model_disagreement:high")
    if agreement == "UNKNOWN":
        reasons.append("model_agreement:unknown")
    if forecast_consensus is not None and forecast_consensus.model_count < 2:
        reasons.append("model_count:insufficient")
    return reasons


def _data_quality_reasons(screening: ScreeningScore) -> list[str]:
    reasons: list[str] = []
    if screening.data_quality == "WARN":
        reasons.append("data_quality:warn")
    elif screening.data_quality == "BLOCK":
        reasons.append("data_quality:block")
    reasons.extend(screening.reasons)
    return reasons


def _risk_reasons(risk_signal_score: Decimal | None) -> list[str]:
    if risk_signal_score is None:
        return ["risk_signal:not_connected"]
    if risk_signal_score < Decimal("50"):
        return ["risk_signal:caution"]
    return ["risk_signal:available"]


def _warnings(reasons: list[str]) -> list[str]:
    warning_prefixes = (
        "data_quality:warn",
        "data_quality:block",
        "model_disagreement:",
        "model_count:insufficient",
    )
    return [reason for reason in reasons if reason.startswith(warning_prefixes)]


def _score_band(total_score: Decimal, warnings: list[str]) -> InvestmentScoreBand:
    if any(warning == "data_quality:block" for warning in warnings):
        return "REVIEW"
    if total_score >= Decimal("75") and not warnings:
        return "STRONG"
    if warnings and total_score < Decimal("65"):
        return "CAUTION"
    if total_score >= Decimal("55"):
        return "BALANCED"
    if total_score >= Decimal("40"):
        return "CAUTION"
    return "REVIEW"


def _round_score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _weight_decimal(value: float) -> Decimal:
    return Decimal(str(value))
