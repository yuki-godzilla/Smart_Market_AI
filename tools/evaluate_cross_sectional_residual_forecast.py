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
    CrossSectionalResidualEvaluationReport,
    CrossSectionalResidualMetric,
    CrossSectionalResidualPrediction,
    build_cross_sectional_residual_report,
    evaluate_cross_sectional_residual_metrics,
    evaluate_point_in_time_cross_sectional_residual,
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
            "Evaluate a causal cross-sectional residual GBDT around the frozen "
            "conservative anchor without changing runtime forecasts."
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
    parser.add_argument("--evaluation-split", default="cross_sectional_audit")
    parser.add_argument("--min-training-samples", type=int, default=80)
    parser.add_argument("--min-training-origins", type=int, default=4)
    parser.add_argument("--min-fit-samples", type=int, default=50)
    parser.add_argument("--min-validation-samples", type=int, default=20)
    parser.add_argument("--min-cross-section-size", type=int, default=5)
    parser.add_argument("--min-samples-leaf", type=int, default=20)
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

    predictions = evaluate_point_in_time_cross_sectional_residual(
        calibration,
        evaluation,
        profiles,
        min_training_sample_count=args.min_training_samples,
        min_training_origin_count=args.min_training_origins,
        min_fit_sample_count=args.min_fit_samples,
        min_validation_sample_count=args.min_validation_samples,
        min_cross_section_size=args.min_cross_section_size,
        min_samples_leaf=args.min_samples_leaf,
    )
    metrics = evaluate_cross_sectional_residual_metrics(evaluation, predictions)
    report = build_cross_sectional_residual_report(
        metrics,
        predictions,
        required_splits=(args.evaluation_split.strip(),),
    )
    paths = write_cross_sectional_residual_artifacts(
        report,
        evaluation,
        predictions,
        Path(args.output),
        calibration_paths=calibration_paths,
        evaluation_path=evaluation_path,
        profile_path=profile_path,
        profile_sha256=profile_sha256,
        calibration_symbol_count=len({item.symbol for item in calibration}),
        calibration_observation_count=len(calibration),
        parameters={
            "learning_rate": "0.05",
            "max_iter": 100,
            "max_leaf_nodes": 7,
            "l2_regularization": "10.0",
            "early_stopping": False,
            "internal_fit_fraction": "0.70",
            "residual_clip_quantile": "0.90",
            "maximum_absolute_residual_correction": "0.25",
            "min_training_samples": args.min_training_samples,
            "min_training_origins": args.min_training_origins,
            "min_fit_samples": args.min_fit_samples,
            "min_validation_samples": args.min_validation_samples,
            "min_cross_section_size": args.min_cross_section_size,
            "min_samples_leaf": args.min_samples_leaf,
            "fit_and_validation_min_rmse_improvement_vs_anchor": "0.01",
            "audit_min_rmse_improvement_vs_anchor_and_consensus": "0.01",
            "minimum_selection_rate": "0.50",
        },
    )
    print(f"calibration observations: {len(calibration)}")
    print(f"evaluation observations: {len(evaluation)}")
    print(
        "cross-sectional selections: "
        f"{report.selected_prediction_count}/{report.prediction_count} "
        f"({report.selection_rate * Decimal('100'):.2f}%)"
    )
    print(f"runtime review eligible: {'yes' if report.runtime_review_eligible else 'no'}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0 if evaluation else 2


def write_cross_sectional_residual_artifacts(
    report: CrossSectionalResidualEvaluationReport,
    evaluation: list,
    predictions: list[CrossSectionalResidualPrediction],
    output_dir: Path,
    *,
    calibration_paths: tuple[Path, ...],
    evaluation_path: Path,
    profile_path: Path,
    profile_sha256: str,
    calibration_symbol_count: int,
    calibration_observation_count: int,
    parameters: dict[str, Any],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": output_dir / "cross_sectional_residual_evaluation.md",
        "manifest": output_dir / "cross_sectional_residual_manifest.json",
        "metrics": output_dir / "cross_sectional_residual_metrics.csv",
        "predictions": output_dir / "cross_sectional_residual_predictions.csv",
        "decisions": output_dir / "cross_sectional_residual_decisions.csv",
    }
    paths["summary"].write_text(
        render_cross_sectional_residual_markdown(
            report,
            evaluation,
            profile_sha256=profile_sha256,
            calibration_symbol_count=calibration_symbol_count,
            calibration_observation_count=calibration_observation_count,
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schema_version": "cross_sectional_residual_evaluation.v1",
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
        "calibration_symbol_count": calibration_symbol_count,
        "calibration_observation_count": calibration_observation_count,
        "evaluation_symbol_count": len({item.symbol for item in evaluation}),
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
    _write_metrics(paths["metrics"], report.metrics)
    _write_predictions(paths["predictions"], evaluation, predictions)
    _write_decisions(paths["decisions"], predictions)
    return paths


def render_cross_sectional_residual_markdown(
    report: CrossSectionalResidualEvaluationReport,
    evaluation: list,
    *,
    profile_sha256: str,
    calibration_symbol_count: int,
    calibration_observation_count: int,
) -> str:
    overall = {
        metric.horizon_days: metric for metric in report.metrics if metric.group_type == "overall"
    }
    origin_times = [item.origin_at for item in evaluation]
    lines = [
        "# Point-in-Time銘柄横断残差GBDT評価",
        "",
        "## 評価境界",
        "",
        f"- 調整履歴: {calibration_symbol_count}銘柄 / {calibration_observation_count}点",
        f"- symbol非重複監査: {len({item.symbol for item in evaluation})}銘柄 / "
        f"{len(evaluation)}点",
        f"- 固定profile SHA-256: `{profile_sha256}`",
        "- 各originでtarget確定済みのdevelopment labelだけを使用",
        "- 同一origin・horizonの予測値、anchor差、予測分散、横断percentile rankを使用",
        "- 古い70% originでfitし、新しい30% originは固定anchor比1% gateに限定",
        "- GBDTは100 trees相当、最大7 leaves、learning rate 0.05、L2=10に事前固定",
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
            "| horizon | Consensus RMSE | 固定anchor RMSE | 横断GBDT RMSE | "
            "vs Consensus | vs anchor |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for horizon, metric in sorted(overall.items()):
        lines.append(
            f"| {horizon}日 | {metric.consensus_rmse:.6f} | {metric.anchor_rmse:.6f} | "
            f"{metric.candidate_rmse:.6f} | "
            f"{metric.relative_rmse_improvement_vs_consensus * Decimal('100'):.2f}% | "
            f"{metric.relative_rmse_improvement_vs_anchor * Decimal('100'):.2f}% |"
        )
    lines.extend(
        [
            "",
            "## 採用gate",
            "",
            f"- 横断補正採用: {report.selected_prediction_count} / {report.prediction_count}点 "
            f"（{report.selection_rate * Decimal('100'):.2f}%）",
            f"- runtime review通過: **{'はい' if report.runtime_review_eligible else 'いいえ'}**",
            "",
        ]
    )
    lines.extend(f"- {reason}" for reason in report.gate_reasons)
    regressions = sorted(
        (
            metric
            for metric in report.metrics
            if metric.group_type not in {"overall", "selection_status"}
            and metric.sample_count >= 10
            and metric.relative_rmse_improvement_vs_anchor < 0
        ),
        key=lambda metric: metric.relative_rmse_improvement_vs_anchor,
    )
    lines.extend(["", "## 固定anchor比の弱いsubgroup", ""])
    if regressions:
        lines.extend(
            [
                "| horizon | group | n | anchor RMSE | 横断GBDT RMSE | 改善率 |",
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
            "- この結果は評価専用です。gate通過だけでruntimeへ自動接続しません。",
            "- 不通過時は現行Forecast、Cockpit、Ranking、Investment Scoreを変更しません。",
            "- この監査を見た後のparameter調整には別symbolまたは後日のsealed auditが必要です。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_metrics(path: Path, metrics: list[CrossSectionalResidualMetric]) -> None:
    fieldnames = list(CrossSectionalResidualMetric.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for metric in metrics:
            writer.writerow(_stringify_row(metric.model_dump()))


def _write_predictions(
    path: Path,
    observations: list,
    predictions: list[CrossSectionalResidualPrediction],
) -> None:
    observations_by_key = {
        (item.symbol, item.horizon_days, item.origin_at, item.target_at): item
        for item in observations
    }
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
        "cross_section_rank",
        "raw_residual_correction",
        "residual_correction",
        "candidate_return",
        "actual_return",
        "decision_status",
        "decision_reason",
        "correction_was_clipped",
        "return_was_capped",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for prediction in predictions:
            key = (
                prediction.symbol,
                prediction.horizon_days,
                prediction.origin_at,
                prediction.target_at,
            )
            observation = observations_by_key[key]
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
                    "cross_section_rank": prediction.cross_section_rank,
                    "raw_residual_correction": prediction.raw_residual_correction,
                    "residual_correction": prediction.residual_correction,
                    "candidate_return": prediction.price_center_return,
                    "actual_return": observation.actual_return,
                    "decision_status": prediction.decision.status,
                    "decision_reason": prediction.decision.reason,
                    "correction_was_clipped": prediction.correction_was_clipped,
                    "return_was_capped": prediction.return_was_capped,
                }
            )


def _write_decisions(
    path: Path,
    predictions: list[CrossSectionalResidualPrediction],
) -> None:
    decisions = {
        (prediction.horizon_days, prediction.origin_at): prediction.decision
        for prediction in predictions
    }
    fieldnames = [
        "model_name",
        "horizon_days",
        "as_of",
        "status",
        "reason",
        "available_sample_count",
        "available_origin_count",
        "fit_sample_count",
        "validation_sample_count",
        "prediction_cross_section_size",
        "correction_limit",
        "fit_anchor_rmse",
        "fit_candidate_rmse",
        "fit_relative_rmse_improvement_vs_anchor",
        "validation_anchor_rmse",
        "validation_candidate_rmse",
        "validation_relative_rmse_improvement_vs_anchor",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for decision in decisions.values():
            row = decision.model_dump(exclude={"feature_names"})
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
    if args.min_cross_section_size < 2:
        parser.error("--min-cross-section-size must be at least 2")
    if args.min_samples_leaf < 2:
        parser.error("--min-samples-leaf must be at least 2")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stringify_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in row.items()
    }


if __name__ == "__main__":
    raise SystemExit(main())
