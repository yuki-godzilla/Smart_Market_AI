from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRED_COLUMNS = {
    "symbol",
    "evaluation_date",
    "baseline_rank",
    "actual_positive",
    "review_status",
    "run_status",
}


def main(argv: list[str] | None = None) -> int:
    from backend.llm_factor.material_evaluation import (
        LLMMaterialEvaluationCase,
        write_llm_material_evaluation_outputs,
    )

    parser = argparse.ArgumentParser(
        description="Create the Phase 36 LLM material evaluation artifacts from a labeled CSV."
    )
    parser.add_argument("--cases-csv", required=True)
    parser.add_argument("--output", default="reports/llm_material_evaluation")
    args = parser.parse_args(argv)
    try:
        cases = _read_cases(Path(args.cases_csv), LLMMaterialEvaluationCase)
    except (OSError, ValueError) as exc:
        print(f"Unable to read material evaluation cases: {exc}", file=sys.stderr)
        return 2
    paths = write_llm_material_evaluation_outputs(cases, Path(args.output))
    print(f"evaluation cases: {len(cases)}")
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


def _read_cases(path: Path, model_type: type) -> list:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
        cases = []
        for line_number, row in enumerate(reader, start=2):
            try:
                cases.append(
                    model_type(
                        symbol=_required(row, "symbol"),
                        evaluation_date=date.fromisoformat(_required(row, "evaluation_date")),
                        baseline_rank=int(_required(row, "baseline_rank")),
                        actual_positive=_bool(_required(row, "actual_positive")),
                        review_status=_required(row, "review_status"),
                        run_status=_required(row, "run_status"),
                        cache_hit=_bool(row.get("cache_hit") or "false"),
                        latency_ms=_optional_int(row.get("latency_ms")),
                        material_relevance_score=_optional_decimal(
                            row.get("material_relevance_score")
                        ),
                        adverse_material_detected=_bool(
                            row.get("adverse_material_detected") or "false"
                        ),
                        dividend_trap_detected=_bool(row.get("dividend_trap_detected") or "false"),
                        adverse_material_expected=_optional_bool(
                            row.get("adverse_material_expected")
                        ),
                        dividend_trap_expected=_optional_bool(row.get("dividend_trap_expected")),
                        failure_reason=_optional_text(row.get("failure_reason")),
                    )
                )
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError(f"invalid row {line_number}: {exc}") from exc
    return cases


def _required(row: dict[str, str | None], name: str) -> str:
    value = (row.get(name) or "").strip()
    if not value:
        raise ValueError(f"{name} is empty")
    return value


def _optional_text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean: {value}")


def _optional_bool(value: str | None) -> bool | None:
    return _bool(value) if value and value.strip() else None


def _optional_int(value: str | None) -> int | None:
    return int(value) if value and value.strip() else None


def _optional_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value and value.strip() else None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
