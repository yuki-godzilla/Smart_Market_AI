from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_screening_score_api_ranks_symbols_with_breakdown():
    response = client.post(
        "/screening/score",
        json={
            "symbols": ["AAPL", "7203.T"],
            "as_of": "2026-04-09",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["rank"] == 1
    assert payload[0]["symbol"] in {"AAPL", "7203.T"}
    assert payload[0]["total_score"] is not None
    assert payload[0]["momentum_score"] is not None
    assert payload[0]["liquidity_score"] is not None
    assert payload[0]["risk_score"] is not None
    assert payload[0]["data_quality_score"] is not None
    assert payload[0]["data_quality"] == "WARN"
    assert payload[0]["summary"]
    assert "5日モメンタムを計算するための履歴データが足りません。" in payload[0]["reason_labels"]
    assert "missing:momentum_5d" in payload[0]["reasons"]


def test_screening_score_api_rejects_empty_symbols():
    response = client.post(
        "/screening/score",
        json={
            "symbols": [],
            "as_of": "2026-04-09",
        },
    )

    assert response.status_code == 422
