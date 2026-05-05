from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_rebalance_check_api_returns_proposal_and_risk_decision():
    response = client.post(
        "/portfolio/rebalance-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "positions": [
                {
                    "symbol": "7203.T",
                    "qty": "10",
                    "avg_price": "2800",
                    "currency": "JPY",
                }
            ],
            "targets": [
                {
                    "symbol": "7203.T",
                    "currency": "JPY",
                    "target_weight": "0.5",
                },
                {
                    "symbol": "AAPL",
                    "currency": "USD",
                    "target_weight": "0.5",
                },
            ],
            "cash_jpy": "29000",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["proposal"]["account_id"] == "acct-1"
    assert body["proposal"]["solver_backend"] == "none"
    assert body["proposal"]["current"]["total_value_jpy"] == "58000"
    assert body["proposal"]["trades"] == [
        {
            "symbol": "AAPL",
            "side": "BUY",
            "qty": "1.1048",
            "price_hint": "175.00",
            "currency": "USD",
        }
    ]
    assert body["risk_decision"]["status"] == "BLOCK"
    assert body["risk_decision"]["breaches"] == [
        "R5:min_dividend_yield:AAPL",
        "R3:max_concentration",
    ]


def test_rebalance_check_api_skips_risk_when_no_trades_are_generated():
    response = client.post(
        "/portfolio/rebalance-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "positions": [
                {
                    "symbol": "7203.T",
                    "qty": "10",
                    "avg_price": "2800",
                    "currency": "JPY",
                }
            ],
            "targets": [
                {
                    "symbol": "7203.T",
                    "currency": "JPY",
                    "target_weight": "1",
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["proposal"]["trades"] == []
    assert body["risk_decision"] is None


def test_rebalance_check_api_returns_computation_error_body():
    response = client.post(
        "/portfolio/rebalance-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "targets": [
                {
                    "symbol": "7203.T",
                    "currency": "JPY",
                    "target_weight": "0.6",
                },
                {
                    "symbol": "AAPL",
                    "currency": "USD",
                    "target_weight": "0.5",
                },
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "code": "APP-2002",
        "message": "Target weights must not exceed 1",
        "details": {"target_weight_sum": "1.1"},
    }


def test_rebalance_check_api_returns_data_source_error_body_for_unknown_symbol():
    response = client.post(
        "/portfolio/rebalance-check",
        json={
            "account_id": "acct-1",
            "as_of": "2026-04-09",
            "positions": [
                {
                    "symbol": "UNKNOWN",
                    "qty": "1",
                    "avg_price": "100",
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
