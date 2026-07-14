from pydantic import ValidationError

from backend.core.config import (
    CONFIG_FILE_ENV,
    PERFORMANCE_PROFILE_ENV,
    Settings,
    get_settings,
    resolve_performance_profile,
)

FIXTURE_DIR = "tests/fixtures/config"


def test_settings_defaults_are_external_yahoo_first(monkeypatch):
    monkeypatch.delenv(CONFIG_FILE_ENV, raising=False)

    settings = get_settings()

    assert settings.app.base_currency == "JPY"
    assert settings.network.main_application.scheme == "http"
    assert settings.network.main_application.port == 8501
    assert settings.network.tailscale_hostname is None
    assert settings.dataaccess.provider == "yahoo"
    assert settings.dataaccess.allow_external_providers is True
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
    assert settings.assistant.llm_planner.enabled is False
    assert settings.assistant.llm_planner.gateway_url == "http://127.0.0.1:8088"
    assert settings.assistant.llm_planner.endpoint_path == "/api/v1/assistant/tool-plan"
    assert settings.assistant.llm_planner.timeout_seconds == 15.0
    assert settings.assistant.llm_planner.max_steps == 5
    assert settings.assistant.llm_planner.fallback_to_deterministic is True
    assert settings.llm_factor.live.enabled is False
    assert settings.llm_factor.live.base_url == "http://127.0.0.1:8088"
    assert settings.llm_factor.live.endpoint_path == "/api/v1/llm-factor/generate"
    assert settings.llm_factor.live.prompt_version == "llm_factor_live_mvp.v1"
    assert settings.llm_factor.live.response_schema_version == "llm_factor.v1"
    assert settings.llm_factor.live.preferred_profile == "desktop_analysis"
    assert settings.llm_factor.live.cache_enabled is True
    assert settings.performance_profiles["notebook"].external_fetch.max_workers == 4
    assert settings.performance_profiles["workstation"].external_fetch.max_workers == 10
    assert settings.performance_profiles["notebook"].external_fetch.global_timeout_sec == 30.0
    assert settings.performance_profiles["workstation"].external_fetch.global_timeout_sec == 45.0
    assert settings.performance_profiles["notebook"].external_fetch.per_source_workers == {
        "yahoo_finance": 2,
        "news": 3,
        "tdnet": 2,
        "edinet": 1,
        "ir_pages": 2,
    }
    assert settings.performance_profiles["notebook"].processing.llm_workers == 1


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


def test_settings_can_load_explicit_assistant_llm_planner_opt_in():
    settings = Settings.model_validate(
        {
            "assistant": {
                "llm_planner": {
                    "enabled": True,
                    "gateway_url": "http://gateway.local",
                    "endpoint_path": "/api/v1/assistant/tool-plan",
                    "timeout_seconds": 4.5,
                    "max_steps": 4,
                    "fallback_to_deterministic": True,
                    "show_source_details": True,
                    "model": "qwen3:1.7b",
                    "execution_mode": "light",
                    "environment_profile": "notebook",
                    "preferred_profile": "assistant_fast",
                }
            }
        }
    )

    planner = settings.assistant.llm_planner
    assert planner.enabled is True
    assert planner.gateway_url == "http://gateway.local"
    assert planner.timeout_seconds == 4.5
    assert planner.max_steps == 4
    assert planner.show_source_details is True
    assert planner.model == "qwen3:1.7b"
    assert planner.execution_mode == "light"
    assert planner.preferred_profile == "assistant_fast"


def test_settings_can_load_explicit_radar_interpretation_opt_in():
    settings = Settings.model_validate(
        {
            "llm_interpretation": {
                "radar": {
                    "enabled": True,
                    "base_url": "http://127.0.0.1:8088",
                    "context_answer_path": "/api/v1/context-answer",
                    "timeout_seconds": 12.0,
                    "execution_mode": "light",
                    "environment_profile": "notebook",
                    "preferred_profile": "desktop_fast",
                    "prompt_version": "radar_interpretation_mvp.v1",
                    "schema_version": "radar_interpretation.v1",
                    "max_citations": 5,
                    "max_context_text_chars": 320,
                }
            }
        }
    )

    radar = settings.llm_interpretation.radar
    assert radar.enabled is True
    assert radar.timeout_seconds == 12.0
    assert radar.schema_version == "radar_interpretation.v1"
    assert radar.max_citations == 5


def test_settings_can_load_explicit_llm_factor_live_opt_in():
    settings = Settings.model_validate(
        {
            "llm_factor": {
                "live": {
                    "enabled": True,
                    "base_url": "http://gateway.local",
                    "endpoint_path": "/api/v1/llm-factor/generate",
                    "timeout_seconds": 12.5,
                    "model": "qwen3:14b",
                    "execution_mode": "quality",
                    "environment_profile": "desktop",
                    "preferred_profile": "desktop_analysis",
                    "prompt_version": "llm_factor_live_mvp.v1",
                    "response_schema_version": "llm_factor.v1",
                    "max_evidence_items": 6,
                    "max_context_text_chars": 320,
                    "cache_enabled": False,
                }
            }
        }
    )

    assert settings.llm_factor.live.enabled is True
    assert settings.llm_factor.live.base_url == "http://gateway.local"
    assert settings.llm_factor.live.timeout_seconds == 12.5
    assert settings.llm_factor.live.model == "qwen3:14b"
    assert settings.llm_factor.live.execution_mode == "quality"
    assert settings.llm_factor.live.environment_profile == "desktop"
    assert settings.llm_factor.live.max_evidence_items == 6
    assert settings.llm_factor.live.cache_enabled is False


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


def test_performance_profile_defaults_to_notebook(monkeypatch):
    monkeypatch.delenv(PERFORMANCE_PROFILE_ENV, raising=False)

    selection = resolve_performance_profile(Settings())

    assert selection.requested_profile == "notebook"
    assert selection.selected_profile == "notebook"
    assert selection.fallback_used is False
    assert selection.external_fetch.max_workers == 4
    assert selection.external_fetch.request_timeout_sec == 12.0
    assert selection.external_fetch.global_timeout_sec == 30.0


def test_performance_profile_can_select_notebook_from_env(monkeypatch):
    monkeypatch.setenv(PERFORMANCE_PROFILE_ENV, "notebook")

    selection = resolve_performance_profile(Settings())

    assert selection.selected_profile == "notebook"
    assert selection.external_fetch.max_workers == 4
    assert selection.external_fetch.cache_ttl_minutes == 30


def test_performance_profile_can_select_workstation_from_env(monkeypatch):
    monkeypatch.setenv(PERFORMANCE_PROFILE_ENV, "workstation")

    selection = resolve_performance_profile(Settings())

    assert selection.selected_profile == "workstation"
    assert selection.external_fetch.max_workers == 10
    assert selection.external_fetch.per_source_workers == {
        "yahoo_finance": 4,
        "news": 6,
        "tdnet": 3,
        "edinet": 2,
        "ir_pages": 4,
    }
    assert selection.external_fetch.request_timeout_sec == 15.0
    assert selection.external_fetch.global_timeout_sec == 45.0
    assert selection.external_fetch.max_symbols_per_refresh == 30
    assert selection.processing.background_refresh_workers == 6


def test_performance_profile_unknown_env_falls_back_with_warning(monkeypatch, caplog):
    monkeypatch.setenv(PERFORMANCE_PROFILE_ENV, "missing-profile")

    selection = resolve_performance_profile(Settings())

    assert selection.requested_profile == "missing-profile"
    assert selection.selected_profile == "notebook"
    assert selection.fallback_used is True
    assert selection.fallback_reason is not None
    assert "Available profiles: notebook, workstation" in selection.fallback_reason
    assert "missing-profile" in caplog.text
