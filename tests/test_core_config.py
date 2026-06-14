from pydantic import ValidationError

from backend.core.config import Settings, get_settings

FIXTURE_DIR = "tests/fixtures/config"


def test_settings_defaults_are_local_and_mock_first():
    settings = get_settings()

    assert settings.app.base_currency == "JPY"
    assert settings.dataaccess.provider == "mock"
    assert settings.dataaccess.allow_external_providers is False
    assert settings.dataaccess.cache.backend == "memory"
    assert settings.portfolio.solver.backend == "none"
    assert settings.scoring.weights.screening == 0.5
    assert settings.scoring.weights.research == 0.0
    assert settings.scoring.weights.risk_signal == 0.1
    assert settings.assistant.gateway.enabled is False
    assert settings.assistant.gateway.base_url == "http://127.0.0.1:8088"
    assert settings.assistant.gateway.context_answer_path == "/api/v1/context-answer"
    assert settings.assistant.gateway.timeout_seconds == 90.0
    assert settings.assistant.gateway.model is None
    assert settings.assistant.gateway.execution_mode == "auto"
    assert settings.assistant.gateway.environment_profile == "notebook"
    assert settings.assistant.gateway.preferred_profile is None


def test_settings_loads_yaml_overrides(monkeypatch):
    monkeypatch.setenv("SMAI_CONFIG_FILE", f"{FIXTURE_DIR}/local.yaml")

    settings = get_settings()

    assert settings.dataaccess.provider == "mock"
    assert settings.risk.thresholds.max_concentration == 0.3
    assert settings.risk.thresholds.min_dividend_yield == 0.02
    assert settings.portfolio.solver.backend == "none"
    assert settings.portfolio.solver.tolerance == 0.0001
    assert settings.scoring.weights.forecast_agreement == 0.25


def test_settings_loads_csv_example_config(monkeypatch):
    monkeypatch.setenv("SMAI_CONFIG_FILE", "config/csv_example.yaml")

    settings = get_settings()

    assert settings.dataaccess.provider == "csv"
    assert settings.dataaccess.csv_data_dir == "data/marketdata"


def test_settings_can_load_explicit_external_provider_opt_in():
    settings = Settings.model_validate(
        {
            "dataaccess": {
                "provider": "yahoo",
                "allow_external_providers": True,
            }
        }
    )

    assert settings.dataaccess.provider == "yahoo"
    assert settings.dataaccess.allow_external_providers is True


def test_settings_can_load_explicit_assistant_gateway_opt_in():
    settings = Settings.model_validate(
        {
            "assistant": {
                "gateway": {
                    "enabled": True,
                    "base_url": "http://127.0.0.1:8088",
                    "context_answer_path": "/api/v1/context-answer",
                    "timeout_seconds": 2.5,
                    "model": "qwen3:8b",
                    "execution_mode": "light",
                    "environment_profile": "notebook",
                    "preferred_profile": "assistant_fast",
                }
            }
        }
    )

    assert settings.assistant.gateway.enabled is True
    assert settings.assistant.gateway.base_url == "http://127.0.0.1:8088"
    assert settings.assistant.gateway.timeout_seconds == 2.5
    assert settings.assistant.gateway.model == "qwen3:8b"
    assert settings.assistant.gateway.execution_mode == "light"
    assert settings.assistant.gateway.environment_profile == "notebook"
    assert settings.assistant.gateway.preferred_profile == "assistant_fast"


def test_settings_rejects_unknown_yaml_keys(monkeypatch):
    monkeypatch.setenv("SMAI_CONFIG_FILE", f"{FIXTURE_DIR}/unknown_key.yaml")

    try:
        get_settings()
    except ValidationError as exc:
        assert exc.errors()[0]["type"] == "extra_forbidden"
    else:
        raise AssertionError("Settings YAML should reject unknown keys")


def test_settings_rejects_non_mapping_yaml(monkeypatch):
    monkeypatch.setenv("SMAI_CONFIG_FILE", f"{FIXTURE_DIR}/non_mapping.yaml")

    try:
        get_settings()
    except ValueError as exc:
        assert str(exc) == "Settings YAML must contain a mapping at the document root"
    else:
        raise AssertionError("Settings YAML should require a mapping root")


def test_settings_reject_unknown_keys():
    try:
        Settings(unknown=True)
    except ValidationError as exc:
        assert exc.errors()[0]["type"] == "extra_forbidden"
    else:
        raise AssertionError("Settings should reject unknown keys")


def test_settings_reject_invalid_scoring_weight_total():
    try:
        Settings.model_validate(
            {
                "scoring": {
                    "weights": {
                        "screening": 0.5,
                        "forecast_agreement": 0.5,
                        "data_quality": 0.5,
                        "risk_signal": 0.5,
                    }
                }
            }
        )
    except ValidationError as exc:
        assert "Scoring weights must sum to 1.0" in str(exc)
    else:
        raise AssertionError("Scoring weights should sum to 1.0")


def test_settings_accepts_disabled_by_default_research_scoring_weight():
    settings = Settings.model_validate(
        {
            "scoring": {
                "weights": {
                    "screening": 0.40,
                    "forecast_agreement": 0.20,
                    "data_quality": 0.20,
                    "research": 0.10,
                    "risk_signal": 0.10,
                }
            }
        }
    )

    assert settings.scoring.weights.research == 0.10
