from pydantic import ValidationError

from backend.core.config import Settings, get_settings


def test_settings_defaults_are_local_and_mock_first():
    settings = get_settings()

    assert settings.app.base_currency == "JPY"
    assert settings.dataaccess.provider == "mock"
    assert settings.dataaccess.cache.backend == "memory"
    assert settings.portfolio.solver.backend == "none"


def test_settings_reject_unknown_keys():
    try:
        Settings(unknown=True)
    except ValidationError as exc:
        assert exc.errors()[0]["type"] == "extra_forbidden"
    else:
        raise AssertionError("Settings should reject unknown keys")
