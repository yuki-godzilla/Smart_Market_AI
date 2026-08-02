from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest

from backend.core.errors import AppError
from backend.reporting import build_decision_report_context, build_report_section
from backend.research import ExternalResearchFetchResult
from ui.cockpit_application import (
    CockpitDisplayModel,
    CockpitForecastHeroContext,
    CockpitPresentationContext,
    CockpitPreviewRequest,
    CockpitPreviewSessionKeys,
    adopt_cockpit_preview,
    build_cockpit_decision_report_render_context,
    build_cockpit_display_model,
    build_cockpit_forecast_hero_context,
    build_cockpit_research_context,
    build_cockpit_summary_context,
    clear_cockpit_preview,
    cockpit_preview_state_from_session,
    load_cockpit_preview,
    run_cockpit_research_refresh,
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

    state = adopt_cockpit_preview(session_state, preview=preview, keys=keys)

    assert session_state == {
        "unrelated": "keep",
        "preview": preview,
        "status": "OK",
        "forecast_days": 21,
    }
    assert state.preview is preview
    assert state.status == "OK"
    assert state.forecast_horizon_days == 21


def test_preview_state_uses_preview_as_the_source_of_truth_for_duplicate_fields():
    preview = StubPreview(status="OK", forecast_horizon_days=21)
    keys = CockpitPreviewSessionKeys(
        preview="preview",
        status="status",
        forecast_days="forecast_days",
        chart_display_currency="chart_currency",
    )
    session_state: dict[str, object] = {
        "preview": preview,
        "status": "ERROR",
        "forecast_days": 5,
    }

    state = cockpit_preview_state_from_session(
        session_state,
        keys=keys,
        preview_from_value=lambda value: value if isinstance(value, StubPreview) else None,
    )

    assert state.preview is preview
    assert state.status == "OK"
    assert state.forecast_horizon_days == 21


def test_clear_preview_removes_all_preview_owned_fields_only():
    keys = CockpitPreviewSessionKeys(
        preview="preview",
        status="status",
        forecast_days="forecast_days",
        chart_display_currency="chart_currency",
    )
    session_state: dict[str, object] = {
        "preview": StubPreview(status="OK", forecast_horizon_days=21),
        "status": "OK",
        "forecast_days": 21,
        "chart_currency": "USD",
        "unrelated": "keep",
    }

    clear_cockpit_preview(session_state, keys=keys)

    assert session_state == {"unrelated": "keep"}


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


def test_cockpit_summary_context_keeps_header_inputs_together():
    score_row = {"総合スコア": "70"}
    metadata = {"market": "jp"}

    context = build_cockpit_summary_context(
        symbol="7203.T",
        name="Toyota",
        provider="yahoo",
        as_of="2026-08-02",
        reference_period_days=120,
        forecast_horizon_days=21,
        score_row=score_row,
        symbol_metadata=metadata,
    )

    assert context.symbol == "7203.T"
    assert context.name == "Toyota"
    assert context.provider == "yahoo"
    assert context.reference_period_days == 120
    assert context.forecast_horizon_days == 21
    score_row["総合スコア"] = "0"
    metadata["market"] = "us"
    assert context.score_row == {"総合スコア": "70"}
    assert context.symbol_metadata == {"market": "jp"}


def test_cockpit_forecast_hero_context_keeps_existing_display_and_normalizes_messages():
    presentation = CockpitPresentationContext(
        symbol_label="AAPL - Apple Inc.",
        display=CockpitDisplayModel(
            forecast_horizon_days=21,
            advanced_forecast_rows=[],
            advanced_forecast_consensus_rows=[],
            forecast_rows=[],
            consensus_rows=[],
            metric_rows=[],
            score_display_rows=[],
        ),
    )

    context = build_cockpit_forecast_hero_context(
        presentation=presentation,
        horizon_summary=" 取得済み価格120点 ",
        horizon_warnings=["coverage warning", 7],
    )

    assert isinstance(context, CockpitForecastHeroContext)
    assert context.presentation is presentation
    assert context.horizon_summary == "取得済み価格120点"
    assert context.horizon_warnings == ("coverage warning", "7")


def test_cockpit_research_and_report_contexts_preserve_one_resolved_snapshot():
    research = build_cockpit_research_context(
        symbol="7203.T",
        as_of=date(2026, 8, 2),
        report=None,
        news_report=None,
        external_research_result=None,
    )
    decision_report = build_decision_report_context(
        title="確認レポート - 7203.T",
        sections=[
            build_report_section(
                title="データ取得状況と信頼性",
                source_kind="cockpit",
                symbol="7203.T",
                summary={"provider": "yahoo"},
            )
        ],
    )
    overview = {"symbol": "7203.T", "total_score": "70"}
    evidence_rows = [{"根拠": "価格トレンド", "読み取り": "横ばい"}]
    score_row = {"総合スコア": "70"}
    symbol_row = {"market": "jp"}

    context = build_cockpit_decision_report_render_context(
        decision_report=decision_report,
        overview=overview,
        summary_lines=["7203.Tは確認対象です。"],
        evidence_rows=evidence_rows,
        score_row=score_row,
        symbol_row=symbol_row,
        research=research,
    )
    overview["total_score"] = "0"
    evidence_rows[0]["読み取り"] = "変更後"
    score_row["総合スコア"] = "0"
    symbol_row["market"] = "us"

    assert context.research is research
    assert context.research.as_of == date(2026, 8, 2)
    assert context.decision_report is decision_report
    assert context.overview == {"symbol": "7203.T", "total_score": "70"}
    assert context.summary_lines == ("7203.Tは確認対象です。",)
    assert context.evidence_rows == ({"根拠": "価格トレンド", "読み取り": "横ばい"},)
    assert context.score_row == {"総合スコア": "70"}
    assert context.symbol_row == {"market": "jp"}


def test_run_cockpit_research_refresh_preserves_order_and_publishes_each_result():
    external_result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="fixture",
        fetched_at=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
        entries=[],
        retention_policy="session",
    )
    progress: list[tuple[str, float]] = []
    events: list[str] = []
    times = iter([100.0, 101.0, 103.0, 104.0, 107.0, 108.0, 113.0, 114.0])

    result = run_cockpit_research_refresh(
        fetch_external_research=lambda: events.append("fetch") or external_result,
        publish_external_research_result=lambda value: events.append(f"external:{value.symbol}"),
        build_research_report=lambda: events.append("report") or None,
        build_stock_news_report=lambda: events.append("news") or None,
        publish_research_report=lambda value: events.append(f"publish_report:{value}"),
        publish_stock_news_report=lambda value: events.append(f"publish_news:{value}"),
        report_progress=lambda message, ratio: progress.append((message, ratio)),
        monotonic_time=lambda: next(times),
    )

    assert events == [
        "fetch",
        "external:7203.T",
        "report",
        "publish_report:None",
        "news",
        "publish_news:None",
    ]
    assert progress == [
        ("外部参照ソースとニュースを取得しています。", 0.24),
        ("外部参照ソースをAI調査に反映しています。", 0.52),
        ("企業リサーチレポートを生成しています。", 0.70),
        ("ニュースと開示材料を整理しています。", 0.86),
    ]
    assert result.external_research_result is external_result
    assert result.external_fetch_error is None
    assert result.trace_rows == (
        ("外部取得", 2.0),
        ("企業レポート生成", 3.0),
        ("ニュース整理", 5.0),
        ("合計", 14.0),
    )


def test_run_cockpit_research_refresh_continues_after_external_fetch_error():
    progress: list[tuple[str, float]] = []
    published: list[str] = []
    times = iter([10.0, 11.0, 13.0, 15.0, 16.0, 20.0, 22.0])

    result = run_cockpit_research_refresh(
        fetch_external_research=lambda: (_ for _ in ()).throw(AppError("external unavailable")),
        publish_external_research_result=lambda _value: published.append("external"),
        build_research_report=lambda: published.append("report") or None,
        build_stock_news_report=lambda: published.append("news") or None,
        publish_research_report=lambda _value: published.append("publish_report"),
        publish_stock_news_report=lambda _value: published.append("publish_news"),
        report_progress=lambda message, ratio: progress.append((message, ratio)),
        monotonic_time=lambda: next(times),
    )

    assert result.external_research_result is None
    assert result.external_fetch_error is not None
    assert result.external_fetch_error.message == "external unavailable"
    assert published == ["report", "publish_report", "news", "publish_news"]
    assert [message for message, _ratio in progress] == [
        "外部参照ソースとニュースを取得しています。",
        "保存済み資料と既存データで調査を続行しています。",
        "企業リサーチレポートを生成しています。",
        "ニュースと開示材料を整理しています。",
    ]
    assert result.trace_rows == (("企業レポート生成", 2.0), ("ニュース整理", 4.0), ("合計", 12.0))


def test_run_cockpit_research_refresh_publishes_external_result_before_report_failure():
    external_result = ExternalResearchFetchResult(
        symbol="7203.T",
        provider="fixture",
        fetched_at=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
        entries=[],
        retention_policy="session",
    )
    events: list[str] = []
    times = iter([10.0, 11.0, 12.0, 13.0])

    with pytest.raises(RuntimeError, match="report build failed"):
        run_cockpit_research_refresh(
            fetch_external_research=lambda: events.append("fetch") or external_result,
            publish_external_research_result=lambda value: events.append(
                f"external:{value.symbol}"
            ),
            build_research_report=lambda: (_ for _ in ()).throw(
                RuntimeError("report build failed")
            ),
            build_stock_news_report=lambda: events.append("news") or None,
            publish_research_report=lambda _value: events.append("publish_report"),
            publish_stock_news_report=lambda _value: events.append("publish_news"),
            report_progress=lambda _message, _ratio: None,
            monotonic_time=lambda: next(times),
        )

    assert events == ["fetch", "external:7203.T"]
