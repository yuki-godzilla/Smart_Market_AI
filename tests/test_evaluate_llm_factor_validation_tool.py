import json

from tools.evaluate_llm_factor_validation import main


def test_llm_factor_validation_tool_writes_explicit_non_integration_report(tmp_path) -> None:
    exit_code = main(["--output", str(tmp_path), "--horizons", "1"])

    assert exit_code == 0
    markdown = (tmp_path / "llm_factor_validation_report.md").read_text(encoding="utf-8")
    payload = json.loads(
        (tmp_path / "llm_factor_validation_report.json").read_text(encoding="utf-8")
    )
    assert "should_integrate_into_forecast_now: false" in markdown
    assert payload["recommendation"]["should_integrate_into_forecast_now"] is False
    assert payload["summary"]["sample_count"] > 0
