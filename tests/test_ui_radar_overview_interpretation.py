from contextlib import nullcontext
from datetime import UTC, date, datetime

from backend.assistant import AssistantContextBundle, AssistantContextSection
from backend.core.config import Settings
from backend.interpretation import (
    RadarOverviewInterpretationCacheMetadata,
    RadarOverviewInterpretationContext,
    RadarOverviewInterpretationServiceResult,
    build_deterministic_radar_overview_interpretation,
)
from ui import radar_overview_interpretation as overview_ui
from ui.radar_overview_interpretation import (
    clear_stale_radar_overview_interpretation_state,
    context_safe_key,
    radar_overview_interpretation_state_owner,
)


def test_radar_overview_state_owner_separates_user_and_context() -> None:
    first = radar_overview_interpretation_state_owner(user_id="yuki", context_hash="aaa")
    other_user = radar_overview_interpretation_state_owner(user_id="kei", context_hash="aaa")
    other_context = radar_overview_interpretation_state_owner(user_id="yuki", context_hash="bbb")

    assert first == "yuki|aaa"
    assert len({first, other_user, other_context}) == 3


def test_radar_overview_state_clears_result_when_owner_changes() -> None:
    state: dict[str, object] = {
        "investment_radar_overview_interpretation_owner": "yuki|old",
        "investment_radar_overview_interpretation_result": {"context_hash": "old"},
        "investment_radar_overview_interpretation_cache_hit": True,
        "unrelated": "keep",
    }

    clear_stale_radar_overview_interpretation_state(state, owner="yuki|new")

    assert state == {"unrelated": "keep"}


def test_radar_overview_button_key_is_safe_and_bounded() -> None:
    value = context_safe_key("radar:direct_mention:7203.T/" + "x" * 100)

    assert value.startswith("radar_direct_mention_7203_T_")
    assert len(value) == 80


def test_radar_overview_live_service_runs_only_after_explicit_button(monkeypatch) -> None:
    context = _context()
    fallback = build_deterministic_radar_overview_interpretation(
        context,
        status="fallback",
        fallback_reason="gateway_unavailable",
    )
    service_result = RadarOverviewInterpretationServiceResult(
        result=fallback,
        cache=RadarOverviewInterpretationCacheMetadata(
            status="miss",
            cache_key="cache-key",
        ),
    )
    calls: list[str] = []

    def build_from_settings(
        *_args: object, **_kwargs: object
    ) -> RadarOverviewInterpretationServiceResult:
        calls.append("called")
        return service_result

    monkeypatch.setattr(
        overview_ui,
        "get_settings",
        lambda: Settings.model_validate(
            {"llm_interpretation": {"radar_overview": {"enabled": True}}}
        ),
    )
    monkeypatch.setattr(
        overview_ui,
        "build_radar_overview_interpretation_context",
        lambda *_args, **_kwargs: context,
    )
    monkeypatch.setattr(
        overview_ui,
        "build_radar_overview_interpretation_from_settings",
        build_from_settings,
    )
    monkeypatch.setattr(overview_ui, "profile_data_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview_ui, "render_section_heading", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview_ui, "_render_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview_ui.st, "caption", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(overview_ui.st, "button", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(overview_ui.st, "spinner", lambda *_args, **_kwargs: nullcontext())

    state: dict[str, object] = {}
    overview_ui.render_radar_overview_interpretation_panel(
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        None,
        user_id="yuki",
        open_symbol_callback=lambda _symbol: None,
        session_state=state,
    )

    assert calls == ["called"]
    assert state["investment_radar_overview_interpretation_owner"] == (
        f"yuki|{context.context_hash}"
    )


def _context() -> RadarOverviewInterpretationContext:
    now = datetime(2026, 8, 10, tzinfo=UTC)
    bundle = AssistantContextBundle(
        bundle_id="radar-overview-test",
        title="Radar overview",
        source="streamlit_context",
        created_at=now,
        active_context_id="radar_overview_interpretation",
        sections=[
            AssistantContextSection(
                section_id="radar_scope",
                title="範囲",
                source_kind="radar_overview_scope",
                summary={"candidate_count": "0"},
            ),
            AssistantContextSection(
                section_id="radar_market_breadth",
                title="市場",
                source_kind="radar_market_breadth",
                summary={"market_state": "missing", "direction_available": "no"},
            ),
            AssistantContextSection(
                section_id="radar_sector_comparison",
                title="セクター",
                source_kind="radar_sector_comparison",
            ),
        ],
    )
    return RadarOverviewInterpretationContext(
        radar_context_id="radar-overview:test",
        as_of=date(2026, 8, 10),
        bundle=bundle,
        context_hash="context-hash",
        market_state="missing",
        allowed_evidence_ids=[
            "radar_scope",
            "radar_market_breadth",
            "radar_sector_comparison",
        ],
        allowed_numeric_values=["0"],
        allowed_dates=["2026-08-10"],
    )
