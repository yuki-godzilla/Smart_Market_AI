from decimal import Decimal

from pydantic import Field

from backend.core.data_contracts import DailySnapshot, FeatureSnapshot, StrictBaseModel


class ScreeningScore(StrictBaseModel):
    """Explainable screening score for one symbol."""

    rank: int = Field(ge=1)
    symbol: str = Field(min_length=1)
    total_score: Decimal = Field(ge=0, le=100)
    momentum_score: Decimal = Field(ge=0, le=100)
    liquidity_score: Decimal = Field(ge=0, le=100)
    risk_score: Decimal = Field(ge=0, le=100)
    data_quality_score: Decimal = Field(ge=0, le=100)
    data_quality: str
    reasons: list[str] = Field(default_factory=list)


class ScreeningService:
    """Rank symbols using Feature Store Lite snapshots."""

    def score(self, snapshot: FeatureSnapshot) -> list[ScreeningScore]:
        """Return ranked screening scores for a feature snapshot."""

        scored = [_score_row(row) for row in snapshot.rows]
        ranked = sorted(scored, key=lambda row: (-row.total_score, row.symbol))
        return [row.model_copy(update={"rank": rank}) for rank, row in enumerate(ranked, start=1)]


def _score_row(row: DailySnapshot) -> ScreeningScore:
    momentum_score = _momentum_score(row)
    liquidity_score = _liquidity_score(row)
    risk_score = _risk_score(row)
    data_quality_score = _data_quality_score(row)
    total_score = _weighted_score(
        momentum_score=momentum_score,
        liquidity_score=liquidity_score,
        risk_score=risk_score,
        data_quality_score=data_quality_score,
    )
    return ScreeningScore(
        rank=1,
        symbol=row.symbol,
        total_score=total_score,
        momentum_score=momentum_score,
        liquidity_score=liquidity_score,
        risk_score=risk_score,
        data_quality_score=data_quality_score,
        data_quality=row.data_quality,
        reasons=_score_reasons(row),
    )


def _momentum_score(row: DailySnapshot) -> Decimal:
    if row.momentum_5d is None:
        return Decimal("50")
    return _clamp_score(Decimal("50") + (row.momentum_5d * Decimal("1000")))


def _liquidity_score(row: DailySnapshot) -> Decimal:
    if row.adv_20d is None:
        return Decimal("0")
    return _clamp_score((row.adv_20d / Decimal("1000000000")) * Decimal("100"))


def _risk_score(row: DailySnapshot) -> Decimal:
    volatility_penalty = (row.vol_20d or Decimal("0")) * Decimal("100")
    drawdown_penalty = (row.drawdown_20d or Decimal("0")) * Decimal("200")
    return _clamp_score(Decimal("100") - volatility_penalty - drawdown_penalty)


def _data_quality_score(row: DailySnapshot) -> Decimal:
    if row.data_quality == "OK":
        return Decimal("100")
    if row.data_quality == "WARN":
        return Decimal("60")
    return Decimal("0")


def _weighted_score(
    *,
    momentum_score: Decimal,
    liquidity_score: Decimal,
    risk_score: Decimal,
    data_quality_score: Decimal,
) -> Decimal:
    score = (
        (momentum_score * Decimal("0.30"))
        + (liquidity_score * Decimal("0.25"))
        + (risk_score * Decimal("0.25"))
        + (data_quality_score * Decimal("0.20"))
    )
    return _round_score(score)


def _score_reasons(row: DailySnapshot) -> list[str]:
    reasons: list[str] = []
    if row.momentum_5d is None:
        reasons.append("neutral_momentum:missing")
    if row.adv_20d is None:
        reasons.append("liquidity:missing")
    if row.data_quality != "OK":
        reasons.extend(row.data_quality_reasons)
    return reasons


def _clamp_score(value: Decimal) -> Decimal:
    return _round_score(min(max(value, Decimal("0")), Decimal("100")))


def _round_score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
