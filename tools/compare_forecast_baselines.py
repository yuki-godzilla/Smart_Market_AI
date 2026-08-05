from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SPLITS = ("tuning", "validation", "audit")
HORIZONS = (20, 60)
GROUP_TYPES = ("overall", "market", "asset_type", "regime")


@dataclass(frozen=True)
class ComparisonPoint:
    split: str
    symbol: str
    market: str
    asset_type: str
    regime: str
    model_name: str
    horizon_days: int
    origin_at: str
    target_at: str
    predicted_return: Decimal
    actual_return: Decimal


@dataclass(frozen=True)
class ComparisonMetric:
    split: str
    group_type: str
    group_value: str
    model_name: str
    horizon_days: int
    symbol_count: int
    sample_count: int
    mae: Decimal
    rmse: Decimal
    direction_accuracy: Decimal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare classic price baselines with persisted advanced-model rolling-origin points."
        ),
    )
    parser.add_argument("--ohlcv", default="data/phase34_evaluation/ohlcv.csv")
    parser.add_argument("--metadata", default="data/phase34_evaluation/symbols.csv")
    parser.add_argument(
        "--manifest",
        default="data/phase34_evaluation/splits/phase34_split_manifest.csv",
    )
    parser.add_argument("--advanced-report-root", default="reports/2026-07-19_1300")
    parser.add_argument(
        "--output",
        default="reports/2026-07-19_1300/forecast_model_broad_comparison",
    )
    parser.add_argument("--required-bars", type=int, default=180)
    parser.add_argument("--recent-bars", type=int, default=750)
    parser.add_argument("--max-origins", type=int, default=3)
    args = parser.parse_args(argv)

    if args.recent_bars < max(HORIZONS) + 40:
        parser.error("--recent-bars is too small for the configured horizons")
    if args.max_origins < 1:
        parser.error("--max-origins must be at least 1")

    points: list[ComparisonPoint] = []
    report_root = Path(args.advanced_report_root)
    for split in SPLITS:
        points.extend(_load_advanced_points(report_root, split))
        points.extend(
            _classic_points(
                Path(args.ohlcv),
                Path(args.metadata),
                Path(args.manifest),
                split,
                required_bars=args.required_bars,
                recent_bars=args.recent_bars,
                max_origins=args.max_origins,
            )
        )

    metrics = aggregate_comparison_points(points)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "forecast_model_broad_comparison.csv"
    summary_path = output_dir / "forecast_model_broad_comparison.md"
    _write_metrics(metrics_path, metrics)
    summary_path.write_text(
        render_comparison_markdown(
            metrics,
            recent_bars=args.recent_bars,
            max_origins=args.max_origins,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"points: {len(points)}")
    print(f"metrics: {metrics_path}")
    print(f"summary: {summary_path}")
    return 0


def rolling_origin_indexes(
    bar_count: int,
    *,
    horizon_days: int,
    max_origins: int,
) -> list[int]:
    """Match forecast evaluation's future-safe, evenly spaced origin selection."""

    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1")
    if max_origins < 1:
        raise ValueError("max_origins must be at least 1")
    minimum_history = max(40, horizon_days + 24)
    first = minimum_history - 1
    last = bar_count - horizon_days - 1
    if last < first:
        return []
    available = list(range(first, last + 1))
    if len(available) <= max_origins:
        return available
    if max_origins == 1:
        return [available[-1]]
    return sorted(
        {
            available[round(index * (len(available) - 1) / (max_origins - 1))]
            for index in range(max_origins)
        }
    )


def aggregate_comparison_points(
    points: Iterable[ComparisonPoint],
) -> list[ComparisonMetric]:
    grouped: dict[tuple[str, str, str, str, int], list[ComparisonPoint]] = defaultdict(list)
    for point in points:
        for group_type in GROUP_TYPES:
            grouped[
                (
                    point.split,
                    group_type,
                    _group_value(point, group_type),
                    point.model_name,
                    point.horizon_days,
                )
            ].append(point)

    metrics: list[ComparisonMetric] = []
    for key in sorted(grouped):
        split, group_type, group_value, model_name, horizon_days = key
        selected = grouped[key]
        errors = [point.predicted_return - point.actual_return for point in selected]
        matches = sum(
            1 for point in selected if _sign(point.predicted_return) == _sign(point.actual_return)
        )
        metrics.append(
            ComparisonMetric(
                split=split,
                group_type=group_type,
                group_value=group_value,
                model_name=model_name,
                horizon_days=horizon_days,
                symbol_count=len({point.symbol for point in selected}),
                sample_count=len(selected),
                mae=_mean(abs(error) for error in errors),
                rmse=_root_mean_square(errors),
                direction_accuracy=_ratio(matches, len(selected)),
            )
        )
    return metrics


def render_comparison_markdown(
    metrics: list[ComparisonMetric],
    *,
    recent_bars: int = 750,
    max_origins: int = 3,
) -> str:
    overall = [
        metric
        for metric in metrics
        if metric.group_type == "overall" and metric.group_value == "all"
    ]
    lines = [
        "# Forecast Model Broad Comparison",
        "",
        "## Scope",
        "",
        "- Phase 34 の symbol-disjoint tuning / validation / audit split を維持",
        f"- 各銘柄の直近{recent_bars}営業日、20日・60日 horizon、"
        f"最大{max_origins} rolling origins",
        "- 旧モデルとadvancedモデルを同じorigin / targetで比較",
        "- 最終判断は未使用audit splitを優先し、単一指標だけで採用しない",
        "",
        "## Overall leaderboard",
        "",
    ]
    for split in SPLITS:
        lines.extend([f"### {split}", ""])
        for horizon in HORIZONS:
            selected = sorted(
                (
                    metric
                    for metric in overall
                    if metric.split == split and metric.horizon_days == horizon
                ),
                key=lambda metric: (metric.rmse, -metric.direction_accuracy, metric.model_name),
            )
            lines.extend(
                [
                    f"#### {horizon}営業日",
                    "",
                    "| Rank | Model | Samples | RMSE | MAE | Direction |",
                    "| ---: | --- | ---: | ---: | ---: | ---: |",
                ]
            )
            lines.extend(
                f"| {rank} | `{metric.model_name}` | {metric.sample_count} | "
                f"{metric.rmse:.4f} | {metric.mae:.4f} | "
                f"{metric.direction_accuracy * 100:.2f}% |"
                for rank, metric in enumerate(selected, start=1)
            )
            if selected:
                best_direction = max(
                    selected,
                    key=lambda metric: (metric.direction_accuracy, -metric.rmse),
                )
                lines.extend(
                    [
                        "",
                        f"- lowest RMSE: `{selected[0].model_name}` ({selected[0].rmse:.4f})",
                        "- best direction: "
                        f"`{best_direction.model_name}` "
                        f"({best_direction.direction_accuracy * 100:.2f}%)",
                    ]
                )
            lines.append("")
    lines.extend(
        [
            "## Interpretation rule",
            "",
            "RMSE最小だけでは採用しません。validationとauditの両方で、20日・60日の"
            "RMSEを一貫して改善し、方向一致率を悪化させず、market / asset type / regime別の"
            "重大劣化がない候補だけをruntime consensusへ進めます。",
            "",
        ]
    )
    return "\n".join(lines)


def _classic_points(
    ohlcv_path: Path,
    metadata_path: Path,
    manifest_path: Path,
    split: str,
    *,
    required_bars: int,
    recent_bars: int,
    max_origins: int,
) -> list[ComparisonPoint]:
    from backend.forecast.dataset import load_forecast_evaluation_dataset
    from backend.forecast.service import (
        MomentumForecastModel,
        MovingAverageForecastModel,
        NaiveForecastModel,
    )

    dataset = load_forecast_evaluation_dataset(
        ohlcv_path,
        metadata_path,
        required_bar_count=required_bars,
    )
    split_symbols = _load_split_symbols(manifest_path, split)
    models = (
        NaiveForecastModel(),
        MovingAverageForecastModel(window=3),
        MomentumForecastModel(lookback=3),
    )
    points: list[ComparisonPoint] = []
    for case in dataset.cases:
        if case.symbol not in split_symbols:
            continue
        bars = sorted(case.bars, key=lambda bar: bar.ts)[-recent_bars:]
        for horizon in HORIZONS:
            for origin_index in rolling_origin_indexes(
                len(bars),
                horizon_days=horizon,
                max_origins=max_origins,
            ):
                history = bars[: origin_index + 1]
                origin = bars[origin_index]
                target = bars[origin_index + horizon]
                if origin.close <= 0:
                    continue
                actual_return = (target.close / origin.close) - Decimal("1")
                for model in models:
                    prediction = model.predict(history, horizon_days=horizon)
                    points.append(
                        ComparisonPoint(
                            split=split,
                            symbol=case.symbol,
                            market=case.market,
                            asset_type=case.asset_type,
                            regime=case.regime,
                            model_name=model.name,
                            horizon_days=horizon,
                            origin_at=origin.ts.isoformat(),
                            target_at=target.ts.isoformat(),
                            predicted_return=(prediction.forecast_close / origin.close)
                            - Decimal("1"),
                            actual_return=actual_return,
                        )
                    )
    return points


def _load_split_symbols(path: Path, split: str) -> set[str]:
    if not path.is_file():
        raise ValueError(f"split manifest not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["symbol"].strip()
            for row in csv.DictReader(handle)
            if row.get("split", "").strip() == split and row.get("symbol", "").strip()
        }


def _load_advanced_points(report_root: Path, split: str) -> list[ComparisonPoint]:
    path = report_root / split / "forecast_model_validation_points.csv"
    if not path.is_file():
        raise ValueError(f"advanced validation points not found: {path}")
    points: list[ComparisonPoint] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            points.append(
                ComparisonPoint(
                    split=split,
                    symbol=row["symbol"],
                    market=row["market"],
                    asset_type=row["asset_type"],
                    regime=row["regime"],
                    model_name=row["model_name"],
                    horizon_days=int(row["horizon_days"]),
                    origin_at=row["origin_at"],
                    target_at=row["target_at"],
                    predicted_return=Decimal(row["predicted_return"]),
                    actual_return=Decimal(row["actual_return"]),
                )
            )
    return points


def _write_metrics(path: Path, metrics: list[ComparisonMetric]) -> None:
    fieldnames = list(ComparisonMetric.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for metric in metrics:
            writer.writerow(asdict(metric))


def _group_value(point: ComparisonPoint, group_type: str) -> str:
    if group_type == "overall":
        return "all"
    return str(getattr(point, group_type))


def _mean(values: Iterable[Decimal]) -> Decimal:
    selected = list(values)
    if not selected:
        return Decimal("0.0000")
    return _decimal(sum(selected, Decimal("0")) / Decimal(len(selected)))


def _root_mean_square(values: Iterable[Decimal]) -> Decimal:
    selected = list(values)
    if not selected:
        return Decimal("0.0000")
    mean_square = sum((value * value for value in selected), Decimal("0")) / Decimal(len(selected))
    return _decimal(mean_square.sqrt())


def _ratio(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return _decimal(Decimal(numerator) / Decimal(denominator))


def _decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
