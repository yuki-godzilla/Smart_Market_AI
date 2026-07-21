from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

from ui.cockpit_application import (
    CockpitPreviewRequest,
    CockpitPreviewSessionKeys,
    adopt_cockpit_preview,
    load_cockpit_preview,
)


@dataclass
class StubPreview:
    status: str
    forecast_horizon_days: int


def test_load_cockpit_preview_passes_typed_request_to_builder():
    received: dict[str, object] = {}

    async def build_preview(
        symbol: str,
        start: date,
        end: date,
        provider: str,
        forecast_horizon_days: int | None,
    ) -> StubPreview:
        received.update(
            symbol=symbol,
            start=start,
            end=end,
            provider=provider,
            forecast_horizon_days=forecast_horizon_days,
        )
        return StubPreview(status="OK", forecast_horizon_days=21)

    request = CockpitPreviewRequest(
        symbol="7203.T",
        start=date(2026, 1, 1),
        end=date(2026, 6, 30),
        provider="yahoo",
    )

    preview = asyncio.run(load_cockpit_preview(request, build_preview=build_preview))

    assert preview == StubPreview(status="OK", forecast_horizon_days=21)
    assert received == {
        "symbol": "7203.T",
        "start": date(2026, 1, 1),
        "end": date(2026, 6, 30),
        "provider": "yahoo",
        "forecast_horizon_days": None,
    }


def test_adopt_cockpit_preview_updates_owned_state_only():
    preview = StubPreview(status="OK", forecast_horizon_days=21)
    session_state: dict[str, object] = {
        "unrelated": "keep",
        "chart_currency": "USD",
    }
    keys = CockpitPreviewSessionKeys(
        preview="preview",
        status="status",
        forecast_days="forecast_days",
        chart_display_currency="chart_currency",
    )

    adopt_cockpit_preview(session_state, preview=preview, keys=keys)

    assert session_state == {
        "unrelated": "keep",
        "preview": preview,
        "status": "OK",
        "forecast_days": 21,
    }
