"""Streamlit-independent adapters for the Cockpit preview flow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Generic, Protocol, TypeVar


class CockpitPreview(Protocol):
    """The preview fields owned by the Cockpit controller."""

    @property
    def status(self) -> str: ...

    @property
    def forecast_horizon_days(self) -> int: ...


class CockpitDisplayPreview(CockpitPreview, Protocol):
    """Preview fields needed to assemble the Cockpit display model."""

    @property
    def bars(self) -> list[Any]: ...

    @property
    def investment_score_rows(self) -> list[dict[str, str]]: ...


class CockpitSessionState(Protocol):
    """The limited mutable session-state surface owned by this controller."""

    def get(self, key: str, default: object = None) -> object: ...

    def __setitem__(self, key: str, value: object) -> None: ...

    def __delitem__(self, key: str) -> None: ...


PreviewT = TypeVar("PreviewT", bound=CockpitPreview)
CockpitPreviewBuilder = Callable[[str, date, date, str, int | None], Awaitable[PreviewT]]


@dataclass(frozen=True)
class CockpitPreviewRequest:
    """Validated inputs for one Cockpit market-data refresh."""

    symbol: str
    start: date
    end: date
    provider: str
    forecast_horizon_days: int | None = None


@dataclass(frozen=True)
class CockpitPreviewSessionKeys:
    """Session-state keys updated after a Cockpit preview completes."""

    preview: str
    status: str
    forecast_days: str
    chart_display_currency: str


@dataclass(frozen=True)
class CockpitPreviewState(Generic[PreviewT]):
    """The preview-derived state a Cockpit renderer may safely consume."""

    preview: PreviewT | None
    status: str
    forecast_horizon_days: int | None


@dataclass(frozen=True)
class CockpitDisplayModel:
    """Derived, deterministic rows consumed by the Cockpit renderers."""

    forecast_horizon_days: int
    advanced_forecast_rows: list[dict[str, str]]
    advanced_forecast_consensus_rows: list[dict[str, str]]
    forecast_rows: list[dict[str, str]]
    consensus_rows: list[dict[str, str]]
    metric_rows: list[dict[str, str]]
    score_display_rows: list[dict[str, str]]


@dataclass(frozen=True)
class CockpitPresentationContext:
    """Stable display inputs shared by the Cockpit hero and detail presenters."""

    symbol_label: str
    display: CockpitDisplayModel


async def load_cockpit_preview(
    request: CockpitPreviewRequest,
    *,
    build_preview: CockpitPreviewBuilder[PreviewT],
) -> PreviewT:
    """Build a preview with the request contract used by the Cockpit page."""

    return await build_preview(
        request.symbol,
        request.start,
        request.end,
        request.provider,
        request.forecast_horizon_days,
    )


def adopt_cockpit_preview(
    session_state: CockpitSessionState,
    *,
    preview: CockpitPreview,
    keys: CockpitPreviewSessionKeys,
) -> CockpitPreviewState[CockpitPreview]:
    """Persist preview-owned state and invalidate a previous chart currency."""

    session_state[keys.preview] = preview
    session_state[keys.status] = preview.status
    session_state[keys.forecast_days] = preview.forecast_horizon_days
    try:
        del session_state[keys.chart_display_currency]
    except KeyError:
        pass
    return CockpitPreviewState(
        preview=preview,
        status=preview.status,
        forecast_horizon_days=preview.forecast_horizon_days,
    )


def cockpit_preview_state_from_session(
    session_state: CockpitSessionState,
    *,
    keys: CockpitPreviewSessionKeys,
    preview_from_value: Callable[[object], PreviewT | None],
) -> CockpitPreviewState[PreviewT]:
    """Read one coherent preview state without trusting stale duplicate fields."""

    preview = preview_from_value(session_state.get(keys.preview))
    if preview is not None:
        return CockpitPreviewState(
            preview=preview,
            status=preview.status,
            forecast_horizon_days=preview.forecast_horizon_days,
        )
    status = session_state.get(keys.status)
    return CockpitPreviewState(
        preview=None,
        status=status if isinstance(status, str) else "not_started",
        forecast_horizon_days=None,
    )


def clear_cockpit_preview(
    session_state: CockpitSessionState,
    *,
    keys: CockpitPreviewSessionKeys,
) -> None:
    """Clear all preview-owned fields before a Cockpit navigation handoff."""

    for key in (
        keys.preview,
        keys.status,
        keys.forecast_days,
        keys.chart_display_currency,
    ):
        try:
            del session_state[key]
        except KeyError:
            pass


def build_cockpit_display_model(
    preview: CockpitDisplayPreview,
    *,
    forecast_horizon_days: int,
    advanced_rows_for_preview: Callable[[Any, int], list[dict[str, str]]],
    advanced_consensus_for_preview: Callable[
        [Any, list[dict[str, str]], int], list[dict[str, str]]
    ],
    chart_rows_for_bars: Callable[
        [Any, int, list[dict[str, str]], list[dict[str, str]]], list[dict[str, str]]
    ],
    consensus_rows_for_bars: Callable[[Any, int], list[dict[str, str]]],
    metric_rows_for_bars: Callable[[Any, int], list[dict[str, str]]],
    score_display_rows_for_preview: Callable[[list[dict[str, str]]], list[dict[str, str]]],
) -> CockpitDisplayModel:
    """Assemble render inputs while leaving Forecast implementation at the UI edge."""

    advanced_forecast_rows = advanced_rows_for_preview(preview, forecast_horizon_days)
    advanced_forecast_consensus_rows = advanced_consensus_for_preview(
        preview,
        advanced_forecast_rows,
        forecast_horizon_days,
    )
    return CockpitDisplayModel(
        forecast_horizon_days=forecast_horizon_days,
        advanced_forecast_rows=advanced_forecast_rows,
        advanced_forecast_consensus_rows=advanced_forecast_consensus_rows,
        forecast_rows=chart_rows_for_bars(
            preview.bars,
            forecast_horizon_days,
            advanced_forecast_rows,
            advanced_forecast_consensus_rows,
        ),
        consensus_rows=consensus_rows_for_bars(preview.bars, forecast_horizon_days),
        metric_rows=metric_rows_for_bars(preview.bars, forecast_horizon_days),
        score_display_rows=score_display_rows_for_preview(preview.investment_score_rows),
    )
