from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.forecast import ForecastEvaluationCase

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    from backend.forecast import (
        evaluate_forecast_models,
        tune_forecast_adapters,
        write_forecast_evaluation_artifacts,
        write_forecast_tuning_artifacts,
    )
    from backend.forecast.dataset import (
        load_forecast_evaluation_dataset,
        write_forecast_dataset_coverage,
    )

    parser = argparse.ArgumentParser(
        description="Evaluate advanced forecast models from local CSV files.",
    )
    parser.add_argument("--ohlcv", default="data/marketdata/ohlcv.csv")
    parser.add_argument("--metadata", default="data/marketdata/symbol_universe.csv")
    parser.add_argument("--output", default="reports/forecast_evaluation")
    parser.add_argument("--required-bars", type=int, default=180)
    parser.add_argument(
        "--recent-bars",
        type=int,
        default=None,
        help="Limit each eligible symbol to its most recent N bars before evaluation.",
    )
    parser.add_argument("--max-origins", type=int, default=5)
    parser.add_argument(
        "--horizons",
        default="20,60",
        help="Comma-separated positive forecast horizons, for example 20,60,90,120.",
    )
    parser.add_argument(
        "--skip-tuning",
        action="store_true",
        help="Write evaluation artifacts without repeating bounded adapter tuning.",
    )
    args = parser.parse_args(argv)
    try:
        horizons = _parse_horizons(args.horizons)
    except ValueError as exc:
        parser.error(str(exc))
    minimum_recent_bars = max(120, max(horizons) + 24)
    if args.recent_bars is not None and args.recent_bars < minimum_recent_bars:
        parser.error(f"--recent-bars must be at least {minimum_recent_bars}")

    output_dir = Path(args.output)
    dataset = load_forecast_evaluation_dataset(
        Path(args.ohlcv),
        Path(args.metadata),
        required_bar_count=args.required_bars,
    )
    coverage_paths = write_forecast_dataset_coverage(dataset, output_dir)
    evaluation_cases = limit_recent_case_bars(dataset.cases, args.recent_bars)
    report = evaluate_forecast_models(
        evaluation_cases,
        horizons=horizons,
        max_origins=args.max_origins,
    )
    evaluation_paths = write_forecast_evaluation_artifacts(report, output_dir)
    tuning_paths = {}
    if not args.skip_tuning:
        tuning_paths = write_forecast_tuning_artifacts(
            tune_forecast_adapters(
                evaluation_cases,
                horizons=horizons,
                max_origins=args.max_origins,
            ),
            output_dir,
        )
    eligible = len(dataset.cases)
    print(f"forecast evaluation dataset: {eligible}/{len(dataset.coverage)} symbols eligible")
    for name, path in {**coverage_paths, **evaluation_paths, **tuning_paths}.items():
        print(f"{name}: {path}")
    if eligible == 0:
        print("No eligible symbols; add longer local OHLCV history before judging accuracy.")
    return 0


def limit_recent_case_bars(
    cases: Iterable[ForecastEvaluationCase],
    recent_bars: int | None,
) -> list[ForecastEvaluationCase]:
    """Return evaluation copies capped to a common recent-history window."""

    if recent_bars is None:
        return list(cases)
    if recent_bars < 120:
        raise ValueError("recent_bars must be at least 120")
    return [
        case.model_copy(
            update={
                "bars": sorted(case.bars, key=lambda bar: bar.ts)[-recent_bars:],
            }
        )
        for case in cases
    ]


def _parse_horizons(value: str) -> tuple[int, ...]:
    try:
        parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError("--horizons must contain comma-separated integers") from exc
    if not parsed:
        raise ValueError("--horizons must contain at least one horizon")
    if any(horizon < 1 for horizon in parsed):
        raise ValueError("--horizons must contain only positive integers")
    if len(parsed) != len(set(parsed)):
        raise ValueError("--horizons must not contain duplicates")
    return tuple(sorted(parsed))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
