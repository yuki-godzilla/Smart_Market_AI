from backend.marketdata.provider_registry import (
    IMPLEMENTED_LIVE_PROVIDERS,
    PLANNED_LIVE_PROVIDERS,
    SUPPORTED_PROVIDERS,
    provider_capability_details,
)


def test_provider_registry_identifies_deterministic_supported_providers():
    assert SUPPORTED_PROVIDERS == ("mock", "csv")
    assert provider_capability_details("csv") == {
        "provider": "csv",
        "registered": True,
        "implemented": True,
        "deterministic": True,
        "requires_external_opt_in": False,
        "supported_providers": ["mock", "csv"],
        "implemented_live_providers": ["yahoo"],
        "planned_live_providers": ["polygon"],
    }


def test_provider_registry_identifies_live_provider_groups():
    assert IMPLEMENTED_LIVE_PROVIDERS == ("yahoo",)
    assert PLANNED_LIVE_PROVIDERS == ("polygon",)
    assert provider_capability_details("yahoo") == {
        "provider": "yahoo",
        "registered": True,
        "implemented": True,
        "deterministic": False,
        "requires_external_opt_in": True,
        "supported_providers": ["mock", "csv"],
        "implemented_live_providers": ["yahoo"],
        "planned_live_providers": ["polygon"],
    }


def test_provider_registry_reports_unknown_provider():
    assert provider_capability_details("unknown") == {
        "provider": "unknown",
        "registered": False,
        "supported_providers": ["mock", "csv"],
        "implemented_live_providers": ["yahoo"],
        "planned_live_providers": ["polygon"],
    }
