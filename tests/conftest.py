import pytest

from backend.core.config import CONFIG_FILE_ENV


@pytest.fixture(autouse=True)
def _use_mock_market_data_config_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep normal test runs deterministic while product defaults stay live-first."""

    monkeypatch.setenv(CONFIG_FILE_ENV, "tests/fixtures/config/local.yaml")
