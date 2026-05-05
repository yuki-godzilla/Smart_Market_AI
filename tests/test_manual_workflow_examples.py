import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_portfolio_rebalance_check_example_runs_against_api():
    request_body = json.loads(Path("examples/portfolio_rebalance_check.json").read_text())

    response = client.post("/portfolio/rebalance-check", json=request_body)

    assert response.status_code == 200
    body = response.json()
    assert body["proposal"]["trades"][0]["symbol"] == "AAPL"
    assert body["proposal"]["trades"][0]["side"] == "BUY"
    assert body["risk_decision"]["status"] == "BLOCK"
