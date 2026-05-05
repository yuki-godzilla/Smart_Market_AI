from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUEST_PATH = PROJECT_ROOT / "examples" / "portfolio_rebalance_check.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the deterministic portfolio rebalance-check API demo."
    )
    parser.add_argument(
        "--request",
        type=Path,
        default=DEFAULT_REQUEST_PATH,
        help="Path to a rebalance-check JSON request body.",
    )
    args = parser.parse_args()

    request_body = _load_json(args.request)
    response = TestClient(app).post("/portfolio/rebalance-check", json=request_body)
    print(json.dumps(response.json(), indent=2, sort_keys=True))
    response.raise_for_status()


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Request JSON must be an object")
    return data


if __name__ == "__main__":
    main()
