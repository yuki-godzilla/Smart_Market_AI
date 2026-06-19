from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    from backend.assistant.agent_evaluation import (
        evaluate_agent_evaluation_case,
        load_agent_evaluation_cases,
    )

    parser = argparse.ArgumentParser(
        description="Evaluate SMAI Assistant agent plan fixtures without network access.",
    )
    parser.add_argument(
        "--fixtures",
        default="tests/fixtures/assistant_agent_plans",
        help="Directory containing Agent Evaluation JSON fixtures.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON report path. Raw provider bodies are not written.",
    )
    parser.add_argument(
        "--live-gateway",
        choices=["false"],
        default="false",
        help="Reserved for future opt-in live checks. Regular evaluation is fixture-only.",
    )
    args = parser.parse_args(argv)

    cases = load_agent_evaluation_cases(args.fixtures)
    case_results = [(case, evaluate_agent_evaluation_case(case)) for case in cases]
    matched = sum(1 for case, result in case_results if result.passed is case.expected_pass)
    mismatched = len(case_results) - matched
    payload = {
        "fixtures": str(Path(args.fixtures)),
        "live_gateway": False,
        "summary": {
            "total": len(case_results),
            "matched_expected": matched,
            "mismatched_expected": mismatched,
        },
        "results": [
            {
                "expected_pass": case.expected_pass,
                "matched_expected": result.passed is case.expected_pass,
                **result.model_dump(mode="json"),
            }
            for case, result in case_results
        ],
    }

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    for case, result in case_results:
        ok = result.passed is case.expected_pass
        status = "PASS" if ok else "FAIL"
        actual = "passed" if result.passed else "failed"
        expected = "pass" if case.expected_pass else "fail"
        print(f"{status} {result.case_id} expected={expected} actual={actual}")
        if not ok:
            print(result.summary)
    print(f"assistant agent evaluation: {matched}/{len(case_results)} matched expected")
    return 0 if mismatched == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
