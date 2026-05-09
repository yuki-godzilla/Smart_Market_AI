from fastapi.testclient import TestClient

from backend.app import main
from backend.app.main import app
from backend.core.errors import (
    ComputationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    RateLimitError,
    SchemaMismatchError,
)

client = TestClient(app)


def test_pre_trade_check_api_blocks_default_single_symbol_basket():
    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "qty": "10",
                    "price_hint": "175",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCK"
    assert body["breaches"] == [
        "R5:min_dividend_yield:AAPL",
        "R3:max_concentration",
    ]
    assert body["evaluated_rules_version"] == "risk-mvp-v1"
    assert len(body["decision_id"]) == 16


def test_pre_trade_check_api_rejects_empty_basket():
    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [],
        },
    )

    assert response.status_code == 422


def test_pre_trade_check_api_returns_data_source_error_body_for_unknown_symbol():
    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "UNKNOWN",
                    "side": "BUY",
                    "qty": "10",
                    "price_hint": "100",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "code": "APP-2000",
        "message": "Unsupported mock symbol",
        "details": {"symbol": "UNKNOWN"},
    }


def test_pre_trade_check_api_returns_live_provider_opt_in_error(monkeypatch):
    monkeypatch.setenv(
        "SMAI_CONFIG_FILE",
        "tests/fixtures/config/live_provider_no_opt_in.yaml",
    )

    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "qty": "10",
                    "price_hint": "175",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "code": "APP-2000",
        "message": "Live market-data provider requires explicit opt-in",
        "details": {
            "provider": "yahoo",
            "registered": True,
            "implemented": False,
            "deterministic": False,
            "requires_external_opt_in": True,
            "adapter_registered": True,
            "adapter_protocol": "MarketDataProviderAdapter",
            "adapter_module": "backend.marketdata.providers.yahoo",
            "optional_dependency": "yfinance",
            "smoke_check_status": "implemented_live_opt_in",
            "supported_providers": ["mock", "csv"],
            "planned_live_providers": ["yahoo", "polygon"],
            "allow_external_providers": False,
            "opt_in_status": "explicit_config_required",
        },
    }


def test_pre_trade_check_api_returns_live_provider_not_implemented_error(monkeypatch):
    monkeypatch.setenv(
        "SMAI_CONFIG_FILE",
        "tests/fixtures/config/live_provider_opt_in.yaml",
    )

    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "qty": "10",
                    "price_hint": "175",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "code": "APP-2000",
        "message": "Live market-data providers are not implemented yet",
        "details": {
            "provider": "polygon",
            "registered": True,
            "implemented": False,
            "deterministic": False,
            "requires_external_opt_in": True,
            "adapter_registered": True,
            "adapter_protocol": "MarketDataProviderAdapter",
            "adapter_module": "backend.marketdata.providers.polygon",
            "optional_dependency": "polygon-api-client",
            "smoke_check_status": "not_implemented",
            "supported_providers": ["mock", "csv"],
            "planned_live_providers": ["yahoo", "polygon"],
            "allow_external_providers": True,
            "opt_in_status": "explicitly_enabled_not_implemented",
        },
    }


def test_pre_trade_check_api_returns_computation_error_body(monkeypatch):
    class BrokenRiskService:
        async def pre_trade_check(self, basket, as_of, account_id):
            raise ComputationError(
                "Trade intent requires price_hint or snapshot.last",
                details={"symbol": basket[0].symbol, "account_id": account_id},
            )

    monkeypatch.setattr(main, "create_risk_service", BrokenRiskService)

    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "qty": "10",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "APP-2002",
        "message": "Trade intent requires price_hint or snapshot.last",
        "details": {"symbol": "AAPL", "account_id": "acct-1"},
    }


def test_pre_trade_check_api_returns_rate_limit_error_body(monkeypatch):
    class BrokenRiskService:
        async def pre_trade_check(self, basket, as_of, account_id):
            raise RateLimitError(
                "provider rate limit",
                details={"provider": "yahoo", "retry_after_seconds": 60},
            )

    monkeypatch.setattr(main, "create_risk_service", BrokenRiskService)

    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "qty": "10",
                    "price_hint": "175",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 429
    assert response.json() == {
        "code": "APP-2001",
        "message": "provider rate limit",
        "details": {"provider": "yahoo", "retry_after_seconds": 60},
    }


def test_pre_trade_check_api_returns_schema_mismatch_error_body(monkeypatch):
    class BrokenRiskService:
        async def pre_trade_check(self, basket, as_of, account_id):
            raise SchemaMismatchError(
                "provider payload schema mismatch",
                details={"provider": "polygon", "field": "close"},
            )

    monkeypatch.setattr(main, "create_risk_service", BrokenRiskService)

    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "qty": "10",
                    "price_hint": "175",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "APP-5001",
        "message": "provider payload schema mismatch",
        "details": {"provider": "polygon", "field": "close"},
    }


def test_pre_trade_check_api_returns_provider_unavailable_error_body(monkeypatch):
    class BrokenRiskService:
        async def pre_trade_check(self, basket, as_of, account_id):
            raise ProviderUnavailableError(
                "provider unavailable",
                details={"provider": "yahoo"},
            )

    monkeypatch.setattr(main, "create_risk_service", BrokenRiskService)

    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "qty": "10",
                    "price_hint": "175",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "code": "APP-2003",
        "message": "provider unavailable",
        "details": {"provider": "yahoo"},
    }


def test_pre_trade_check_api_returns_provider_timeout_error_body(monkeypatch):
    class BrokenRiskService:
        async def pre_trade_check(self, basket, as_of, account_id):
            raise ProviderTimeoutError(
                "provider timed out",
                details={"provider": "polygon", "timeout_ms": 5000},
            )

    monkeypatch.setattr(main, "create_risk_service", BrokenRiskService)

    response = client.post(
        "/risk/pre-trade-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "basket": [
                {
                    "symbol": "AAPL",
                    "side": "BUY",
                    "qty": "10",
                    "price_hint": "175",
                    "currency": "USD",
                }
            ],
        },
    )

    assert response.status_code == 504
    assert response.json() == {
        "code": "APP-2004",
        "message": "provider timed out",
        "details": {"provider": "polygon", "timeout_ms": 5000},
    }
