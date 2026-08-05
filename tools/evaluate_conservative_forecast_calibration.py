from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.forecast import (  # noqa: E402
    CONSENSUS_MODEL_NAME,
    ConservativeCalibrationEvaluationReport,
    ConservativeCalibrationMetric,
    ConservativeCalibrationObservation,
    HorizonConservativeCalibrationProfile,
    MovingAverageForecastModel,
    apply_horizon_conditioned_calibration,
    build_conservative_calibration_report,
    evaluate_horizon_conditioned_calibration,
    fit_horizon_conditioned_calibration,
    load_forecast_evaluation_dataset,
)
from tools.compare_forecast_baselines import rolling_origin_indexes  # noqa: E402

SPLITS = ("tuning", "validation", "audit")
HORIZONS = (20, 60)
QUANTILE_MODEL_NAME = "advanced_quantile"
MOVING_AVERAGE_MODEL_NAME = "moving_average_3"


@dataclass(frozen=True)
class CalibrationCohortSource:
    name: str
    ohlcv_path: Path
    metadata_path: Path
    manifest_path: Path
    advanced_report_root: Path


@dataclass(frozen=True)
class _AdvancedPoint:
    symbol: str
    market: str
    asset_type: str
    regime: str
    horizon_days: int
    origin_at: datetime
    target_at: datetime
    predicted_return: Decimal
    actual_return: Decimal


PointKey = tuple[str, int, datetime, datetime]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fit horizon-conditioned conservative price-center calibration from tuning data "
            "and apply the frozen profiles to validation and audit splits."
        )
    )
    parser.add_argument("--primary-ohlcv", default="data/phase34_evaluation/ohlcv.csv")
    parser.add_argument("--primary-metadata", default="data/phase34_evaluation/symbols.csv")
    parser.add_argument(
        "--primary-manifest",
        default="data/phase34_evaluation/splits/phase34_split_manifest.csv",
    )
    parser.add_argument("--primary-report-root", default="reports/2026-07-19_1300")
    parser.add_argument(
        "--extended-ohlcv",
        default="reports/2026-07-19_1300/extended_live_data/ohlcv.csv",
    )
    parser.add_argument(
        "--extended-metadata",
        default="reports/2026-07-19_1300/extended_live_data/symbols.csv",
    )
    parser.add_argument(
        "--extended-manifest",
        default=("reports/2026-07-19_1300/extended_live_data/splits/" "phase34_split_manifest.csv"),
    )
    parser.add_argument(
        "--extended-report-root",
        default="reports/2026-07-19_1300/extended_live_backtest",
    )
    parser.add_argument(
        "--output",
        default="reports/2026-07-19_1300/conservative_forecast_calibration",
    )
    parser.add_argument("--required-bars", type=int, default=180)
    parser.add_argument("--recent-bars", type=int, default=750)
    parser.add_argument("--max-origins", type=int, default=3)
    args = parser.parse_args(argv)
    if args.required_bars < 1:
        parser.error("--required-bars must be at least 1")
    if args.recent_bars < max(HORIZONS) + 40:
        parser.error("--recent-bars is too small for the configured horizons")
    if args.max_origins < 1:
        parser.error("--max-origins must be at least 1")

    sources = (
        CalibrationCohortSource(
            name="phase34_primary",
            ohlcv_path=Path(args.primary_ohlcv),
            metadata_path=Path(args.primary_metadata),
            manifest_path=Path(args.primary_manifest),
            advanced_report_root=Path(args.primary_report_root),
        ),
        CalibrationCohortSource(
            name="extended_live",
            ohlcv_path=Path(args.extended_ohlcv),
            metadata_path=Path(args.extended_metadata),
            manifest_path=Path(args.extended_manifest),
            advanced_report_root=Path(args.extended_report_root),
        ),
    )
    observations: list[ConservativeCalibrationObservation] = []
    load_warnings: list[str] = []
    for source in sources:
        loaded, warnings = load_cohort_calibration_observations(
            source,
            required_bars=args.required_bars,
            recent_bars=args.recent_bars,
            max_origins=args.max_origins,
        )
        observations.extend(loaded)
        load_warnings.extend(warnings)
    tuning = [observation for observation in observations if observation.split == "tuning"]
    profiles = fit_horizon_conditioned_calibration(tuning)
    metrics = evaluate_horizon_conditioned_calibration(observations, profiles)
    report = build_conservative_calibration_report(profiles, metrics)
    if load_warnings:
        report = report.model_copy(
            update={"warnings": [*report.warnings, *load_warnings]},
        )
    paths = write_conservative_calibration_artifacts(
        report,
        observations,
        Path(args.output),
        recent_bars=args.recent_bars,
        max_origins=args.max_origins,
    )
    counts: dict[str, int] = {
        split: sum(observation.split == split for observation in observations) for split in SPLITS
    }
    print(f"observations: {len(observations)} ({counts})")
    print(f"runtime review eligible: {'yes' if report.runtime_review_eligible else 'no'}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def load_cohort_calibration_observations(
    source: CalibrationCohortSource,
    *,
    required_bars: int,
    recent_bars: int,
    max_origins: int,
) -> tuple[list[ConservativeCalibrationObservation], list[str]]:
    """Join advanced and classic predictions at identical origin/target keys."""

    dataset = load_forecast_evaluation_dataset(
        source.ohlcv_path,
        source.metadata_path,
        required_bar_count=required_bars,
    )
    split_by_symbol = _load_split_manifest(source.manifest_path)
    moving_average_points: dict[PointKey, Decimal] = {}
    model = MovingAverageForecastModel(window=3)
    for case in dataset.cases:
        split = split_by_symbol.get(case.symbol)
        if split not in SPLITS:
            continue
        bars = sorted(case.bars, key=lambda bar: bar.ts)[-recent_bars:]
        for horizon in HORIZONS:
            for origin_index in rolling_origin_indexes(
                len(bars), horizon_days=horizon, max_origins=max_origins
            ):
                history = bars[: origin_index + 1]
                origin = bars[origin_index]
                target = bars[origin_index + horizon]
                if origin.close <= 0:
                    continue
                prediction = model.predict(history, horizon_days=horizon)
                key = (case.symbol, horizon, origin.ts, target.ts)
                moving_average_points[key] = prediction.forecast_close / origin.close - Decimal("1")

    observations: list[ConservativeCalibrationObservation] = []
    warnings: list[str] = []
    for split in SPLITS:
        advanced_path = source.advanced_report_root / split / "forecast_model_validation_points.csv"
        advanced = _load_advanced_points(advanced_path)
        consensus_points = {
            key: point
            for (model_name, key), point in advanced.items()
            if model_name == CONSENSUS_MODEL_NAME
        }
        quantile_points = {
            key: point
            for (model_name, key), point in advanced.items()
            if model_name == QUANTILE_MODEL_NAME
        }
        missing_quantile = 0
        missing_moving_average = 0
        for key, consensus in sorted(consensus_points.items()):
            quantile = quantile_points.get(key)
            moving_average_return = moving_average_points.get(key)
            if quantile is None:
                missing_quantile += 1
                continue
            if moving_average_return is None:
                missing_moving_average += 1
                continue
            if quantile.actual_return != consensus.actual_return:
                raise ValueError(f"actual return mismatch for {source.name} {key}")
            observations.append(
                ConservativeCalibrationObservation(
                    cohort=source.name,
                    split=split,
                    symbol=consensus.symbol,
                    market=consensus.market,
                    asset_type=consensus.asset_type,
                    regime=consensus.regime,
                    horizon_days=consensus.horizon_days,
                    origin_at=consensus.origin_at,
                    target_at=consensus.target_at,
                    consensus_return=consensus.predicted_return,
                    actual_return=consensus.actual_return,
                    conservative_returns={
                        QUANTILE_MODEL_NAME: quantile.predicted_return,
                        MOVING_AVERAGE_MODEL_NAME: moving_average_return,
                    },
                )
            )
        if missing_quantile or missing_moving_average:
            warnings.append(
                f"{source.name}/{split}: unmatched points "
                f"quantile={missing_quantile}, moving_average={missing_moving_average}。"
            )
    return observations, warnings


def write_conservative_calibration_artifacts(
    report: ConservativeCalibrationEvaluationReport,
    observations: list[ConservativeCalibrationObservation],
    output_dir: Path,
    *,
    recent_bars: int,
    max_origins: int,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": output_dir / "horizon_conditioned_conservative_calibration.md",
        "profile": output_dir / "horizon_conditioned_conservative_calibration_profile.json",
        "metrics": output_dir / "horizon_conditioned_conservative_calibration_metrics.csv",
        "points": output_dir / "horizon_conditioned_conservative_calibration_points.csv",
    }
    paths["summary"].write_text(
        render_conservative_calibration_markdown(
            report,
            recent_bars=recent_bars,
            max_origins=max_origins,
        ),
        encoding="utf-8",
        newline="\n",
    )
    paths["profile"].write_text(
        json.dumps(
            {
                "model_name": report.model_name,
                "runtime_review_eligible": report.runtime_review_eligible,
                "profiles": [profile.model_dump(mode="json") for profile in report.profiles],
                "gate_reasons": report.gate_reasons,
                "warnings": report.warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_metrics(paths["metrics"], report.metrics)
    _write_points(paths["points"], observations, report.profiles)
    return paths


def render_conservative_calibration_markdown(
    report: ConservativeCalibrationEvaluationReport,
    *,
    recent_bars: int,
    max_origins: int,
) -> str:
    lines = [
        "# Horizon-conditioned Conservative Forecast Calibration",
        "",
        "## Scope",
        "",
        "- Phase 34 primary / extended liveのsymbol非重複splitを統合",
        f"- 各銘柄の直近{recent_bars}営業日、20日・60日horizon、最大{max_origins} rolling origins",
        "- profileはtuningだけで決定し、validation / sealed auditでは再調整しない",
        "- price centerは保守baselineへ縮小し、direction headは元のadvanced consensusを保持",
        "- evaluation-only。Cockpit、Ranking、Forecast APIのruntime値は変更しない",
        "",
        "## Frozen profiles",
        "",
        "| Horizon | Conservative model | Consensus weight | Conservative weight | Samples | Consensus RMSE | Candidate RMSE | Improvement | Center direction | Retained direction |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for profile in report.profiles:
        lines.append(
            f"| {profile.horizon_days} | `{profile.conservative_model_name}` | "
            f"{profile.consensus_weight:.2f} | {profile.conservative_weight:.2f} | "
            f"{profile.tuning_sample_count} | {profile.tuning_consensus_rmse:.4f} | "
            f"{profile.tuning_candidate_rmse:.4f} | "
            f"{profile.tuning_relative_rmse_improvement * Decimal('100'):.2f}% | "
            f"{profile.tuning_candidate_center_direction_accuracy * Decimal('100'):.2f}% | "
            f"{profile.tuning_retained_direction_accuracy * Decimal('100'):.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Validation and sealed audit",
            "",
            "| Split | Horizon | Samples | Consensus RMSE | Candidate RMSE | Improvement | Consensus direction | Center direction | Retained direction | Max abs return |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    overall = sorted(
        (
            metric
            for metric in report.metrics
            if metric.group_type == "overall" and metric.split in ("validation", "audit")
        ),
        key=lambda metric: (SPLITS.index(metric.split), metric.horizon_days),
    )
    for metric in overall:
        lines.append(
            f"| {metric.split} | {metric.horizon_days} | {metric.sample_count} | "
            f"{metric.consensus_rmse:.4f} | {metric.candidate_price_rmse:.4f} | "
            f"{metric.relative_rmse_improvement * Decimal('100'):.2f}% | "
            f"{metric.consensus_direction_accuracy * Decimal('100'):.2f}% | "
            f"{metric.candidate_center_direction_accuracy * Decimal('100'):.2f}% | "
            f"{metric.retained_direction_accuracy * Decimal('100'):.2f}% | "
            f"{metric.maximum_absolute_candidate_return:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Gate",
            "",
            f"- Runtime review eligible: **{'yes' if report.runtime_review_eligible else 'no'}**",
            *[f"- {reason}" for reason in report.gate_reasons],
            "",
            "## Largest subgroup regressions",
            "",
            "| Split | Horizon | Group | Samples | Consensus RMSE | Candidate RMSE | Delta |",
            "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    regressions = sorted(
        (
            metric
            for metric in report.metrics
            if metric.split in ("validation", "audit")
            and metric.group_type != "overall"
            and metric.sample_count >= 10
            and metric.candidate_price_rmse > metric.consensus_rmse
        ),
        key=lambda metric: metric.candidate_price_rmse - metric.consensus_rmse,
        reverse=True,
    )[:20]
    if regressions:
        for metric in regressions:
            lines.append(
                f"| {metric.split} | {metric.horizon_days} | "
                f"{metric.group_type}={metric.group_value} | {metric.sample_count} | "
                f"{metric.consensus_rmse:.4f} | {metric.candidate_price_rmse:.4f} | "
                f"{metric.candidate_price_rmse - metric.consensus_rmse:+.4f} |"
            )
    else:
        lines.append("| - | - | 重大・集計対象の劣化なし | - | - | - | - |")
    lines.extend(["", "## Warnings", "", *[f"- {warning}" for warning in report.warnings], ""])
    return "\n".join(lines)


def _load_split_manifest(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"split manifest not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["symbol"].strip(): row["split"].strip()
            for row in csv.DictReader(handle)
            if row.get("symbol", "").strip() and row.get("split", "").strip()
        }


def _load_advanced_points(path: Path) -> dict[tuple[str, PointKey], _AdvancedPoint]:
    if not path.is_file():
        raise ValueError(f"advanced validation points not found: {path}")
    points: dict[tuple[str, PointKey], _AdvancedPoint] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            model_name = row["model_name"]
            if model_name not in (CONSENSUS_MODEL_NAME, QUANTILE_MODEL_NAME):
                continue
            point = _AdvancedPoint(
                symbol=row["symbol"],
                market=row["market"],
                asset_type=row["asset_type"],
                regime=row["regime"],
                horizon_days=int(row["horizon_days"]),
                origin_at=datetime.fromisoformat(row["origin_at"]),
                target_at=datetime.fromisoformat(row["target_at"]),
                predicted_return=Decimal(row["predicted_return"]),
                actual_return=Decimal(row["actual_return"]),
            )
            key: PointKey = (
                point.symbol,
                point.horizon_days,
                point.origin_at,
                point.target_at,
            )
            points[(model_name, key)] = point
    return points


def _write_metrics(path: Path, metrics: list[ConservativeCalibrationMetric]) -> None:
    if not metrics:
        raise ValueError("calibration metrics are required")
    fieldnames = list(metrics[0].model_dump())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for metric in metrics:
            writer.writerow(metric.model_dump())


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
        "advanced_quantile_return",
        "moving_average_3_return",
        "candidate_price_center_return",
        "retained_direction_return",
        "actual_return",
        "conservative_model_name",
        "consensus_weight",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for observation in observations:
            profile = profiles_by_horizon[observation.horizon_days]
            prediction = apply_horizon_conditioned_calibration(observation, profile)
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
                    "advanced_quantile_return": observation.conservative_returns[
                        QUANTILE_MODEL_NAME
                    ],
                    "moving_average_3_return": observation.conservative_returns[
                        MOVING_AVERAGE_MODEL_NAME
                    ],
                    "candidate_price_center_return": prediction.price_center_return,
                    "retained_direction_return": prediction.direction_return,
                    "actual_return": observation.actual_return,
                    "conservative_model_name": profile.conservative_model_name,
                    "consensus_weight": profile.consensus_weight,
                }
            )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
