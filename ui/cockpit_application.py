"""Streamlit-independent adapters for the Cockpit preview flow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import MutableMapping, Protocol, TypeVar


class CockpitPreview(Protocol):
    """The preview fields owned by the Cockpit controller."""

    status: str
    forecast_horizon_days: int


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
    session_state: MutableMapping[str, object],
    *,
    preview: CockpitPreview,
    keys: CockpitPreviewSessionKeys,
) -> None:
    """Persist preview-owned state and invalidate a previous chart currency."""

    session_state[keys.preview] = preview
    session_state[keys.status] = preview.status
    session_state[keys.forecast_days] = preview.forecast_horizon_days
    session_state.pop(keys.chart_display_currency, None)
