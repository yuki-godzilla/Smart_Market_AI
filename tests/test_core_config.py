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


def test_settings_loads_yaml_overrides(monkeypatch):
    monkeypatch.setenv("SMAI_CONFIG_FILE", f"{FIXTURE_DIR}/local.yaml")

    settings = get_settings()

    assert settings.dataaccess.provider == "mock"
    assert settings.risk.thresholds.max_concentration == 0.3
    assert settings.risk.thresholds.min_dividend_yield == 0.02
    assert settings.portfolio.solver.backend == "none"
    assert settings.portfolio.solver.tolerance == 0.0001


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
