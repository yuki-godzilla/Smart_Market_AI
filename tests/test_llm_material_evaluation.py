from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from backend.llm_factor.material_evaluation import (
    LLMMaterialEvaluationCase,
    decide_llm_material_adoption,
    summarize_llm_material_evaluation,
    write_llm_material_evaluation_outputs,
)
from tools.evaluate_llm_material_assessment import _read_cases


def _case(
    index: int,
    *,
    actual_positive: bool,
    review_status: Literal["retain", "caution", "unavailable"] = "retain",
    run_status: Literal["completed", "failed", "skipped"] = "completed",
    cache_hit: bool = False,
) -> LLMMaterialEvaluationCase:
    return LLMMaterialEvaluationCase(
        symbol=f"{index:04d}.T",
        evaluation_date=date(2026, 1, 1) + timedelta(days=index % 3),
        baseline_rank=(index % 10) + 1,
        actual_positive=actual_positive,
        review_status=review_status,
        run_status=run_status,
        cache_hit=cache_hit,
        latency_ms=120 + index if run_status == "completed" else None,
        adverse_material_detected=review_status == "caution",
        adverse_material_expected=not actual_positive,
        dividend_trap_detected=index % 7 == 0,
        dividend_trap_expected=index % 7 == 0,
        failure_reason="gateway_timeout" if run_status == "failed" else None,
    )


def test_material_evaluation_is_offline_and_preserves_positive_candidate_coverage():
    cases = [
        _case(1, actual_positive=True),
        _case(2, actual_positive=False, review_status="caution"),
        _case(3, actual_positive=False),
        _case(4, actual_positive=True, cache_hit=True),
        _case(7, actual_positive=True),
    ]

    summary = summarize_llm_material_evaluation(cases)

    assert summary.baseline_false_positive_count == 2
    assert summary.retained_false_positive_count == 1
    assert summary.false_positive_reduction_count == 1
    assert summary.positive_candidate_coverage == Decimal("1.00")
    assert summary.cache_hit_rate == Decimal("0.20")
    assert summary.adverse_precision == Decimal("1.00")
    assert summary.dividend_trap_recall == Decimal("1.00")


def test_material_adoption_is_badges_only_even_when_sample_passes_gate():
    cases = [
        _case(
            index,
            actual_positive=index % 2 == 0,
            review_status="caution" if index % 2 else "retain",
        )
        for index in range(30)
    ]

    decision = decide_llm_material_adoption(summarize_llm_material_evaluation(cases))

    assert decision.status == "badge_only_candidate"
    assert decision.allow_badges is True
    assert decision.allow_rank_correction is False


def test_material_evaluation_writes_all_phase36_outputs(tmp_path):
    cases = [
        _case(1, actual_positive=True),
        _case(2, actual_positive=False, run_status="failed"),
    ]

    paths = write_llm_material_evaluation_outputs(cases, tmp_path)

    assert set(paths) == {
        "cases",
        "summary",
        "false_positive",
        "latency",
        "decision",
    }
    assert paths["cases"].read_text(encoding="utf-8-sig").startswith("symbol,")
    assert "通常Rankingの順位・スコアは変更していません" in paths["summary"].read_text(
        encoding="utf-8"
    )
    assert "ranking_rank_correction: false" in paths["decision"].read_text(encoding="utf-8")
    assert "gateway_timeout" in paths["latency"].read_text(encoding="utf-8")


def test_material_evaluation_csv_reader_accepts_the_runner_contract(tmp_path):
    path = tmp_path / "material_cases.csv"
    path.write_text(
        "symbol,evaluation_date,baseline_rank,actual_positive,review_status,run_status,"
        "cache_hit,latency_ms,adverse_material_detected,dividend_trap_detected\n"
        "AAA,2026-01-02,1,true,retain,completed,true,110,false,false\n",
        encoding="utf-8",
    )

    cases = _read_cases(path, LLMMaterialEvaluationCase)

    assert len(cases) == 1
    assert cases[0].cache_hit is True
    assert cases[0].latency_ms == 110
