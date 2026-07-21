from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date

from ui.cockpit_application import (
    CockpitDisplayModel,
    CockpitPresentationContext,
    CockpitPreviewRequest,
    CockpitPreviewSessionKeys,
    adopt_cockpit_preview,
    build_cockpit_display_model,
    load_cockpit_preview,
)


@dataclass
class StubPreview:
    status: str
    forecast_horizon_days: int


@dataclass
class StubDisplayPreview(StubPreview):
    bars: list[object]
    investment_score_rows: list[dict[str, str]]


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


def test_build_cockpit_display_model_preserves_one_common_horizon():
    preview = StubDisplayPreview(
        status="OK",
        forecast_horizon_days=21,
        bars=["bar"],
        investment_score_rows=[{"total_score": "70"}],
    )
    calls: list[tuple[object, ...]] = []

    def advanced_rows(current: object, horizon_days: int) -> list[dict[str, str]]:
        calls.append(("advanced", current, horizon_days))
        return [{"horizon_days": str(horizon_days)}]

    def advanced_consensus(
        current: object,
        rows: list[dict[str, str]],
        horizon_days: int,
    ) -> list[dict[str, str]]:
        calls.append(("advanced_consensus", current, rows, horizon_days))
        return [{"horizon_days": str(horizon_days), "model_count": "1"}]

    def chart_rows(
        bars: list[object],
        horizon_days: int,
        rows: list[dict[str, str]],
        consensus: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        calls.append(("chart", bars, horizon_days, rows, consensus))
        return [{"close": "100"}]

    def consensus_rows(bars: list[object], horizon_days: int) -> list[dict[str, str]]:
        calls.append(("consensus", bars, horizon_days))
        return [{"ensemble_forecast_close": "101"}]

    def metric_rows(bars: list[object], horizon_days: int) -> list[dict[str, str]]:
        calls.append(("metrics", bars, horizon_days))
        return [{"rmse": "2"}]

    model = build_cockpit_display_model(
        preview,
        forecast_horizon_days=10,
        advanced_rows_for_preview=advanced_rows,
        advanced_consensus_for_preview=advanced_consensus,
        chart_rows_for_bars=chart_rows,
        consensus_rows_for_bars=consensus_rows,
        metric_rows_for_bars=metric_rows,
        score_display_rows_for_preview=lambda rows: [{"総合スコア": rows[0]["total_score"]}],
    )

    assert model.forecast_horizon_days == 10
    assert model.advanced_forecast_rows == [{"horizon_days": "10"}]
    assert model.advanced_forecast_consensus_rows == [{"horizon_days": "10", "model_count": "1"}]
    assert model.forecast_rows == [{"close": "100"}]
    assert model.consensus_rows == [{"ensemble_forecast_close": "101"}]
    assert model.metric_rows == [{"rmse": "2"}]
    assert model.score_display_rows == [{"総合スコア": "70"}]
    assert [call[0] for call in calls] == [
        "advanced",
        "advanced_consensus",
        "chart",
        "consensus",
        "metrics",
    ]


def test_cockpit_presentation_context_keeps_one_display_model_for_renderers():
    display = CockpitDisplayModel(
        forecast_horizon_days=10,
        advanced_forecast_rows=[],
        advanced_forecast_consensus_rows=[],
        forecast_rows=[{"close": "100"}],
        consensus_rows=[{"ensemble_forecast_close": "101"}],
        metric_rows=[{"rmse": "2"}],
        score_display_rows=[{"総合スコア": "70"}],
    )

    presentation = CockpitPresentationContext(symbol_label="7203.T - Toyota", display=display)

    assert presentation.symbol_label == "7203.T - Toyota"
    assert presentation.display is display
