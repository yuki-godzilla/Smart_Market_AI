from backend.marketdata.live_provider_adapters import live_provider_adapter_details


def test_live_provider_adapter_details_describe_yahoo_adapter_boundary():
    assert live_provider_adapter_details("yahoo") == {
        "adapter_registered": True,
        "adapter_module": "backend.marketdata.providers.yahoo",
        "optional_dependency": "yfinance",
        "smoke_check_status": "not_implemented",
    }


def test_live_provider_adapter_details_describe_polygon_adapter_boundary():
    assert live_provider_adapter_details("polygon") == {
        "adapter_registered": True,
        "adapter_module": "backend.marketdata.providers.polygon",
        "optional_dependency": "polygon-api-client",
        "smoke_check_status": "not_implemented",
    }


def test_live_provider_adapter_details_report_unknown_provider():
    assert live_provider_adapter_details("unknown") == {
        "adapter_registered": False,
    }
