from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_forecast_evaluate_api_returns_available_baselines():
    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-04-07",
            "end": "2026-04-09",
            "horizon_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [row["model_name"] for row in payload] == ["naive", "moving_average_3"]
    assert payload[0]["symbol"] == "AAPL"
    assert payload[0]["latest_forecast"]["forecast_close"] == "175.0000"
    assert payload[0]["metrics"]["sample_count"] == 2
    assert payload[1]["metrics"]["sample_count"] == 0


def test_forecast_evaluate_api_rejects_reversed_date_range():
    response = client.post(
        "/forecast/evaluate",
        json={
            "symbol": "AAPL",
            "start": "2026-04-10",
            "end": "2026-04-09",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "APP-2002"
    assert response.json()["message"] == "Forecast start date must be on or before end date"
