from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.forecast import (  # noqa: E402
    ADAPTIVE_SOURCE_MODEL_NAMES,
    AdaptiveCalibrationEvaluationReport,
    AdaptiveCalibrationPrediction,
    ConservativeCalibrationMetric,
    ConservativeCalibrationObservation,
    HorizonConservativeCalibrationProfile,
    apply_horizon_conditioned_calibration,
    build_adaptive_calibration_report,
    evaluate_adaptive_calibration_metrics,
    evaluate_horizon_conditioned_calibration,
    evaluate_point_in_time_adaptive_calibration,
)
from tools.evaluate_frozen_forecast_calibration import (  # noqa: E402
    DEFAULT_PROFILE,
    load_frozen_calibration_profiles,
)

REQUIRED_POINT_FIELDS = {
    "cohort",
    "split",
    "symbol",
    "market",
    "asset_type",
    "regime",
    "horizon_days",
    "origin_at",
    "target_at",
    "consensus_return",
    "advanced_quantile_return",
    "moving_average_3_return",
    "actual_return",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate point-in-time adaptive non-negative forecast calibration on a "
            "symbol-disjoint audit cohort without runtime adoption."
        )
    )
    parser.add_argument(
        "--calibration-points",
        action="append",
        required=True,
        help="Calibration point CSV; repeat to combine development histories.",
    )
    parser.add_argument("--evaluation-points", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--evaluation-split", default="adaptive_audit")
    parser.add_argument("--min-training-samples", type=int, default=40)
    parser.add_argument("--min-training-origins", type=int, default=3)
    parser.add_argument("--min-fit-samples", type=int, default=20)
    parser.add_argument("--min-validation-samples", type=int, default=10)
    args = parser.parse_args(argv)
    if not args.evaluation_split.strip():
        parser.error("--evaluation-split must not be empty")
    if args.min_training_samples < 1:
        parser.error("--min-training-samples must be positive")
    if args.min_training_origins < 2:
        parser.error("--min-training-origins must be at least 2")
    if args.min_fit_samples < 1 or args.min_validation_samples < 1:
        parser.error("internal sample minimums must be positive")

    calibration_paths = tuple(Path(path) for path in args.calibration_points)
    evaluation_path = Path(args.evaluation_points)
    calibration = load_calibration_point_csvs(calibration_paths)
    evaluation = [
        observation.model_copy(update={"split": args.evaluation_split.strip()})
        for observation in load_calibration_point_csvs((evaluation_path,))
    ]
    assert_observation_symbol_disjoint(calibration, evaluation)
    predictions = evaluate_point_in_time_adaptive_calibration(
        calibration,
        evaluation,
        min_training_sample_count=args.min_training_samples,
        min_training_origin_count=args.min_training_origins,
        min_fit_sample_count=args.min_fit_samples,
        min_validation_sample_count=args.min_validation_samples,
    )
    adaptive_metrics = evaluate_adaptive_calibration_metrics(evaluation, predictions)
    report = build_adaptive_calibration_report(
        adaptive_metrics,
        predictions,
        required_splits=(args.evaluation_split.strip(),),
    )
    profiles, profile_sha256 = load_frozen_calibration_profiles(Path(args.profile))
    fixed_metrics = evaluate_horizon_conditioned_calibration(evaluation, profiles)
    paths = write_adaptive_calibration_artifacts(
        report,
        calibration,
        evaluation,
        predictions,
        fixed_metrics,
        profiles,
        Path(args.output),
        calibration_paths=calibration_paths,
        evaluation_path=evaluation_path,
        profile_path=Path(args.profile),
        profile_sha256=profile_sha256,
        adaptive_parameters={
            "weight_grid_step": "0.1",
            "internal_fit_fraction": "0.7",
            "min_training_samples": args.min_training_samples,
            "min_training_origins": args.min_training_origins,
            "min_fit_samples": args.min_fit_samples,
            "min_validation_samples": args.min_validation_samples,
            "fit_and_validation_min_relative_rmse_improvement": "0.01",
            "minimum_adaptive_selection_rate": "0.50",
        },
    )
    print(f"calibration observations: {len(calibration)}")
    print(f"evaluation observations: {len(evaluation)}")
    print(
        "adaptive selections: "
        f"{report.selected_prediction_count}/{report.prediction_count} "
        f"({report.selection_rate * Decimal('100'):.2f}%)"
    )
    print(f"runtime review eligible: {'yes' if report.runtime_review_eligible else 'no'}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0 if evaluation else 2


def load_calibration_point_csvs(
    paths: tuple[Path, ...],
) -> list[ConservativeCalibrationObservation]:
    """Load auditable source returns from one or more point-in-time CSVs."""

    observations: list[ConservativeCalibrationObservation] = []
    seen: set[tuple[str, int, datetime, datetime]] = set()
    for path in paths:
        if not path.is_file():
            raise ValueError(f"calibration point CSV not found: {path}")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = REQUIRED_POINT_FIELDS - set(reader.fieldnames or ())
            if missing:
                raise ValueError(
                    f"calibration point CSV is missing fields: {','.join(sorted(missing))}"
                )
            for row in reader:
                observation = ConservativeCalibrationObservation(
                    cohort=row["cohort"].strip(),
                    split=row["split"].strip(),
                    symbol=row["symbol"].strip(),
                    market=row["market"].strip(),
                    asset_type=row["asset_type"].strip(),
                    regime=row["regime"].strip(),
                    horizon_days=int(row["horizon_days"]),
                    origin_at=_parse_datetime(row["origin_at"]),
                    target_at=_parse_datetime(row["target_at"]),
                    consensus_return=Decimal(row["consensus_return"]),
                    actual_return=Decimal(row["actual_return"]),
                    conservative_returns={
                        "advanced_quantile": Decimal(row["advanced_quantile_return"]),
                        "moving_average_3": Decimal(row["moving_average_3_return"]),
                    },
                )
                key = _observation_key(observation)
                if key in seen:
                    raise ValueError(f"duplicate calibration point: {key}")
                seen.add(key)
                observations.append(observation)
    return observations


def assert_observation_symbol_disjoint(
    calibration: list[ConservativeCalibrationObservation],
    evaluation: list[ConservativeCalibrationObservation],
) -> None:
    calibration_symbols = {observation.symbol for observation in calibration}
    evaluation_symbols = {observation.symbol for observation in evaluation}
    overlap = sorted(calibration_symbols & evaluation_symbols)
    if overlap:
        raise ValueError(
            "adaptive evaluation symbols overlap calibration history: " + ",".join(overlap)
        )


def write_adaptive_calibration_artifacts(
    report: AdaptiveCalibrationEvaluationReport,
    calibration: list[ConservativeCalibrationObservation],
    evaluation: list[ConservativeCalibrationObservation],
    predictions: list[AdaptiveCalibrationPrediction],
    fixed_metrics: list[ConservativeCalibrationMetric],
    profiles: list[HorizonConservativeCalibrationProfile],
    output_dir: Path,
    *,
    calibration_paths: tuple[Path, ...],
    evaluation_path: Path,
    profile_path: Path,
    profile_sha256: str,
    adaptive_parameters: dict[str, str | int],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": output_dir / "adaptive_calibration_evaluation.md",
        "manifest": output_dir / "adaptive_calibration_manifest.json",
        "adaptive_metrics": output_dir / "adaptive_calibration_metrics.csv",
        "fixed_metrics": output_dir / "fixed_calibration_comparison_metrics.csv",
        "predictions": output_dir / "adaptive_calibration_predictions.csv",
        "decisions": output_dir / "adaptive_calibration_weight_decisions.csv",
    }
    paths["summary"].write_text(
        render_adaptive_calibration_markdown(
            report,
            evaluation,
            fixed_metrics,
            profile_sha256=profile_sha256,
            calibration_symbol_count=len({item.symbol for item in calibration}),
            calibration_observation_count=len(calibration),
            evaluation_symbol_count=len({item.symbol for item in evaluation}),
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schema_version": "adaptive_calibration_evaluation.v1",
        "model_name": report.model_name,
        "evaluation_only": True,
        "runtime_changed": False,
        "calibration_paths": [path.as_posix() for path in calibration_paths],
        "calibration_sha256": [_sha256(path) for path in calibration_paths],
        "evaluation_path": evaluation_path.as_posix(),
        "evaluation_sha256": _sha256(evaluation_path),
        "frozen_profile_path": profile_path.as_posix(),
        "frozen_profile_sha256": profile_sha256,
        "source_models": list(ADAPTIVE_SOURCE_MODEL_NAMES),
        "adaptive_parameters": adaptive_parameters,
        "symbol_disjoint": True,
        "calibration_symbol_count": len({item.symbol for item in calibration}),
        "evaluation_symbol_count": len({item.symbol for item in evaluation}),
        "calibration_observation_count": len(calibration),
        "evaluation_observation_count": len(evaluation),
        "selected_prediction_count": report.selected_prediction_count,
        "fallback_prediction_count": report.fallback_prediction_count,
        "selection_rate": str(report.selection_rate),
        "runtime_review_eligible": report.runtime_review_eligible,
        "gate_reasons": report.gate_reasons,
        "warnings": report.warnings,
    }
    paths["manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_metrics(paths["adaptive_metrics"], report.metrics)
    _write_metrics(paths["fixed_metrics"], fixed_metrics)
    _write_predictions(paths["predictions"], evaluation, predictions, profiles)
    _write_decisions(paths["decisions"], predictions)
    return paths


def render_adaptive_calibration_markdown(
    report: AdaptiveCalibrationEvaluationReport,
    evaluation: list[ConservativeCalibrationObservation],
    fixed_metrics: list[ConservativeCalibrationMetric],
    *,
    profile_sha256: str,
    calibration_symbol_count: int,
    calibration_observation_count: int,
    evaluation_symbol_count: int,
) -> str:
    adaptive_overall = _overall_by_horizon(report.metrics)
    fixed_overall = _overall_by_horizon(fixed_metrics)
    period_metrics = sorted(
        (metric for metric in report.metrics if metric.group_type == "period"),
        key=lambda metric: (metric.group_value, metric.horizon_days),
    )
    regressions = sorted(
        (
            metric
            for metric in report.metrics
            if metric.group_type not in ("overall", "selection_status")
            and metric.sample_count >= 10
            and metric.relative_rmse_improvement < 0
        ),
        key=lambda metric: metric.relative_rmse_improvement,
    )
    predictions = report.prediction_count
    origin_times = [observation.origin_at for observation in evaluation]
    lines = [
        "# Point-in-time適応型Forecastキャリブレーション評価",
        "",
        "## 評価境界",
        "",
        f"- 調整履歴: {calibration_symbol_count}銘柄 / {calibration_observation_count}点",
        f"- symbol非重複監査: {evaluation_symbol_count}銘柄 / {predictions}点",
        f"- 固定profile SHA-256: `{profile_sha256}`",
        "- weightは各監査origin以前にtargetが確定した調整履歴だけで決定",
        "- 古いoriginでweightを選択し、新しい内部validation originは通過判定だけに使用",
        "- stock / ETFと20日 / 60日を分離。未来label、監査symbolのlabelはweightへ不使用",
        "- direction headは現行Consensusを保持。ランタイムは未変更",
    ]
    if origin_times:
        lines.append(
            f"- 監査origin範囲: {min(origin_times).isoformat()} ～ {max(origin_times).isoformat()}"
        )
    lines.extend(
        [
            "",
            "## 全体比較",
            "",
            "| Horizon | Samples | Consensus RMSE | 適応型RMSE | 適応型改善 | 固定候補RMSE | 固定候補改善 |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for horizon, adaptive in sorted(adaptive_overall.items()):
        fixed = fixed_overall.get(horizon)
        fixed_rmse = f"{fixed.candidate_price_rmse:.4f}" if fixed else "N/A"
        fixed_improvement = (
            f"{fixed.relative_rmse_improvement * Decimal('100'):.2f}%" if fixed else "N/A"
        )
        lines.append(
            f"| {horizon} | {adaptive.sample_count} | {adaptive.consensus_rmse:.4f} | "
            f"{adaptive.candidate_price_rmse:.4f} | "
            f"{adaptive.relative_rmse_improvement * Decimal('100'):.2f}% | "
            f"{fixed_rmse} | {fixed_improvement} |"
        )
    lines.extend(
        [
            "",
            "## 適応weight利用状況",
            "",
            f"- 適応weight採用: {report.selected_prediction_count}/{report.prediction_count} "
            f"({report.selection_rate * Decimal('100'):.2f}%)",
            f"- Consensus fallback: {report.fallback_prediction_count}/{report.prediction_count}",
            "",
            "## 期間別結果",
            "",
            "| 期間 | Horizon | Samples | Consensus RMSE | 適応型RMSE | 改善率 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| `{metric.group_value}` | {metric.horizon_days} | {metric.sample_count} | "
        f"{metric.consensus_rmse:.4f} | {metric.candidate_price_rmse:.4f} | "
        f"{metric.relative_rmse_improvement * Decimal('100'):.2f}% |"
        for metric in period_metrics
    )
    lines.extend(["", "## 劣化したサブグループ（標本数10以上）", ""])
    if regressions:
        lines.extend(
            [
                "| Horizon | グループ | Samples | Consensus RMSE | 適応型RMSE | 改善率 |",
                "| ---: | --- | ---: | ---: | ---: | ---: |",
                *[
                    f"| {metric.horizon_days} | `{metric.group_type}={metric.group_value}` | "
                    f"{metric.sample_count} | {metric.consensus_rmse:.4f} | "
                    f"{metric.candidate_price_rmse:.4f} | "
                    f"{metric.relative_rmse_improvement * Decimal('100'):.2f}% |"
                    for metric in regressions[:25]
                ],
            ]
        )
    else:
        lines.append("- 該当なし")
    lines.extend(
        [
            "",
            "## 採用ゲート",
            "",
            f"- 通過: **{'はい' if report.runtime_review_eligible else 'いいえ'}**",
            *[f"- {reason}" for reason in report.gate_reasons],
            "",
            "この評価はshadow比較であり、通過してもruntimeへ自動採用しない。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_metrics(path: Path, metrics: list[ConservativeCalibrationMetric]) -> None:
    fieldnames = list(ConservativeCalibrationMetric.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for metric in metrics:
            writer.writerow(metric.model_dump(mode="json"))


def _write_predictions(
    path: Path,
    observations: list[ConservativeCalibrationObservation],
    predictions: list[AdaptiveCalibrationPrediction],
    profiles: list[HorizonConservativeCalibrationProfile],
) -> None:
    observations_by_key = {_observation_key(item): item for item in observations}
    profiles_by_horizon = {profile.horizon_days: profile for profile in profiles}
    fieldnames = [
        "cohort",
        "split",
        "symbol",
        "market",
        "asset_type",
        "regime",
        "horizon_days",
        "origin_at",
        "target_at",
        "consensus_return",
        "advanced_quantile_return",
        "moving_average_3_return",
        "zero_return",
        "adaptive_price_center_return",
        "fixed_price_center_return",
        "retained_direction_return",
        "actual_return",
        "decision_status",
        "decision_reason",
        "available_sample_count",
        "available_origin_count",
        "fit_sample_count",
        "validation_sample_count",
        *[f"weight_{model_name}" for model_name in ADAPTIVE_SOURCE_MODEL_NAMES],
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for prediction in predictions:
            observation = observations_by_key[_prediction_key(prediction)]
            fixed = apply_horizon_conditioned_calibration(
                observation,
                profiles_by_horizon[observation.horizon_days],
            )
            decision = prediction.decision
            row = {
                "cohort": observation.cohort,
                "split": observation.split,
                "symbol": observation.symbol,
                "market": observation.market,
                "asset_type": observation.asset_type,
                "regime": observation.regime,
                "horizon_days": observation.horizon_days,
                "origin_at": observation.origin_at.isoformat(),
                "target_at": observation.target_at.isoformat(),
                "consensus_return": observation.consensus_return,
                "advanced_quantile_return": observation.conservative_returns["advanced_quantile"],
                "moving_average_3_return": observation.conservative_returns["moving_average_3"],
                "zero_return": Decimal("0"),
                "adaptive_price_center_return": prediction.price_center_return,
                "fixed_price_center_return": fixed.price_center_return,
                "retained_direction_return": prediction.direction_return,
                "actual_return": observation.actual_return,
                "decision_status": decision.status,
                "decision_reason": decision.reason,
                "available_sample_count": decision.available_sample_count,
                "available_origin_count": decision.available_origin_count,
                "fit_sample_count": decision.fit_sample_count,
                "validation_sample_count": decision.validation_sample_count,
            }
            row.update(
                {
                    f"weight_{model_name}": decision.weights[model_name]
                    for model_name in ADAPTIVE_SOURCE_MODEL_NAMES
                }
            )
            writer.writerow(row)


def _write_decisions(
    path: Path,
    predictions: list[AdaptiveCalibrationPrediction],
) -> None:
    decisions = {
        (
            prediction.decision.asset_type,
            prediction.decision.horizon_days,
            prediction.decision.as_of,
        ): prediction.decision
        for prediction in predictions
    }
    fieldnames = [
        "asset_type",
        "horizon_days",
        "as_of",
        "status",
        "reason",
        "available_sample_count",
        "available_origin_count",
        "fit_sample_count",
        "validation_sample_count",
        *[f"weight_{model_name}" for model_name in ADAPTIVE_SOURCE_MODEL_NAMES],
        "fit_consensus_rmse",
        "fit_candidate_rmse",
        "fit_relative_rmse_improvement",
        "validation_consensus_rmse",
        "validation_candidate_rmse",
        "validation_relative_rmse_improvement",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for _key, decision in sorted(decisions.items()):
            row = {
                "asset_type": decision.asset_type,
                "horizon_days": decision.horizon_days,
                "as_of": decision.as_of.isoformat(),
                "status": decision.status,
                "reason": decision.reason,
                "available_sample_count": decision.available_sample_count,
                "available_origin_count": decision.available_origin_count,
                "fit_sample_count": decision.fit_sample_count,
                "validation_sample_count": decision.validation_sample_count,
                "fit_consensus_rmse": decision.fit_consensus_rmse,
                "fit_candidate_rmse": decision.fit_candidate_rmse,
                "fit_relative_rmse_improvement": decision.fit_relative_rmse_improvement,
                "validation_consensus_rmse": decision.validation_consensus_rmse,
                "validation_candidate_rmse": decision.validation_candidate_rmse,
                "validation_relative_rmse_improvement": (
                    decision.validation_relative_rmse_improvement
                ),
            }
            row.update(
                {
                    f"weight_{model_name}": decision.weights[model_name]
                    for model_name in ADAPTIVE_SOURCE_MODEL_NAMES
                }
            )
            writer.writerow(row)


def _overall_by_horizon(
    metrics: list[ConservativeCalibrationMetric],
) -> dict[int, ConservativeCalibrationMetric]:
    return {metric.horizon_days: metric for metric in metrics if metric.group_type == "overall"}


def _observation_key(
    observation: ConservativeCalibrationObservation,
) -> tuple[str, int, datetime, datetime]:
    return (
        observation.symbol,
        observation.horizon_days,
        observation.origin_at,
        observation.target_at,
    )


def _prediction_key(
    prediction: AdaptiveCalibrationPrediction,
) -> tuple[str, int, datetime, datetime]:
    return (
        prediction.symbol,
        prediction.horizon_days,
        prediction.origin_at,
        prediction.target_at,
    )


def _parse_datetime(raw: str) -> datetime:
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("calibration timestamps must be timezone-aware")
    return parsed


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
