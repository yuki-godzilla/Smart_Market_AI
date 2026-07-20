from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.forecast import (  # noqa: E402
    AnchoredResidualCalibrationDecision,
    AnchoredResidualCalibrationEvaluationReport,
    AnchoredResidualCalibrationMetric,
    AnchoredResidualCalibrationPrediction,
    ConservativeCalibrationMetric,
    ConservativeCalibrationObservation,
    HorizonConservativeCalibrationProfile,
    build_anchored_residual_calibration_report,
    evaluate_adaptive_calibration_metrics,
    evaluate_anchored_residual_calibration_metrics,
    evaluate_horizon_conditioned_calibration,
    evaluate_point_in_time_adaptive_calibration,
    evaluate_point_in_time_anchored_residual_calibration,
)
from tools.evaluate_adaptive_forecast_calibration import (  # noqa: E402
    assert_observation_symbol_disjoint,
    load_calibration_point_csvs,
)
from tools.evaluate_frozen_forecast_calibration import (  # noqa: E402
    DEFAULT_PROFILE,
    load_frozen_calibration_profiles,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate causal ridge residual corrections around a frozen forecast anchor "
            "on a symbol-disjoint cohort without runtime adoption."
        )
    )
    parser.add_argument(
        "--calibration-points",
        action="append",
        required=True,
        help="Development point CSV; repeat to combine histories.",
    )
    parser.add_argument("--evaluation-points", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--evaluation-split", default="anchored_residual_audit")
    parser.add_argument("--min-training-samples", type=int, default=80)
    parser.add_argument("--min-training-origins", type=int, default=3)
    parser.add_argument("--min-fit-samples", type=int, default=40)
    parser.add_argument("--min-validation-samples", type=int, default=20)
    args = parser.parse_args(argv)
    _validate_args(parser, args)

    calibration_paths = tuple(Path(path) for path in args.calibration_points)
    evaluation_path = Path(args.evaluation_points)
    profile_path = Path(args.profile)
    calibration = load_calibration_point_csvs(calibration_paths)
    evaluation = [
        observation.model_copy(update={"split": args.evaluation_split.strip()})
        for observation in load_calibration_point_csvs((evaluation_path,))
    ]
    assert_observation_symbol_disjoint(calibration, evaluation)
    profiles, profile_sha256 = load_frozen_calibration_profiles(profile_path)

    residual_predictions = evaluate_point_in_time_anchored_residual_calibration(
        calibration,
        evaluation,
        profiles,
        min_training_sample_count=args.min_training_samples,
        min_training_origin_count=args.min_training_origins,
        min_fit_sample_count=args.min_fit_samples,
        min_validation_sample_count=args.min_validation_samples,
    )
    residual_metrics = evaluate_anchored_residual_calibration_metrics(
        evaluation,
        residual_predictions,
    )
    report = build_anchored_residual_calibration_report(
        residual_metrics,
        residual_predictions,
        required_splits=(args.evaluation_split.strip(),),
    )
    fixed_metrics = evaluate_horizon_conditioned_calibration(evaluation, profiles)
    adaptive_predictions = evaluate_point_in_time_adaptive_calibration(
        calibration,
        evaluation,
    )
    adaptive_metrics = evaluate_adaptive_calibration_metrics(
        evaluation,
        adaptive_predictions,
    )
    paths = write_anchored_residual_artifacts(
        report,
        calibration,
        evaluation,
        residual_predictions,
        fixed_metrics,
        adaptive_metrics,
        profiles,
        Path(args.output),
        calibration_paths=calibration_paths,
        evaluation_path=evaluation_path,
        profile_path=profile_path,
        profile_sha256=profile_sha256,
        parameters={
            "candidate_specs": ["global_ridge", "context_ridge"],
            "ridge_alpha": {"global_ridge": "10", "context_ridge": "25"},
            "internal_fit_fraction": "0.7",
            "residual_clip_quantile": "0.90",
            "maximum_absolute_residual_correction": "0.25",
            "min_training_samples": args.min_training_samples,
            "min_training_origins": args.min_training_origins,
            "min_fit_samples": args.min_fit_samples,
            "min_validation_samples": args.min_validation_samples,
            "fit_and_validation_min_rmse_improvement_vs_anchor": "0.01",
            "audit_min_rmse_improvement_vs_anchor_and_consensus": "0.01",
            "minimum_residual_selection_rate": "0.50",
        },
    )
    print(f"calibration observations: {len(calibration)}")
    print(f"evaluation observations: {len(evaluation)}")
    print(
        "residual selections: "
        f"{report.selected_prediction_count}/{report.prediction_count} "
        f"({report.selection_rate * Decimal('100'):.2f}%)"
    )
    print(f"runtime review eligible: {'yes' if report.runtime_review_eligible else 'no'}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0 if evaluation else 2


def write_anchored_residual_artifacts(
    report: AnchoredResidualCalibrationEvaluationReport,
    calibration: list[ConservativeCalibrationObservation],
    evaluation: list[ConservativeCalibrationObservation],
    residual_predictions: list[AnchoredResidualCalibrationPrediction],
    fixed_metrics: list[ConservativeCalibrationMetric],
    adaptive_metrics: list[ConservativeCalibrationMetric],
    profiles: list[HorizonConservativeCalibrationProfile],
    output_dir: Path,
    *,
    calibration_paths: tuple[Path, ...],
    evaluation_path: Path,
    profile_path: Path,
    profile_sha256: str,
    parameters: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": output_dir / "anchored_residual_calibration_evaluation.md",
        "manifest": output_dir / "anchored_residual_calibration_manifest.json",
        "metrics": output_dir / "anchored_residual_calibration_metrics.csv",
        "comparators": output_dir / "anchored_residual_comparator_metrics.csv",
        "predictions": output_dir / "anchored_residual_calibration_predictions.csv",
        "decisions": output_dir / "anchored_residual_calibration_decisions.csv",
    }
    paths["summary"].write_text(
        render_anchored_residual_markdown(
            report,
            evaluation,
            fixed_metrics,
            adaptive_metrics,
            profile_sha256=profile_sha256,
            calibration_symbol_count=len({item.symbol for item in calibration}),
            calibration_observation_count=len(calibration),
            evaluation_symbol_count=len({item.symbol for item in evaluation}),
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schema_version": "anchored_residual_calibration_evaluation.v1",
        "model_name": report.model_name,
        "evaluation_only": True,
        "runtime_changed": False,
        "calibration_paths": [path.as_posix() for path in calibration_paths],
        "calibration_sha256": [_sha256(path) for path in calibration_paths],
        "evaluation_path": evaluation_path.as_posix(),
        "evaluation_sha256": _sha256(evaluation_path),
        "frozen_profile_path": profile_path.as_posix(),
        "frozen_profile_sha256": profile_sha256,
        "parameters": parameters,
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
    _write_residual_metrics(paths["metrics"], report.metrics)
    _write_comparator_metrics(paths["comparators"], fixed_metrics, adaptive_metrics)
    _write_predictions(paths["predictions"], evaluation, residual_predictions)
    _write_decisions(paths["decisions"], residual_predictions)
    return paths


def render_anchored_residual_markdown(
    report: AnchoredResidualCalibrationEvaluationReport,
    evaluation: list[ConservativeCalibrationObservation],
    fixed_metrics: list[ConservativeCalibrationMetric],
    adaptive_metrics: list[ConservativeCalibrationMetric],
    *,
    profile_sha256: str,
    calibration_symbol_count: int,
    calibration_observation_count: int,
    evaluation_symbol_count: int,
) -> str:
    residual_overall = _residual_overall_by_horizon(report.metrics)
    fixed_overall = _conservative_overall_by_horizon(fixed_metrics)
    adaptive_overall = _conservative_overall_by_horizon(adaptive_metrics)
    origin_times = [item.origin_at for item in evaluation]
    lines = [
        "# 固定anchor残差Ridge Forecast評価",
        "",
        "## 評価境界",
        "",
        f"- 調整履歴: {calibration_symbol_count}銘柄 / {calibration_observation_count}点",
        f"- symbol非重複監査: {evaluation_symbol_count}銘柄 / {len(evaluation)}点",
        f"- 固定profile SHA-256: `{profile_sha256}`",
        "- 20日・60日を分離し、各監査origin以前にtargetが確定した開発履歴だけで学習",
        "- 古い70% originで候補を選択し、新しい30% originは固定anchor比の通過判定だけに使用",
        "- 候補はglobal Ridge（alpha=10）とcontext Ridge（alpha=25）の2本に事前固定",
        "- 補正はfit残差の90%点か絶対25%の小さい方でclip。総returnは絶対75%でcap",
        "- direction headはConsensusを保持。ランタイムは未変更",
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
            "| horizon | Consensus RMSE | 固定anchor RMSE | 適応weight RMSE | "
            "残差Ridge RMSE | 残差 vs anchor | 残差 vs Consensus |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for horizon, metric in sorted(residual_overall.items()):
        fixed = fixed_overall.get(horizon)
        adaptive = adaptive_overall.get(horizon)
        lines.append(
            f"| {horizon}日 | {metric.consensus_rmse:.6f} | "
            f"{fixed.candidate_price_rmse:.6f} | "
            f"{adaptive.candidate_price_rmse:.6f} | "
            f"{metric.candidate_rmse:.6f} | "
            f"{metric.relative_rmse_improvement_vs_anchor * Decimal('100'):.2f}% | "
            f"{metric.relative_rmse_improvement_vs_consensus * Decimal('100'):.2f}% |"
            if fixed is not None and adaptive is not None
            else f"| {horizon}日 | 比較データ不足 |"
        )
    lines.extend(
        [
            "",
            "## 採用gate",
            "",
            f"- residual補正採用: {report.selected_prediction_count} / "
            f"{report.prediction_count}点（{report.selection_rate * Decimal('100'):.2f}%）",
            f"- runtime review通過: **{'はい' if report.runtime_review_eligible else 'いいえ'}**",
            "",
        ]
    )
    lines.extend(f"- {reason}" for reason in report.gate_reasons)
    regressions = sorted(
        (
            metric
            for metric in report.metrics
            if metric.group_type not in ("overall", "selection_status", "model_spec")
            and metric.sample_count >= 10
            and metric.relative_rmse_improvement_vs_anchor < 0
        ),
        key=lambda metric: metric.relative_rmse_improvement_vs_anchor,
    )
    lines.extend(["", "## 固定anchor比の弱いsubgroup", ""])
    if regressions:
        lines.extend(
            [
                "| horizon | group | n | anchor RMSE | residual RMSE | 改善率 |",
                "|---:|---|---:|---:|---:|---:|",
            ]
        )
        for metric in regressions[:20]:
            lines.append(
                f"| {metric.horizon_days}日 | {metric.group_type}={metric.group_value} | "
                f"{metric.sample_count} | {metric.anchor_rmse:.6f} | "
                f"{metric.candidate_rmse:.6f} | "
                f"{metric.relative_rmse_improvement_vs_anchor * Decimal('100'):.2f}% |"
            )
    else:
        lines.append("- sample 10点以上で固定anchor比マイナスのsubgroupはありません。")
    lines.extend(
        [
            "",
            "## 結論",
            "",
            "- この結果は評価専用です。採用gate通過だけでは自動的にruntimeへ接続しません。",
            "- 不通過時は固定anchorを維持し、Forecast・Cockpit・Ranking・Investment Scoreを変更しません。",
            "- この監査を見た後のparameter調整には、さらに別symbolまたは後日のsealed auditが必要です。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_residual_metrics(
    path: Path,
    metrics: list[AnchoredResidualCalibrationMetric],
) -> None:
    fieldnames = list(AnchoredResidualCalibrationMetric.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for metric in metrics:
            writer.writerow(_stringify_row(metric.model_dump()))


def _write_comparator_metrics(
    path: Path,
    fixed_metrics: list[ConservativeCalibrationMetric],
    adaptive_metrics: list[ConservativeCalibrationMetric],
) -> None:
    fieldnames = ["model", *ConservativeCalibrationMetric.model_fields]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for model, metrics in (
            ("fixed_anchor", fixed_metrics),
            ("adaptive_weight", adaptive_metrics),
        ):
            for metric in metrics:
                writer.writerow({"model": model, **_stringify_row(metric.model_dump())})


def _write_predictions(
    path: Path,
    observations: list[ConservativeCalibrationObservation],
    predictions: list[AnchoredResidualCalibrationPrediction],
) -> None:
    observations_by_key = {_point_key(item): item for item in observations}
    fieldnames = [
        "symbol",
        "market",
        "asset_type",
        "regime",
        "horizon_days",
        "origin_at",
        "target_at",
        "consensus_return",
        "anchor_return",
        "raw_residual_correction",
        "residual_correction",
        "candidate_return",
        "actual_return",
        "decision_status",
        "decision_reason",
        "selected_spec",
        "correction_was_clipped",
        "return_was_capped",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for prediction in predictions:
            observation = observations_by_key[_point_key(prediction)]
            writer.writerow(
                {
                    "symbol": prediction.symbol,
                    "market": observation.market,
                    "asset_type": observation.asset_type,
                    "regime": observation.regime,
                    "horizon_days": prediction.horizon_days,
                    "origin_at": prediction.origin_at.isoformat(),
                    "target_at": prediction.target_at.isoformat(),
                    "consensus_return": prediction.original_consensus_return,
                    "anchor_return": prediction.anchor_return,
                    "raw_residual_correction": prediction.raw_residual_correction,
                    "residual_correction": prediction.residual_correction,
                    "candidate_return": prediction.price_center_return,
                    "actual_return": observation.actual_return,
                    "decision_status": prediction.decision.status,
                    "decision_reason": prediction.decision.reason,
                    "selected_spec": prediction.decision.selected_spec,
                    "correction_was_clipped": prediction.correction_was_clipped,
                    "return_was_capped": prediction.return_was_capped,
                }
            )


def _write_decisions(
    path: Path,
    predictions: list[AnchoredResidualCalibrationPrediction],
) -> None:
    decisions = {
        (prediction.horizon_days, prediction.origin_at): prediction.decision
        for prediction in predictions
    }
    fieldnames = list(AnchoredResidualCalibrationDecision.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for decision in decisions.values():
            row = decision.model_dump()
            for field in ("feature_names", "feature_means", "feature_scales", "coefficients"):
                row[field] = "|".join(str(value) for value in row[field])
            writer.writerow(_stringify_row(row))


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not args.evaluation_split.strip():
        parser.error("--evaluation-split must not be empty")
    if args.min_training_samples < 1:
        parser.error("--min-training-samples must be positive")
    if args.min_training_origins < 2:
        parser.error("--min-training-origins must be at least 2")
    if args.min_fit_samples < 1 or args.min_validation_samples < 1:
        parser.error("internal sample minimums must be positive")


def _residual_overall_by_horizon(
    metrics: list[AnchoredResidualCalibrationMetric],
) -> dict[int, AnchoredResidualCalibrationMetric]:
    return {metric.horizon_days: metric for metric in metrics if metric.group_type == "overall"}


def _conservative_overall_by_horizon(
    metrics: list[ConservativeCalibrationMetric],
) -> dict[int, ConservativeCalibrationMetric]:
    return {metric.horizon_days: metric for metric in metrics if metric.group_type == "overall"}


def _point_key(
    item: ConservativeCalibrationObservation | AnchoredResidualCalibrationPrediction,
) -> tuple[str, int, datetime, datetime]:
    return (item.symbol, item.horizon_days, item.origin_at, item.target_at)


def _stringify_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: (
            value.isoformat()
            if isinstance(value, datetime)
            else str(value) if isinstance(value, Decimal) else value
        )
        for key, value in row.items()
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
