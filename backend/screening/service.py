from decimal import Decimal, InvalidOperation

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
    summary: str = ""
    reason_labels: list[str] = Field(default_factory=list)
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
    reasons = _score_reasons(row)
    return ScreeningScore(
        rank=1,
        symbol=row.symbol,
        total_score=total_score,
        momentum_score=momentum_score,
        liquidity_score=liquidity_score,
        risk_score=risk_score,
        data_quality_score=data_quality_score,
        data_quality=row.data_quality,
        summary=_score_summary(row, total_score),
        reason_labels=[_reason_label(reason) for reason in reasons],
        reasons=reasons,
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


def _score_summary(row: DailySnapshot, total_score: Decimal) -> str:
    if row.data_quality == "BLOCK":
        return f"{row.symbol} はデータ不足が大きいため、今回のスコアは参考度が低めです。"
    if total_score >= Decimal("75"):
        return (
            f"{row.symbol} は今回の条件では上位候補です。"
            "流動性やリスクの見やすさがスコアを支えています。"
        )
    if total_score >= Decimal("50"):
        return f"{row.symbol} は中立寄りの候補です。スコア内訳と注意点を確認してください。"
    return (
        f"{row.symbol} は今回の条件では優先度が低めです。"
        "リスクやデータ品質の注意点を確認してください。"
    )


def _reason_label(reason: str) -> str:
    static_labels = {
        "neutral_momentum:missing": "5日分の値動きデータが足りないため、勢いは中立評価です。",
        "liquidity:missing": "売買代金データが足りないため、流動性を低めに見ています。",
        "missing:momentum_5d": "5日モメンタムを計算するための履歴データが足りません。",
        "missing:return_1d": "1日リターンを計算するための履歴データが足りません。",
        "missing:drawdown_20d": "最大下落率を計算するための履歴データが足りません。",
        "missing:dividend_yield": "配当利回りデータが取得できていません。",
        "missing:market_cap_jpy": "時価総額データが取得できていません。",
    }
    if reason in static_labels:
        return static_labels[reason]
    if reason.startswith("partial_data_completeness:"):
        return _partial_data_completeness_label(reason)
    return f"確認が必要なデータ品質メモ: {reason}"


def _partial_data_completeness_label(reason: str) -> str:
    _, _, raw_value = reason.partition(":")
    try:
        percent = (Decimal(raw_value) * Decimal("100")).quantize(Decimal("1"))
    except InvalidOperation:
        return "期待する履歴データが一部不足しています。"
    return f"期待する履歴データのうち {percent}% 程度しかそろっていません。"


def _clamp_score(value: Decimal) -> Decimal:
    return _round_score(min(max(value, Decimal("0")), Decimal("100")))


def _round_score(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))
