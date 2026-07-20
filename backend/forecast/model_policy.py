from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Sequence

HORIZON_MODEL_POLICY_VERSION = "horizon_validation_router_v1"
SHORT_HORIZON_MAX_DAYS = 30
AUDITED_HORIZON_MAX_DAYS = 60
MIN_SELECTION_SAMPLE_COUNT = 24
MIN_SELECTION_FOLD_COUNT = 2
MIN_RELATIVE_RMSE_IMPROVEMENT = Decimal("0.01")

QUANTILE_ADAPTER_NAME = "advanced_quantile"
TREE_ADAPTER_NAME = "advanced_tree_sklearn"
GBDT_ADAPTER_NAME = "advanced_gbdt_sklearn"

ForecastHorizonBand = Literal["short", "medium", "long"]
ForecastAuditStatus = Literal["sealed_anchor", "interpolated", "outside_sealed_audit"]
ForecastSelectionMode = Literal[
    "validated_consensus",
    "quantile_anchor",
    "best_available_fallback",
    "range_first_long_horizon",
]


@dataclass(frozen=True)
class AdvancedForecastModelCandidate:
    """Past-only validation summary used by the deterministic model router."""

    adapter_name: str
    rmse: Decimal
    baseline_zero_rmse: Decimal | None
    rmse_improvement: Decimal | None
    direction_accuracy: Decimal
    sample_count: int
    fold_count: int


@dataclass(frozen=True)
class AdvancedForecastModelSelection:
    """Auditable role-based model selection for one common forecast horizon."""

    policy_version: str
    horizon_days: int
    horizon_band: ForecastHorizonBand
    audit_status: ForecastAuditStatus
    selection_mode: ForecastSelectionMode
    center_adapter_names: tuple[str, ...]
    direction_adapter_names: tuple[str, ...]
    selected_adapter_names: tuple[str, ...]
    center_excluded_adapter_names: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...] = ()


def select_advanced_forecast_models(
    candidates: Sequence[AdvancedForecastModelCandidate],
    *,
    horizon_days: int,
) -> AdvancedForecastModelSelection:
    """Select center and direction roles using horizon and past-only validation.

    The sealed 20/60-day audits support ``advanced_quantile`` as the conservative
    advanced-model center. Tree and GBDT adapters may join only when their validation
    available at the forecast origin clears the predeclared improvement gate. The
    unstable linear adapter remains visible as detail but is not routed into the center.
    """

    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1")
    names = [candidate.adapter_name for candidate in candidates]
    if len(names) != len(set(names)):
        raise ValueError("advanced forecast model candidates must have unique adapter names")

    horizon_band = _horizon_band(horizon_days)
    audit_status = _audit_status(horizon_days)
    by_name = {candidate.adapter_name: candidate for candidate in candidates}
    quantile = by_name.get(QUANTILE_ADAPTER_NAME)

    secondary_limit = 2 if horizon_band == "short" else 1 if horizon_band == "medium" else 0
    secondary_candidates = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.adapter_name in {TREE_ADAPTER_NAME, GBDT_ADAPTER_NAME}
            and _passes_center_gate(candidate, anchor=quantile)
        ),
        key=_center_sort_key,
    )[:secondary_limit]

    warnings: list[str] = []
    if quantile is not None:
        center = [quantile, *secondary_candidates]
        if horizon_band == "long":
            selection_mode: ForecastSelectionMode = "range_first_long_horizon"
            reason = (
                "60日超はsealed監査外のため、過去分布を使うレンジモデルだけを中心値に採用しました。"
            )
        elif secondary_candidates:
            selection_mode = "validated_consensus"
            reason = (
                "監査で安定したレンジモデルを中心に、forecast origin以前のwalk-forward検証で"
                "レンジモデルのRMSEを1%以上改善した非線形モデルだけを追加しました。"
            )
        else:
            selection_mode = "quantile_anchor"
            reason = (
                "追加モデルが検証gateを満たさないため、監査で相対的に安定したレンジモデルを"
                "中心値として採用しました。"
            )
    elif secondary_candidates:
        center = secondary_candidates
        selection_mode = "best_available_fallback"
        reason = "レンジモデルを利用できないため、検証gateを通過したモデルへfallbackしました。"
        warnings.append("The audited quantile anchor was unavailable for this forecast.")
    elif candidates:
        center = [min(candidates, key=_fallback_sort_key)]
        selection_mode = "best_available_fallback"
        reason = (
            "検証gate通過モデルがないため、利用可能モデルのうちRMSEが最小の1モデルへ縮退しました。"
        )
        warnings.append(
            "No model passed the validation gate; the consensus used one fallback model."
        )
    else:
        center = []
        selection_mode = "best_available_fallback"
        reason = "利用可能な高度予測モデルがありません。"

    # Sealed audits found the pre-existing all-adapter direction head more
    # stable than a direction inferred from the newly routed price center.
    # Preserve it through 60 days. Beyond the sealed audit range, shrink the
    # direction role to the same conservative models as the price center.
    direction = list(candidates) if horizon_days <= AUDITED_HORIZON_MAX_DAYS else list(center)

    selected_names = _ordered_unique(
        [candidate.adapter_name for candidate in center]
        + [candidate.adapter_name for candidate in direction]
    )
    center_names = {candidate.adapter_name for candidate in center}
    center_excluded_names = tuple(name for name in names if name not in center_names)
    if audit_status == "interpolated":
        warnings.append(
            "This horizon is routed by interpolation between the sealed 20-day and 60-day audits."
        )
    elif audit_status == "outside_sealed_audit":
        warnings.append(
            "This horizon is outside the sealed 20-day and 60-day price-center audits; "
            "price-center confidence is capped low."
        )
    if center_excluded_names:
        warnings.append(
            "Some available adapters were excluded from the price-center consensus by the "
            "horizon validation policy."
        )

    return AdvancedForecastModelSelection(
        policy_version=HORIZON_MODEL_POLICY_VERSION,
        horizon_days=horizon_days,
        horizon_band=horizon_band,
        audit_status=audit_status,
        selection_mode=selection_mode,
        center_adapter_names=tuple(candidate.adapter_name for candidate in center),
        direction_adapter_names=tuple(candidate.adapter_name for candidate in direction),
        selected_adapter_names=selected_names,
        center_excluded_adapter_names=center_excluded_names,
        reason=reason,
        warnings=tuple(warnings),
    )


def _passes_center_gate(
    candidate: AdvancedForecastModelCandidate,
    *,
    anchor: AdvancedForecastModelCandidate | None,
) -> bool:
    if not _has_sufficient_validation(candidate):
        return False
    if anchor is not None:
        if not _has_sufficient_validation(anchor) or anchor.rmse <= 0:
            return False
        return candidate.rmse <= anchor.rmse * (Decimal("1") - MIN_RELATIVE_RMSE_IMPROVEMENT)
    baseline = candidate.baseline_zero_rmse
    improvement = candidate.rmse_improvement
    if baseline is None or baseline <= 0 or improvement is None:
        return False
    return improvement / baseline >= MIN_RELATIVE_RMSE_IMPROVEMENT


def _has_sufficient_validation(candidate: AdvancedForecastModelCandidate) -> bool:
    return (
        candidate.sample_count >= MIN_SELECTION_SAMPLE_COUNT
        and candidate.fold_count >= MIN_SELECTION_FOLD_COUNT
    )


def _relative_improvement(candidate: AdvancedForecastModelCandidate) -> Decimal:
    baseline = candidate.baseline_zero_rmse
    improvement = candidate.rmse_improvement
    if baseline is None or baseline <= 0 or improvement is None:
        return Decimal("-1")
    return improvement / baseline


def _center_sort_key(
    candidate: AdvancedForecastModelCandidate,
) -> tuple[Decimal, Decimal, int, str]:
    return (
        candidate.rmse,
        -candidate.direction_accuracy,
        -candidate.sample_count,
        candidate.adapter_name,
    )


def _fallback_sort_key(candidate: AdvancedForecastModelCandidate) -> tuple[Decimal, Decimal, str]:
    return (candidate.rmse, -candidate.direction_accuracy, candidate.adapter_name)


def _horizon_band(horizon_days: int) -> ForecastHorizonBand:
    if horizon_days <= SHORT_HORIZON_MAX_DAYS:
        return "short"
    if horizon_days <= AUDITED_HORIZON_MAX_DAYS:
        return "medium"
    return "long"


def _audit_status(horizon_days: int) -> ForecastAuditStatus:
    if horizon_days in {20, 60}:
        return "sealed_anchor"
    if horizon_days <= AUDITED_HORIZON_MAX_DAYS:
        return "interpolated"
    return "outside_sealed_audit"


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
