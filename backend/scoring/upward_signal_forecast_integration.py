from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping

from pydantic import ConfigDict, Field

from backend.core.data_contracts import StrictBaseModel
from backend.forecast.evaluation import CONSENSUS_MODEL_NAME, ForecastValidationPoint
from backend.scoring.reversal import calculate_reversal_expectation


class UpwardSignalForecastIntegration(StrictBaseModel):
    """Evaluation-only forecast contribution for the Upward Signal axis.

    This contract deliberately does not replace the runtime ranking score. It
    makes the existing forecast consensus evidence comparable with the chart
    shape score before any guarded adoption decision is considered.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    forecast_upside_score: Decimal = Field(ge=0, le=100)
    downside_safety_score: Decimal = Field(ge=0, le=100)
    direction_agreement_score: Decimal = Field(ge=0, le=100)
    confidence_score: Decimal = Field(ge=0, le=100)
    forecast_integration_score: Decimal = Field(ge=0, le=100)
    score_ceiling: Decimal = Field(ge=0, le=100)
    score_ceiling_reason: str = Field(min_length=1)
    consensus_confidence: str = Field(min_length=1)
    model_disagreement_pct: Decimal = Field(ge=0)
    model_count: int = Field(ge=0)
    up_model_count: int = Field(ge=0)
    down_model_count: int = Field(ge=0)
    flat_model_count: int = Field(ge=0)
    predicted_return: Decimal | None = None
    predicted_return_lower: Decimal | None = None
    predicted_return_upper: Decimal | None = None
    warnings: list[str] = Field(default_factory=list)


class UpwardSignalForecastCase(StrictBaseModel):
    """One symbol-level comparison between current and forecast-aware scoring."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    upward_signal_score: Decimal = Field(ge=0, le=100)
    forecast_integration_score: Decimal = Field(ge=0, le=100)
    score_delta: Decimal
    chart_shape_score: Decimal = Field(ge=0, le=100)
    forecast_score: Decimal = Field(ge=0, le=100)
    downside_safety_score: Decimal = Field(ge=0, le=100)
    confidence: str = Field(min_length=1)
    model_disagreement_pct: Decimal = Field(ge=0)
    warning_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class UpwardSignalForecastValidationCase(StrictBaseModel):
    """Forecast contribution reconstructed at one point-in-time origin."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    target_at: datetime
    actual_return: Decimal
    predicted_return: Decimal
    forecast_integration_score: Decimal = Field(ge=0, le=100)
    confidence: str = Field(min_length=1)
    model_disagreement_pct: Decimal = Field(ge=0)
    direction_agreement_score: Decimal = Field(ge=0, le=100)
    warning_count: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class UpwardSignalForecastValidationSummary(StrictBaseModel):
    """Grouped outcome metrics for adoption review, not runtime scoring."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    group_type: str = Field(min_length=1)
    group_value: str = Field(min_length=1)
    horizon_days: int = Field(ge=0)
    case_count: int = Field(ge=0)
    positive_actual_rate: Decimal = Field(ge=0, le=1)
    direction_accuracy: Decimal = Field(ge=0, le=1)
    mean_actual_return: Decimal
    mean_predicted_return: Decimal
    mean_integration_score: Decimal = Field(ge=0, le=100)
    warning_case_rate: Decimal = Field(ge=0, le=1)


@dataclass(frozen=True)
class _ForecastEvidence:
    predicted_return: Decimal | None
    predicted_return_lower: Decimal | None
    predicted_return_upper: Decimal | None
    direction_agreement_score: Decimal | None
    confidence: str
    model_count: int
    up_model_count: int
    down_model_count: int
    flat_model_count: int
    disagreement_pct: Decimal


def calculate_forecast_integration(
    row: Mapping[str, object],
    consensus: object | Mapping[str, object] | None = None,
) -> UpwardSignalForecastIntegration:
    """Calculate a bounded, deterministic forecast contribution.

    ``consensus`` may be an ``AdvancedForecastConsensus``/``ForecastConsensus``
    instance or a mapping. Missing evidence is represented conservatively and
    never becomes an upside score by accident.
    """

    evidence = _read_evidence(row, consensus)
    predicted_return = evidence.predicted_return or Decimal("0")
    lower_return = evidence.predicted_return_lower
    if lower_return is None:
        lower_return = predicted_return
    upper_return = evidence.predicted_return_upper
    if upper_return is None:
        upper_return = predicted_return

    upside = _score_return(predicted_return)
    safety = _score_return(lower_return)
    agreement = evidence.direction_agreement_score
    if agreement is None:
        agreement = _direction_agreement_from_counts(evidence)
    confidence_score, ceiling, ceiling_reason = _confidence_policy(evidence.confidence)
    raw = (
        upside * Decimal("0.40")
        + safety * Decimal("0.30")
        + agreement * Decimal("0.20")
        + confidence_score * Decimal("0.10")
    )
    integration_score = min(raw, ceiling)
    warnings: list[str] = []
    if evidence.confidence in {"low", "unknown"}:
        warnings.append("forecast_confidence:low")
    if evidence.disagreement_pct >= Decimal("10"):
        warnings.append("model_disagreement:high")
    if lower_return < Decimal("0"):
        warnings.append("quantile_downside:negative")
    if evidence.model_count < 2:
        warnings.append("model_count:insufficient")
    return UpwardSignalForecastIntegration(
        forecast_upside_score=_round(upside),
        downside_safety_score=_round(safety),
        direction_agreement_score=_round(agreement),
        confidence_score=_round(confidence_score),
        forecast_integration_score=_round(integration_score),
        score_ceiling=ceiling,
        score_ceiling_reason=ceiling_reason,
        consensus_confidence=evidence.confidence,
        model_disagreement_pct=_round(evidence.disagreement_pct),
        model_count=evidence.model_count,
        up_model_count=evidence.up_model_count,
        down_model_count=evidence.down_model_count,
        flat_model_count=evidence.flat_model_count,
        predicted_return=predicted_return if evidence.predicted_return is not None else None,
        predicted_return_lower=(
            lower_return if evidence.predicted_return_lower is not None else None
        ),
        predicted_return_upper=(
            upper_return if evidence.predicted_return_upper is not None else None
        ),
        warnings=warnings,
    )


def evaluate_upward_signal_forecast_case(
    symbol: str,
    row: Mapping[str, object],
    consensus: object | Mapping[str, object] | None = None,
) -> UpwardSignalForecastCase:
    """Compare current Upward Signal output with an evaluation-only contribution."""

    current = calculate_reversal_expectation(row)
    integration = calculate_forecast_integration(row, consensus)
    return UpwardSignalForecastCase(
        symbol=symbol,
        upward_signal_score=current.reversal_expectation_score,
        forecast_integration_score=integration.forecast_integration_score,
        score_delta=_round(
            integration.forecast_integration_score - current.reversal_expectation_score
        ),
        chart_shape_score=current.reversal_chart_shape_score,
        forecast_score=current.reversal_forecast_score,
        downside_safety_score=current.reversal_safety_score,
        confidence=integration.consensus_confidence,
        model_disagreement_pct=integration.model_disagreement_pct,
        warning_count=len(integration.warnings),
        warnings=integration.warnings,
    )


def evaluate_forecast_validation_points(
    points: list[ForecastValidationPoint],
) -> list[UpwardSignalForecastValidationCase]:
    """Reconstruct forecast evidence for each consensus validation origin.

    Adapter predictions at an origin are used only to derive direction
    agreement and the prediction range. ``actual_return`` is copied as a
    post-origin evaluation label and is never used by the integration score.
    """

    grouped: dict[tuple[str, datetime, int], list[ForecastValidationPoint]] = {}
    for point in points:
        grouped.setdefault((point.symbol, point.origin_at, point.horizon_days), []).append(point)

    cases: list[UpwardSignalForecastValidationCase] = []
    for group in grouped.values():
        consensus = next(
            (point for point in group if point.model_name == CONSENSUS_MODEL_NAME), None
        )
        adapters = [point for point in group if point.model_name != CONSENSUS_MODEL_NAME]
        if consensus is None or not adapters:
            continue
        returns = [point.predicted_return for point in adapters]
        up_count = sum(1 for value in returns if value > 0)
        down_count = sum(1 for value in returns if value < 0)
        flat_count = len(returns) - up_count - down_count
        dominant = max(up_count, down_count, flat_count)
        agreement = Decimal("100") * Decimal(dominant) / Decimal(len(returns))
        disagreement = max(returns) - min(returns)
        confidence = _validation_confidence(disagreement, len(returns), agreement)
        integration = calculate_forecast_integration(
            {
                "consensus_predicted_return": consensus.predicted_return,
                "predicted_return_lower": min(returns),
                "predicted_return_upper": max(returns),
                "predicted_return_range": disagreement,
                "direction_agreement_score": agreement,
                "confidence": confidence,
                "model_count": len(returns),
                "up_model_count": up_count,
                "down_model_count": down_count,
                "flat_model_count": flat_count,
            }
        )
        cases.append(
            UpwardSignalForecastValidationCase(
                symbol=consensus.symbol,
                market=consensus.market,
                asset_type=consensus.asset_type,
                regime=consensus.regime,
                horizon_days=consensus.horizon_days,
                origin_at=consensus.origin_at,
                target_at=consensus.target_at,
                actual_return=consensus.actual_return,
                predicted_return=consensus.predicted_return,
                forecast_integration_score=integration.forecast_integration_score,
                confidence=integration.consensus_confidence,
                model_disagreement_pct=integration.model_disagreement_pct,
                direction_agreement_score=integration.direction_agreement_score,
                warning_count=len(integration.warnings),
                warnings=integration.warnings,
            )
        )
    return cases


def summarize_forecast_validation_cases(
    cases: list[UpwardSignalForecastValidationCase],
) -> list[UpwardSignalForecastValidationSummary]:
    """Summarize validation outcomes by horizon and forecast-risk group."""

    selections: list[tuple[str, str, int, list[UpwardSignalForecastValidationCase]]] = [
        ("overall", "all", 0, cases)
    ]
    for horizon in sorted({case.horizon_days for case in cases}):
        selections.append(
            (
                "horizon",
                str(horizon),
                horizon,
                [case for case in cases if case.horizon_days == horizon],
            )
        )
    for group_type, attribute in (
        ("market", "market"),
        ("asset_type", "asset_type"),
        ("regime", "regime"),
        ("confidence", "confidence"),
    ):
        for value in sorted({str(getattr(case, attribute)) for case in cases}):
            selections.append(
                (
                    group_type,
                    value,
                    0,
                    [case for case in cases if str(getattr(case, attribute)) == value],
                )
            )
    disagreement_bands = {
        "low": lambda case: case.model_disagreement_pct < Decimal("5"),
        "medium": lambda case: Decimal("5") <= case.model_disagreement_pct < Decimal("12"),
        "high": lambda case: case.model_disagreement_pct >= Decimal("12"),
    }
    for band, predicate in disagreement_bands.items():
        selections.append(("disagreement", band, 0, [case for case in cases if predicate(case)]))

    summaries: list[UpwardSignalForecastValidationSummary] = []
    for group_type, group_value, horizon, selected in selections:
        if not selected:
            continue
        positive_count = sum(1 for case in selected if case.actual_return > 0)
        direction_matches = sum(
            1
            for case in selected
            if _return_sign(case.predicted_return) == _return_sign(case.actual_return)
        )
        warning_cases = sum(1 for case in selected if case.warning_count > 0)
        count = Decimal(len(selected))
        summaries.append(
            UpwardSignalForecastValidationSummary(
                group_type=group_type,
                group_value=group_value,
                horizon_days=horizon,
                case_count=len(selected),
                positive_actual_rate=_round(Decimal(positive_count) / count),
                direction_accuracy=_round(Decimal(direction_matches) / count),
                mean_actual_return=_round(
                    sum((case.actual_return for case in selected), Decimal("0")) / count
                ),
                mean_predicted_return=_round(
                    sum((case.predicted_return for case in selected), Decimal("0")) / count
                ),
                mean_integration_score=_round(
                    sum((case.forecast_integration_score for case in selected), Decimal("0"))
                    / count
                ),
                warning_case_rate=_round(Decimal(warning_cases) / count),
            )
        )
    return summaries


def write_forecast_validation_summary(
    summaries: list[UpwardSignalForecastValidationSummary],
    output_dir: Path,
) -> Path:
    """Write grouped point-in-time outcomes for review and later adoption gates."""

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "upward_signal_forecast_validation_summary.csv"
    fields = list(UpwardSignalForecastValidationSummary.model_fields)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary.model_dump() for summary in summaries)
    return path


def write_forecast_validation_outputs(
    cases: list[UpwardSignalForecastValidationCase],
    output_dir: Path,
) -> dict[str, Path]:
    """Write point-in-time cases and grouped outcome summaries."""

    output_dir.mkdir(parents=True, exist_ok=True)
    cases_path = output_dir / "upward_signal_forecast_validation_cases.csv"
    with cases_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(UpwardSignalForecastValidationCase.model_fields)
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {**case.model_dump(exclude={"warnings"}), "warnings": ";".join(case.warnings)}
            for case in cases
        )
    summary_path = write_forecast_validation_summary(
        summarize_forecast_validation_cases(cases), output_dir
    )
    return {"cases": cases_path, "summary": summary_path}


def write_upward_signal_forecast_outputs(
    cases: list[UpwardSignalForecastCase],
    integrations: Mapping[str, UpwardSignalForecastIntegration],
    output_dir: Path,
) -> dict[str, Path]:
    """Write the three Phase 35-A evaluation artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "cases": output_dir / "upward_signal_model_contribution_cases.csv",
        "integration": output_dir / "upward_signal_forecast_integration.md",
        "confidence": output_dir / "upward_signal_confidence_adjustments.md",
    }
    with paths["cases"].open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "symbol",
                "upward_signal_score",
                "forecast_integration_score",
                "score_delta",
                "chart_shape_score",
                "forecast_score",
                "downside_safety_score",
                "confidence",
                "model_disagreement_pct",
                "warning_count",
                "warnings",
            ],
        )
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {**case.model_dump(exclude={"warnings"}), "warnings": ";".join(case.warnings)}
            )
    paths["integration"].write_text(
        _render_integration_summary(cases, integrations), encoding="utf-8", newline="\n"
    )
    paths["confidence"].write_text(
        _render_confidence_summary(integrations), encoding="utf-8", newline="\n"
    )
    return paths


def _read_evidence(
    row: Mapping[str, object], consensus: object | Mapping[str, object] | None
) -> _ForecastEvidence:
    def value(name: str, default: object = None) -> object:
        if consensus is not None:
            if isinstance(consensus, Mapping) and name in consensus:
                return consensus[name]
            if hasattr(consensus, name):
                return getattr(consensus, name)
        return row.get(name, default)

    predicted = _optional_return(value("consensus_predicted_return", value("forecast_return_pct")))
    lower = _optional_return(value("predicted_return_lower"))
    upper = _optional_return(value("predicted_return_upper"))
    range_value = _optional_return(value("predicted_return_range", value("forecast_range_pct")))
    disagreement = abs(range_value or Decimal("0")) * Decimal("100")
    return _ForecastEvidence(
        predicted_return=predicted,
        predicted_return_lower=lower,
        predicted_return_upper=upper,
        direction_agreement_score=_optional_decimal(value("direction_agreement_score")),
        confidence=str(
            value("confidence", value("consensus_confidence", "unknown")) or "unknown"
        ).lower(),
        model_count=_nonnegative_int(value("model_count", 0)),
        up_model_count=_nonnegative_int(value("up_model_count", 0)),
        down_model_count=_nonnegative_int(value("down_model_count", 0)),
        flat_model_count=_nonnegative_int(value("flat_model_count", 0)),
        disagreement_pct=_round(disagreement),
    )


def _direction_agreement_from_counts(evidence: _ForecastEvidence) -> Decimal:
    total = evidence.up_model_count + evidence.down_model_count + evidence.flat_model_count
    if total < 1:
        return Decimal("50")
    dominant = max(evidence.up_model_count, evidence.down_model_count, evidence.flat_model_count)
    return Decimal("100") * Decimal(dominant) / Decimal(total)


def _confidence_policy(confidence: str) -> tuple[Decimal, Decimal, str]:
    if confidence == "high":
        return Decimal("90"), Decimal("100"), "confidence:high_no_additional_ceiling"
    if confidence == "medium":
        return Decimal("65"), Decimal("85"), "confidence:medium_ceiling_85"
    if confidence == "low":
        return Decimal("35"), Decimal("65"), "confidence:low_ceiling_65"
    return Decimal("50"), Decimal("50"), "confidence:unknown_ceiling_50"


def _validation_confidence(
    disagreement: Decimal,
    model_count: int,
    direction_agreement: Decimal,
) -> str:
    disagreement_pct = disagreement * Decimal("100")
    if model_count >= 3 and disagreement_pct <= Decimal("5") and direction_agreement >= 75:
        return "high"
    if model_count >= 2 and disagreement_pct <= Decimal("12") and direction_agreement >= 50:
        return "medium"
    return "low"


def _score_return(value: Decimal) -> Decimal:
    # A +/-20% forecast maps to the 0..100 evidence scale; it is not a return
    # forecast or an investment recommendation.
    return _clamp(Decimal("50") + value * Decimal("250"), Decimal("0"), Decimal("100"))


def _optional_return(value: object) -> Decimal | None:
    parsed = _optional_decimal(value)
    if parsed is None:
        return None
    # Ranking rows historically store percentage points while forecast models
    # store decimal returns. Accept both at this boundary only.
    return parsed / Decimal("100") if abs(parsed) > Decimal("1") else parsed


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _nonnegative_int(value: object) -> int:
    if not isinstance(value, (str, int, float, Decimal)):
        return 0
    try:
        return max(0, int(value))
    except (OverflowError, ValueError):
        return 0


def _return_sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _clamp(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return max(lower, min(upper, value))


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _render_integration_summary(
    cases: list[UpwardSignalForecastCase],
    integrations: Mapping[str, UpwardSignalForecastIntegration],
) -> str:
    if not cases:
        return "# 上向き兆候 Forecast統合評価\n\n評価ケースはありません。\n"
    high_disagreement = sum(
        1 for item in integrations.values() if item.model_disagreement_pct >= 10
    )
    low_confidence = sum(
        1 for item in integrations.values() if item.consensus_confidence in {"low", "unknown"}
    )
    average_delta = sum((case.score_delta for case in cases), Decimal("0")) / Decimal(len(cases))
    return (
        "# 上向き兆候 Forecast統合評価\n\n"
        "これは既存の上向き兆候スコアへForecast根拠を接続した場合の評価専用出力です。"
        "通常Rankingの順位・runtime weightは変更していません。\n\n"
        f"- 評価ケース数: {len(cases)}\n"
        f"- 現行スコアとの差分平均: {_round(average_delta)}\n"
        f"- 高disagreement: {high_disagreement}件\n"
        f"- low/unknown confidence: {low_confidence}件\n"
    )


def _render_confidence_summary(
    integrations: Mapping[str, UpwardSignalForecastIntegration],
) -> str:
    counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for item in integrations.values():
        counts[item.consensus_confidence] = counts.get(item.consensus_confidence, 0) + 1
    return (
        "# 上向き兆候 Confidence調整候補\n\n"
        "confidenceは予測の正しさを保証するものではなく、評価専用のscore ceiling候補です。\n\n"
        f"- high: {counts.get('high', 0)}件 / ceiling 100\n"
        f"- medium: {counts.get('medium', 0)}件 / ceiling 85\n"
        f"- low: {counts.get('low', 0)}件 / ceiling 65\n"
        f"- unknown: {counts.get('unknown', 0)}件 / ceiling 50\n\n"
        "採用には新規銘柄・新規期間でのwalk-forward holdout確認が必要です。\n"
    )
