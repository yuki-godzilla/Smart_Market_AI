from fastapi.testclient import TestClient

from backend.app import main
from backend.app.main import app
from backend.core.errors import ComputationError

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
