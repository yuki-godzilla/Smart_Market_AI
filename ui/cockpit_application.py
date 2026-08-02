"""Streamlit-independent adapters for the Cockpit preview flow."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Generic, Mapping, Protocol, Sequence, TypeVar

from backend.core.errors import AppError
from backend.reporting import DecisionReportContext
from backend.research import (
    CompanyResearchReport,
    ExternalResearchFetchResult,
    StockNewsReport,
)


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


@dataclass(frozen=True)
class CockpitSummaryContext:
    """Stable inputs for the Cockpit header summary."""

    symbol: str
    name: str
    provider: str
    as_of: str
    reference_period_days: int
    forecast_horizon_days: int
    score_row: dict[str, str] | None
    symbol_metadata: dict[str, str] | None


@dataclass(frozen=True)
class CockpitForecastHeroContext:
    """Context-frozen inputs for the Cockpit price and Forecast hero header."""

    presentation: CockpitPresentationContext
    horizon_summary: str
    horizon_warnings: tuple[str, ...]


@dataclass(frozen=True)
class CockpitResearchContext:
    """One symbol-scoped snapshot of the Research inputs used by Cockpit sections."""

    symbol: str
    as_of: date
    report: CompanyResearchReport | None
    news_report: StockNewsReport | None
    external_research_result: ExternalResearchFetchResult | None


@dataclass(frozen=True)
class CockpitDecisionReportRenderContext:
    """Prepared Decision Report inputs shared by Cockpit renderers and assistant context."""

    decision_report: DecisionReportContext
    overview: dict[str, str]
    summary_lines: tuple[str, ...]
    evidence_rows: tuple[dict[str, str], ...]
    score_row: dict[str, str]
    symbol_row: dict[str, str] | None
    research: CockpitResearchContext


CockpitResearchExternalFetcher = Callable[[], ExternalResearchFetchResult]
CockpitResearchResultPublisher = Callable[[ExternalResearchFetchResult], None]
CockpitResearchReportBuilder = Callable[[], CompanyResearchReport | None]
CockpitStockNewsReportBuilder = Callable[[], StockNewsReport | None]
CockpitResearchReportPublisher = Callable[[CompanyResearchReport | None], None]
CockpitStockNewsReportPublisher = Callable[[StockNewsReport | None], None]
CockpitResearchProgressReporter = Callable[[str, float], None]
CockpitResearchClock = Callable[[], float]


@dataclass(frozen=True)
class CockpitResearchRefreshResult:
    """Completed refresh data and trace information for one Cockpit Research request."""

    external_research_result: ExternalResearchFetchResult | None
    external_fetch_error: AppError | None
    report: CompanyResearchReport | None
    news_report: StockNewsReport | None
    trace_rows: tuple[tuple[str, float], ...]


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


def build_cockpit_summary_context(
    *,
    symbol: str,
    name: str,
    provider: str,
    as_of: str,
    reference_period_days: int,
    forecast_horizon_days: int,
    score_row: Mapping[str, str] | None,
    symbol_metadata: Mapping[str, str] | None,
) -> CockpitSummaryContext:
    """Collect the header-summary inputs without referring to Streamlit state."""

    return CockpitSummaryContext(
        symbol=symbol,
        name=name,
        provider=provider,
        as_of=as_of,
        reference_period_days=reference_period_days,
        forecast_horizon_days=forecast_horizon_days,
        score_row=dict(score_row) if score_row is not None else None,
        symbol_metadata=dict(symbol_metadata) if symbol_metadata is not None else None,
    )


def build_cockpit_forecast_hero_context(
    *,
    presentation: CockpitPresentationContext,
    horizon_summary: str,
    horizon_warnings: Sequence[object],
) -> CockpitForecastHeroContext:
    """Freeze only the already-derived Forecast header inputs for page rendering."""

    return CockpitForecastHeroContext(
        presentation=presentation,
        horizon_summary=horizon_summary.strip(),
        horizon_warnings=tuple(str(warning) for warning in horizon_warnings),
    )


def build_cockpit_research_context(
    *,
    symbol: str,
    as_of: date,
    report: CompanyResearchReport | None,
    news_report: StockNewsReport | None,
    external_research_result: ExternalResearchFetchResult | None,
) -> CockpitResearchContext:
    """Collect the already-resolved, symbol-scoped Research inputs for one render pass."""

    return CockpitResearchContext(
        symbol=symbol,
        as_of=as_of,
        report=report,
        news_report=news_report,
        external_research_result=external_research_result,
    )


def build_cockpit_decision_report_render_context(
    *,
    decision_report: DecisionReportContext,
    overview: Mapping[str, str],
    summary_lines: Sequence[str],
    evidence_rows: Sequence[Mapping[str, str]],
    score_row: Mapping[str, str],
    symbol_row: Mapping[str, str] | None,
    research: CockpitResearchContext,
) -> CockpitDecisionReportRenderContext:
    """Freeze report presentation inputs before the Streamlit renderer consumes them."""

    return CockpitDecisionReportRenderContext(
        decision_report=decision_report,
        overview=dict(overview),
        summary_lines=tuple(summary_lines),
        evidence_rows=tuple(dict(row) for row in evidence_rows),
        score_row=dict(score_row),
        symbol_row=dict(symbol_row) if symbol_row is not None else None,
        research=research,
    )


def run_cockpit_research_refresh(
    *,
    fetch_external_research: CockpitResearchExternalFetcher,
    publish_external_research_result: CockpitResearchResultPublisher,
    build_research_report: CockpitResearchReportBuilder,
    build_stock_news_report: CockpitStockNewsReportBuilder,
    publish_research_report: CockpitResearchReportPublisher,
    publish_stock_news_report: CockpitStockNewsReportPublisher,
    report_progress: CockpitResearchProgressReporter,
    monotonic_time: CockpitResearchClock,
) -> CockpitResearchRefreshResult:
    """Run the Cockpit Research refresh without referring to Streamlit or session state.

    A successful external result is published before report generation so a later report-builder
    failure cannot discard the session-local evidence that was already obtained. External fetch
    failures retain the existing fail-open behavior: report and news generation still continue.
    """

    refresh_started = monotonic_time()
    trace_rows: list[tuple[str, float]] = []
    external_research_result: ExternalResearchFetchResult | None = None
    external_fetch_error: AppError | None = None

    try:
        report_progress("外部参照ソースとニュースを取得しています。", 0.24)
        step_started = monotonic_time()
        external_research_result = fetch_external_research()
        publish_external_research_result(external_research_result)
        trace_rows.append(("外部取得", monotonic_time() - step_started))
        report_progress("外部参照ソースをAI調査に反映しています。", 0.52)
    except AppError as exc:
        external_fetch_error = exc
        report_progress("保存済み資料と既存データで調査を続行しています。", 0.52)

    report_progress("企業リサーチレポートを生成しています。", 0.70)
    step_started = monotonic_time()
    report = build_research_report()
    publish_research_report(report)
    trace_rows.append(("企業レポート生成", monotonic_time() - step_started))

    report_progress("ニュースと開示材料を整理しています。", 0.86)
    step_started = monotonic_time()
    news_report = build_stock_news_report()
    publish_stock_news_report(news_report)
    trace_rows.append(("ニュース整理", monotonic_time() - step_started))
    trace_rows.append(("合計", monotonic_time() - refresh_started))

    return CockpitResearchRefreshResult(
        external_research_result=external_research_result,
        external_fetch_error=external_fetch_error,
        report=report,
        news_report=news_report,
        trace_rows=tuple(trace_rows),
    )
