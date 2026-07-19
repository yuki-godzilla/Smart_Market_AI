from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.forecast import (  # noqa: E402
    ConservativeCalibrationEvaluationReport,
    ConservativeCalibrationMetric,
    ConservativeCalibrationObservation,
    HorizonConservativeCalibrationProfile,
    apply_horizon_conditioned_calibration,
    build_conservative_calibration_report,
    build_point_in_time_calibration_observations,
    evaluate_forecast_models,
    evaluate_horizon_conditioned_calibration,
    load_forecast_evaluation_dataset,
    write_forecast_dataset_coverage,
    write_forecast_evaluation_artifacts,
)
from tools.evaluate_forecast_models import limit_recent_case_bars  # noqa: E402

DEFAULT_PROFILE = (
    "data/forecast_evaluation/profiles/"
    "horizon_conditioned_conservative_calibration_2026-07-19.json"
)
DEFAULT_EXCLUSION_METADATA = (
    "data/forecast_evaluation/symbols.csv",
    "data/phase34_evaluation/symbols.csv",
    "data/forecast_evaluation/profiles/extended_live_calibration_symbols_2026-07-19.csv",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply an already-frozen conservative calibration profile to a symbol-disjoint "
            "replication cohort without refitting."
        )
    )
    parser.add_argument("--ohlcv", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--cohort-name", default="frozen_profile_replication")
    parser.add_argument("--split-name", default="new_audit")
    parser.add_argument("--evaluation-end", default=None)
    parser.add_argument("--required-bars", type=int, default=500)
    parser.add_argument("--recent-bars", type=int, default=750)
    parser.add_argument("--max-origins", type=int, default=3)
    parser.add_argument(
        "--exclude-metadata",
        action="append",
        default=None,
        help="Metadata CSV whose symbols must not occur in this cohort; repeat as needed.",
    )
    args = parser.parse_args(argv)
    if args.required_bars < 80:
        parser.error("--required-bars must be at least 80")
    if args.recent_bars < 120:
        parser.error("--recent-bars must be at least 120")
    if args.max_origins < 1:
        parser.error("--max-origins must be at least 1")

    profile_path = Path(args.profile)
    profiles, profile_sha256 = load_frozen_calibration_profiles(profile_path)
    end_at = parse_evaluation_end(args.evaluation_end)
    dataset = load_forecast_evaluation_dataset(
        Path(args.ohlcv),
        Path(args.metadata),
        required_bar_count=args.required_bars,
        end_at=end_at,
    )
    exclusion_paths = tuple(
        Path(path) for path in (args.exclude_metadata or list(DEFAULT_EXCLUSION_METADATA))
    )
    missing_exclusions = [path for path in exclusion_paths if not path.is_file()]
    if missing_exclusions:
        missing = ", ".join(path.as_posix() for path in missing_exclusions)
        raise ValueError(f"exclusion metadata not found: {missing}")
    assert_symbol_disjoint({row.symbol for row in dataset.coverage}, exclusion_paths)
    cases = limit_recent_case_bars(dataset.cases, args.recent_bars)
    evaluation = evaluate_forecast_models(cases, max_origins=args.max_origins)
    observations = build_point_in_time_calibration_observations(
        cases,
        evaluation.validation_points,
        cohort=args.cohort_name,
        split=args.split_name,
    )
    metrics = evaluate_horizon_conditioned_calibration(observations, profiles)
    report = build_conservative_calibration_report(
        profiles,
        metrics,
        required_splits=(args.split_name,),
    )
    output_dir = Path(args.output)
    advanced_dir = output_dir / "advanced_evaluation"
    coverage_paths = write_forecast_dataset_coverage(dataset, advanced_dir)
    evaluation_paths = write_forecast_evaluation_artifacts(evaluation, advanced_dir)
    replication_paths = write_frozen_replication_artifacts(
        report,
        observations,
        output_dir,
        profile_path=profile_path,
        profile_sha256=profile_sha256,
        requested_symbol_count=len(dataset.coverage),
        eligible_symbol_count=len(cases),
        evaluation_end=end_at,
        recent_bars=args.recent_bars,
        max_origins=args.max_origins,
        exclusion_paths=exclusion_paths,
    )
    print(f"frozen profile sha256: {profile_sha256}")
    print(f"eligible symbols: {len(cases)}/{len(dataset.coverage)}")
    print(f"observations: {len(observations)}")
    print(f"replication gate passed: {'yes' if report.runtime_review_eligible else 'no'}")
    for name, path in {**coverage_paths, **evaluation_paths, **replication_paths}.items():
        print(f"{name}: {path}")
    return 0 if observations else 2


def load_frozen_calibration_profiles(
    path: Path,
) -> tuple[list[HorizonConservativeCalibrationProfile], str]:
    """Load a versioned evaluation profile without exposing a fit path."""

    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("schema_version") != "frozen_conservative_calibration.v1":
        raise ValueError("unsupported frozen calibration schema")
    if payload.get("evaluation_only") is not True:
        raise ValueError("frozen calibration profile must remain evaluation-only")
    profiles = [
        HorizonConservativeCalibrationProfile.model_validate(row)
        for row in payload.get("profiles", [])
    ]
    horizons = [profile.horizon_days for profile in profiles]
    if sorted(horizons) != [20, 60] or len(set(horizons)) != len(horizons):
        raise ValueError("frozen calibration profile must contain unique 20/60-day horizons")
    return profiles, hashlib.sha256(raw).hexdigest()


def assert_symbol_disjoint(symbols: set[str], metadata_paths: tuple[Path, ...]) -> None:
    overlaps: dict[str, list[str]] = {}
    for path in metadata_paths:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            used = {
                row["symbol"].strip()
                for row in csv.DictReader(handle)
                if row.get("symbol", "").strip()
            }
        shared = sorted(symbols & used)
        if shared:
            overlaps[path.as_posix()] = shared
    if overlaps:
        details = "; ".join(
            f"{path}={','.join(shared)}" for path, shared in sorted(overlaps.items())
        )
        raise ValueError(f"replication cohort is not symbol-disjoint: {details}")


def parse_evaluation_end(raw: str | None) -> datetime | None:
    if raw is None or not raw.strip():
        return None
    value = raw.strip()
    if "T" not in value:
        return datetime.combine(datetime.fromisoformat(value).date(), time.max, tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def write_frozen_replication_artifacts(
    report: ConservativeCalibrationEvaluationReport,
    observations: list[ConservativeCalibrationObservation],
    output_dir: Path,
    *,
    profile_path: Path,
    profile_sha256: str,
    requested_symbol_count: int,
    eligible_symbol_count: int,
    evaluation_end: datetime | None,
    recent_bars: int,
    max_origins: int,
    exclusion_paths: tuple[Path, ...],
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "replication_summary": output_dir / "frozen_calibration_replication.md",
        "replication_manifest": output_dir / "frozen_calibration_replication_manifest.json",
        "replication_metrics": output_dir / "frozen_calibration_replication_metrics.csv",
        "replication_points": output_dir / "frozen_calibration_replication_points.csv",
    }
    paths["replication_summary"].write_text(
        render_frozen_replication_markdown(
            report,
            observations,
            profile_sha256=profile_sha256,
            requested_symbol_count=requested_symbol_count,
            eligible_symbol_count=eligible_symbol_count,
            evaluation_end=evaluation_end,
            recent_bars=recent_bars,
            max_origins=max_origins,
        ),
        encoding="utf-8",
        newline="\n",
    )
    manifest = {
        "schema_version": "frozen_calibration_replication.v1",
        "profile_path": profile_path.as_posix(),
        "profile_sha256": profile_sha256,
        "profile_refit": False,
        "replication_gate_passed": report.runtime_review_eligible,
        "requested_symbol_count": requested_symbol_count,
        "eligible_symbol_count": eligible_symbol_count,
        "observation_count": len(observations),
        "evaluation_end": evaluation_end.isoformat() if evaluation_end is not None else None,
        "recent_bars": recent_bars,
        "max_origins": max_origins,
        "excluded_metadata": [path.as_posix() for path in exclusion_paths],
        "gate_reasons": report.gate_reasons,
        "runtime_changed": False,
    }
    paths["replication_manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_metrics(paths["replication_metrics"], report.metrics)
    _write_points(paths["replication_points"], observations, report.profiles)
    return paths


def render_frozen_replication_markdown(
    report: ConservativeCalibrationEvaluationReport,
    observations: list[ConservativeCalibrationObservation],
    *,
    profile_sha256: str,
    requested_symbol_count: int,
    eligible_symbol_count: int,
    evaluation_end: datetime | None,
    recent_bars: int,
    max_origins: int,
) -> str:
    overall = sorted(
        (metric for metric in report.metrics if metric.group_type == "overall"),
        key=lambda metric: metric.horizon_days,
    )
    subgroup_regressions = sorted(
        (
            metric
            for metric in report.metrics
            if metric.group_type != "overall"
            and metric.sample_count >= 10
            and metric.relative_rmse_improvement < 0
        ),
        key=lambda metric: metric.relative_rmse_improvement,
    )
    origin_times = [observation.origin_at for observation in observations]
    lines = [
        "# 固定済み保守的キャリブレーションの再現評価",
        "",
        "## 評価境界",
        "",
        f"- 固定プロファイル SHA-256: `{profile_sha256}`",
        "- プロファイル再調整: **なし**",
        f"- 銘柄非重複カバレッジ: 適格 {eligible_symbol_count}/{requested_symbol_count}",
        f"- 評価終端: {evaluation_end.isoformat() if evaluation_end else '取得済み最新バー'}",
        f"- 評価窓: 終端以前の直近 {recent_bars} 本、rolling origin は最大 {max_origins}",
        "- レジーム分類には各 origin 時点までのバーだけを使用し、後続バーを使用しない",
        "- ランタイムの Forecast、Cockpit、Ranking、スコアは未変更",
        "",
        "## 固定プロファイル",
        "",
        "| 予測期間 | 保守モデル | Consensus 比率 | 保守モデル比率 |",
        "| ---: | --- | ---: | ---: |",
    ]
    lines.extend(
        f"| {profile.horizon_days} | `{profile.conservative_model_name}` | "
        f"{profile.consensus_weight:.2f} | {profile.conservative_weight:.2f} |"
        for profile in sorted(report.profiles, key=lambda item: item.horizon_days)
    )
    lines.extend(
        [
            "",
            "## 全体結果",
            "",
            "| 予測期間 | 標本数 | Consensus RMSE | 候補 RMSE | 改善率 | Consensus 方向精度 | 中心値方向精度 | 維持方向精度 |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| {metric.horizon_days} | {metric.sample_count} | {metric.consensus_rmse:.4f} | "
        f"{metric.candidate_price_rmse:.4f} | "
        f"{metric.relative_rmse_improvement * Decimal('100'):.2f}% | "
        f"{metric.consensus_direction_accuracy * Decimal('100'):.2f}% | "
        f"{metric.candidate_center_direction_accuracy * Decimal('100'):.2f}% | "
        f"{metric.retained_direction_accuracy * Decimal('100'):.2f}% |"
        for metric in overall
    )
    lines.extend(
        [
            "",
            "## 劣化したサブグループ（標本数10以上）",
            "",
        ]
    )
    if subgroup_regressions:
        lines.extend(
            [
                "| 予測期間 | グループ | 標本数 | Consensus RMSE | 候補 RMSE | 改善率 |",
                "| ---: | --- | ---: | ---: | ---: | ---: |",
                *[
                    f"| {metric.horizon_days} | `{metric.group_type}={metric.group_value}` | "
                    f"{metric.sample_count} | {metric.consensus_rmse:.4f} | "
                    f"{metric.candidate_price_rmse:.4f} | "
                    f"{metric.relative_rmse_improvement * Decimal('100'):.2f}% |"
                    for metric in subgroup_regressions[:20]
                ],
            ]
        )
    else:
        lines.append("- 該当なし")
    lines.extend(
        [
            "",
            "## 再現評価ゲート",
            "",
            f"- 通過: **{'はい' if report.runtime_review_eligible else 'いいえ'}**",
            *[f"- {reason}" for reason in report.gate_reasons],
            "",
            "この再現評価を通過しても、ランタイム採用を自動承認しない。"
            "後日の暦期間を使った監査が引き続き必要。",
            "",
        ]
    )
    if origin_times:
        lines.insert(
            9,
            f"- Origin 範囲: {min(origin_times).isoformat()} ～ {max(origin_times).isoformat()}",
        )
    return "\n".join(lines)


def _write_metrics(path: Path, metrics: list[ConservativeCalibrationMetric]) -> None:
    fieldnames = list(ConservativeCalibrationMetric.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for metric in metrics:
            writer.writerow(metric.model_dump(mode="json"))


def _write_points(
    path: Path,
    observations: list[ConservativeCalibrationObservation],
    profiles: list[HorizonConservativeCalibrationProfile],
) -> None:
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
        "moving_average_3_return",
        "candidate_price_center_return",
        "retained_direction_return",
        "actual_return",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for observation in observations:
            prediction = apply_horizon_conditioned_calibration(
                observation, profiles_by_horizon[observation.horizon_days]
            )
            writer.writerow(
                {
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
                    "moving_average_3_return": observation.conservative_returns["moving_average_3"],
                    "candidate_price_center_return": prediction.price_center_return,
                    "retained_direction_return": prediction.direction_return,
                    "actual_return": observation.actual_return,
                }
            )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
