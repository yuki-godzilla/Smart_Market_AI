from backend.marketdata.provider_registry import (
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
        "planned_live_providers": ["yahoo", "polygon"],
    }


def test_provider_registry_identifies_planned_live_providers():
    assert PLANNED_LIVE_PROVIDERS == ("yahoo", "polygon")
    assert provider_capability_details("yahoo") == {
        "provider": "yahoo",
        "registered": True,
        "implemented": False,
        "deterministic": False,
        "requires_external_opt_in": True,
        "supported_providers": ["mock", "csv"],
        "planned_live_providers": ["yahoo", "polygon"],
    }


def test_provider_registry_reports_unknown_provider():
    assert provider_capability_details("unknown") == {
        "provider": "unknown",
        "registered": False,
        "supported_providers": ["mock", "csv"],
    }
