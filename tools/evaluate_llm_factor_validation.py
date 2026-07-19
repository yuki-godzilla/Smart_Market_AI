from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    from backend.llm_factor import (
        LLMFactorValidationConfig,
        build_llm_factor_validation_report_json,
        build_llm_factor_validation_report_markdown,
        load_llm_factor_historical_fixture_pack,
        run_llm_factor_validation_report,
    )

    parser = argparse.ArgumentParser(
        description="Evaluate deterministic SMAI LLM material-factor fixtures.",
    )
    parser.add_argument("--output", default="reports/llm_factor_validation")
    parser.add_argument("--horizons", nargs="+", type=int, default=[1, 5, 20])
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--top-quantile", type=float, default=0.8)
    args = parser.parse_args(argv)

    config = LLMFactorValidationConfig(
        horizons=args.horizons,
        top_n=args.top_n,
        top_quantile=args.top_quantile,
    )
    report = run_llm_factor_validation_report(
        load_llm_factor_historical_fixture_pack(),
        config,
    )
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "llm_factor_validation_report.json"
    markdown_path = output_dir / "llm_factor_validation_report.md"
    json_path.write_text(
        build_llm_factor_validation_report_json(report) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(
        build_llm_factor_validation_report_markdown(report),
        encoding="utf-8",
        newline="\n",
    )
    print(f"fixture: {report.fixture_id}@{report.fixture_version}")
    print(f"samples: {report.summary.sample_count}")
    print(f"recommendation: {report.recommendation.status}")
    print(f"json: {json_path}")
    print(f"markdown: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
