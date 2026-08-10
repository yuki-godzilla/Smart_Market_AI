from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import cast

import streamlit as st
from pydantic import ValidationError

from backend.core.config import get_settings
from backend.interpretation import (
    RADAR_OVERVIEW_INTERPRETATION_CACHE_FILENAME,
    RadarOverviewInterpretationContext,
    RadarOverviewInterpretationPoint,
    RadarOverviewInterpretationResult,
    build_deterministic_radar_overview_interpretation,
    build_radar_overview_interpretation_context,
    build_radar_overview_interpretation_from_settings,
)
from backend.news import NewsDashboardSnapshot, RadarCandidateMap
from backend.news.radar_market import RadarMarketSnapshot
from ui.content.radar_overview_interpretation_texts import (
    RADAR_OVERVIEW_INTERPRETATION_DISABLED_NOTE,
    RADAR_OVERVIEW_INTERPRETATION_GENERATE_LABEL,
    RADAR_OVERVIEW_INTERPRETATION_INTRO,
    RADAR_OVERVIEW_INTERPRETATION_LOADING,
    RADAR_OVERVIEW_INTERPRETATION_PENDING_NOTE,
    RADAR_OVERVIEW_INTERPRETATION_REGENERATE_LABEL,
    RADAR_OVERVIEW_INTERPRETATION_TITLE,
)
from ui.styles import render_section_heading
from ui.user_data import profile_data_path

OpenSymbolCallback = Callable[[str], None]

_OWNER_KEY = "investment_radar_overview_interpretation_owner"
_RESULT_KEY = "investment_radar_overview_interpretation_result"
_CACHE_HIT_KEY = "investment_radar_overview_interpretation_cache_hit"


def render_radar_overview_interpretation_panel(
    news_snapshot: NewsDashboardSnapshot,
    candidate_map: RadarCandidateMap,
    market_snapshot: RadarMarketSnapshot | None,
    *,
    user_id: str,
    open_symbol_callback: OpenSymbolCallback,
    session_state: MutableMapping[str, object] | None = None,
) -> None:
    state = (
        session_state
        if session_state is not None
        else cast(MutableMapping[str, object], st.session_state)
    )
    settings = get_settings()
    config = settings.llm_interpretation.radar_overview
    context = build_radar_overview_interpretation_context(
        news_snapshot,
        candidate_map,
        market_snapshot,
        max_themes=config.max_themes,
        max_sector_groups=config.max_sector_groups,
        max_deep_dive_candidates=config.max_deep_dive_candidates,
        max_text_chars=config.max_context_text_chars,
    )
    owner = radar_overview_interpretation_state_owner(
        user_id=user_id,
        context_hash=context.context_hash,
    )
    _clear_stale_state(state, owner=owner)

    render_section_heading(RADAR_OVERVIEW_INTERPRETATION_TITLE)
    st.caption(RADAR_OVERVIEW_INTERPRETATION_INTRO)
    result = _stored_result(state, context=context)
    if not config.enabled or config.execution_mode == "off":
        st.caption(RADAR_OVERVIEW_INTERPRETATION_DISABLED_NOTE)
        result = build_deterministic_radar_overview_interpretation(
            context,
            status="disabled",
            fallback_reason="disabled",
        )
    else:
        st.caption(RADAR_OVERVIEW_INTERPRETATION_PENDING_NOTE)
        label = (
            RADAR_OVERVIEW_INTERPRETATION_REGENERATE_LABEL
            if result is not None
            else RADAR_OVERVIEW_INTERPRETATION_GENERATE_LABEL
        )
        if st.button(
            label,
            key=f"investment_radar_overview_generate_{context.context_hash[:12]}",
        ):
            with st.spinner(RADAR_OVERVIEW_INTERPRETATION_LOADING):
                service_result = build_radar_overview_interpretation_from_settings(
                    context,
                    user_id=user_id,
                    cache_file=profile_data_path(
                        f"cache/{RADAR_OVERVIEW_INTERPRETATION_CACHE_FILENAME}",
                        user_id=user_id,
                    ),
                    settings=settings,
                )
            result = service_result.result
            state[_OWNER_KEY] = owner
            state[_RESULT_KEY] = result.model_dump(mode="json")
            state[_CACHE_HIT_KEY] = service_result.cache.cache_hit
    if result is not None:
        _render_result(
            result,
            context=context,
            candidate_map=candidate_map,
            cache_hit=bool(state.get(_CACHE_HIT_KEY, False)),
            open_symbol_callback=open_symbol_callback,
        )


def radar_overview_interpretation_state_owner(*, user_id: str, context_hash: str) -> str:
    return f"{user_id.strip() or 'default'}|{context_hash}"


def clear_stale_radar_overview_interpretation_state(
    state: MutableMapping[str, object],
    *,
    owner: str,
) -> None:
    _clear_stale_state(state, owner=owner)


def _clear_stale_state(state: MutableMapping[str, object], *, owner: str) -> None:
    if state.get(_OWNER_KEY) in {None, owner}:
        return
    for key in (_OWNER_KEY, _RESULT_KEY, _CACHE_HIT_KEY):
        state.pop(key, None)


def _stored_result(
    state: MutableMapping[str, object],
    *,
    context: RadarOverviewInterpretationContext,
) -> RadarOverviewInterpretationResult | None:
    raw = state.get(_RESULT_KEY)
    if raw is None:
        return None
    try:
        result = RadarOverviewInterpretationResult.model_validate(raw)
    except ValidationError:
        state.pop(_RESULT_KEY, None)
        return None
    if result.context_hash != context.context_hash:
        state.pop(_RESULT_KEY, None)
        return None
    return result


def _render_result(
    result: RadarOverviewInterpretationResult,
    *,
    context: RadarOverviewInterpretationContext,
    candidate_map: RadarCandidateMap,
    cache_hit: bool,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    status_label = {
        "live": "live生成",
        "fallback": "簡易ガイド",
        "disabled": "簡易ガイド",
        "validation_error": "検証NG・簡易ガイド",
    }[result.status]
    if cache_hit and result.status == "live":
        status_label += "（cache）"
    st.caption(f"状態: {status_label} / 候補順・価格・スコア・Forecastの変更なし")
    st.markdown(result.summary.summary)
    if result.candidate_set_movement is not None:
        _render_points("取得済み候補の値動き", [result.candidate_set_movement])
    _render_sector_notes(result, context=context)
    _render_theme_notes(result, context=context)
    _render_deep_dive_hints(
        result,
        candidate_map=candidate_map,
        open_symbol_callback=open_symbol_callback,
    )
    _render_points("不明点", result.unknowns)
    _render_points("次に確認すること", result.next_checks)
    for warning in result.warnings:
        st.warning(warning)
    _render_runtime_details(result, context=context, cache_hit=cache_hit)


def _render_points(title: str, points: list[RadarOverviewInterpretationPoint]) -> None:
    if not points:
        return
    st.markdown(f"#### {title}")
    for point in points:
        st.markdown(f"- {point.summary}")


def _render_sector_notes(
    result: RadarOverviewInterpretationResult,
    *,
    context: RadarOverviewInterpretationContext,
) -> None:
    if not result.sector_notes:
        return
    labels = {
        row.get("sector_id", ""): row.get("sector_label", row.get("sector_id", ""))
        for section in context.bundle.sections
        if section.section_id == "radar_sector_comparison"
        for row in section.rows
    }
    st.markdown("#### セクター別の確認ポイント")
    for note in result.sector_notes:
        st.markdown(f"- **{labels.get(note.sector_id, note.sector_id)}**: {note.reading.summary}")


def _render_theme_notes(
    result: RadarOverviewInterpretationResult,
    *,
    context: RadarOverviewInterpretationContext,
) -> None:
    if not result.theme_notes:
        return
    labels = {
        section.section_id: section.title
        for section in context.bundle.sections
        if section.source_kind == "radar_news_theme"
    }
    st.markdown("#### ニューステーマと関連候補")
    for note in result.theme_notes:
        st.markdown(f"- **{labels.get(note.theme_id, note.theme_id)}**: {note.reading.summary}")


def _render_deep_dive_hints(
    result: RadarOverviewInterpretationResult,
    *,
    candidate_map: RadarCandidateMap,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    if not result.deep_dive_hints:
        return
    by_id = {item.candidate_id: item for item in candidate_map.candidates}
    st.markdown("#### 次に詳しく確認する候補")
    for hint in result.deep_dive_hints:
        candidate = by_id.get(hint.candidate_id)
        if candidate is None or candidate.provenance == "macro_proxy":
            continue
        label = candidate.display_name or candidate.symbol
        with st.container(border=True):
            st.markdown(f"**{label}（{candidate.symbol}）**")
            st.caption(hint.reason.summary)
            st.button(
                "銘柄コックピットで確認",
                key=f"radar_overview_open_{context_safe_key(hint.candidate_id)}",
                on_click=open_symbol_callback,
                args=(candidate.symbol,),
            )
            st.caption("画面遷移だけを行い、価格取得・ニュース更新・RAG検索は開始しません。")


def context_safe_key(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)[:80]


def _render_runtime_details(
    result: RadarOverviewInterpretationResult,
    *,
    context: RadarOverviewInterpretationContext,
    cache_hit: bool,
) -> None:
    with st.expander("AI読み解きの実行情報", expanded=False):
        st.caption(f"status: {result.status} / fallback: {result.fallback_reason or 'none'}")
        st.caption(
            f"provider: {result.provider or 'unknown'} / model: {result.model or 'unknown'} / "
            f"profile: {result.gateway_profile or 'unknown'}"
        )
        st.caption(
            f"schema: {result.schema_version} / prompt: {result.prompt_version} / "
            f"cache_hit: {str(cache_hit).lower()}"
        )
        st.caption(f"context: {context.context_hash[:16]} / market_state: {context.market_state}")
        if result.generated_at is not None:
            st.caption(f"generated_at: {result.generated_at.isoformat()}")
