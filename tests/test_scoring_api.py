from decimal import Decimal

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_investment_score_api_returns_breakdown_and_warnings():
    response = client.post(
        "/scoring/investment-score",
        json={
            "symbols": ["AAPL", "7203.T"],
            "as_of": "2026-04-09",
            "horizon_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["rank"] == 1
    assert payload[0]["symbol"] in {"AAPL", "7203.T"}
    assert payload[0]["total_score"] is not None
    assert payload[0]["decision_support_note"] == (
        "Decision-support score only; not a buy/sell recommendation."
    )
    assert [component["component"] for component in payload[0]["breakdown"]] == [
        "screening",
        "forecast_agreement",
        "data_quality",
        "risk_signal",
    ]
    assert payload[0]["forecast_agreement"] in {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
    assert "risk_signal:available" in payload[0]["reasons"]
    assert any(reason.startswith("data_quality:") for reason in payload[0]["reasons"])


def test_investment_score_api_rejects_empty_symbols():
    response = client.post(
        "/scoring/investment-score",
        json={
            "symbols": [],
            "as_of": "2026-04-09",
        },
    )

    assert response.status_code == 422


def test_investment_score_api_accepts_optional_research_scores_without_default_reweight():
    response = client.post(
        "/scoring/investment-score",
        json={
            "symbols": ["AAPL"],
            "as_of": "2026-04-09",
            "horizon_days": 1,
            "research_scores_by_symbol": {"AAPL": "60"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert Decimal(str(payload[0]["research_score"])) == Decimal("60")
    assert [component["component"] for component in payload[0]["breakdown"]] == [
        "screening",
        "forecast_agreement",
        "data_quality",
        "risk_signal",
    ]
