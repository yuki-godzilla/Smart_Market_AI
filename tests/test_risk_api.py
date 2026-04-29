from fastapi.testclient import TestClient

from backend.app.main import app

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
