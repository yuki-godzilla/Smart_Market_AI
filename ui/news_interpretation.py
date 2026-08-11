from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import cast

import streamlit as st
from pydantic import ValidationError

from backend.core.config import get_settings
from backend.interpretation import (
    NEWS_INTERPRETATION_CACHE_FILENAME,
    NewsInterpretationContext,
    NewsInterpretationPoint,
    NewsInterpretationResult,
    build_deterministic_news_interpretation,
    build_news_interpretation_context,
    build_news_interpretation_from_settings,
)
from backend.news import NewsDashboardSnapshot, RadarCandidateMap
from ui.content.news_interpretation_texts import (
    NEWS_INTERPRETATION_DISABLED_NOTE,
    NEWS_INTERPRETATION_GENERATE_LABEL,
    NEWS_INTERPRETATION_INTRO,
    NEWS_INTERPRETATION_LOADING,
    NEWS_INTERPRETATION_PENDING_NOTE,
    NEWS_INTERPRETATION_REGENERATE_LABEL,
    NEWS_INTERPRETATION_TITLE,
)
from ui.styles import render_section_heading
from ui.user_data import profile_data_path

OpenSymbolCallback = Callable[[str], None]
_OWNER_KEY = "investment_news_interpretation_owner"
_RESULT_KEY = "investment_news_interpretation_result"
_CACHE_HIT_KEY = "investment_news_interpretation_cache_hit"

_DIRECTION_LABELS = {
    "tailwind_candidate": "事業・業績への追い風候補",
    "headwind_candidate": "事業・業績への逆風候補",
    "mixed": "プラス・マイナスの両面あり",
    "unclear": "影響方向は未確認",
    "not_applicable": "個別影響の対象外",
}
_HORIZON_LABELS = {
    "current_event": "発生中・現在確認",
    "next_confirmation_cycle": "次の決算・政策・開示で確認",
    "multi_quarter": "数四半期で確認",
    "structural": "中長期の構造要因",
    "unclear": "時間軸は未確認",
}


def render_news_interpretation_panel(
    snapshot: NewsDashboardSnapshot,
    candidate_map: RadarCandidateMap,
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
    config = settings.llm_interpretation.news
    context = build_news_interpretation_context(
        snapshot,
        candidate_map,
        max_material_groups=config.max_material_groups,
        max_evidence_per_group=config.max_evidence_per_group,
        max_sector_groups=config.max_sector_groups,
        max_handoff_candidates=config.max_handoff_candidates,
        max_text_chars=config.max_context_text_chars,
    )
    owner = news_interpretation_state_owner(user_id=user_id, context_hash=context.context_hash)
    clear_stale_news_interpretation_state(state, owner=owner)
    render_section_heading(NEWS_INTERPRETATION_TITLE)
    st.caption(NEWS_INTERPRETATION_INTRO)
    result = _stored_result(state, context=context)
    if not config.enabled or config.execution_mode == "off":
        st.caption(NEWS_INTERPRETATION_DISABLED_NOTE)
        result = build_deterministic_news_interpretation(
            context, status="disabled", fallback_reason="disabled"
        )
    else:
        st.caption(NEWS_INTERPRETATION_PENDING_NOTE)
        label = (
            NEWS_INTERPRETATION_REGENERATE_LABEL
            if result is not None
            else NEWS_INTERPRETATION_GENERATE_LABEL
        )
        if st.button(
            label, key=f"investment_news_interpretation_generate_{context.context_hash[:12]}"
        ):
            with st.spinner(NEWS_INTERPRETATION_LOADING):
                service_result = build_news_interpretation_from_settings(
                    context,
                    user_id=user_id,
                    cache_file=profile_data_path(
                        f"cache/{NEWS_INTERPRETATION_CACHE_FILENAME}", user_id=user_id
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


def news_interpretation_state_owner(*, user_id: str, context_hash: str) -> str:
    return f"{user_id.strip() or 'default'}|{context_hash}"


def clear_stale_news_interpretation_state(
    state: MutableMapping[str, object], *, owner: str
) -> None:
    if state.get(_OWNER_KEY) in {None, owner}:
        return
    for key in (_OWNER_KEY, _RESULT_KEY, _CACHE_HIT_KEY):
        state.pop(key, None)


def _stored_result(
    state: MutableMapping[str, object], *, context: NewsInterpretationContext
) -> NewsInterpretationResult | None:
    raw = state.get(_RESULT_KEY)
    if raw is None:
        return None
    try:
        result = NewsInterpretationResult.model_validate(raw)
    except ValidationError:
        state.pop(_RESULT_KEY, None)
        return None
    if result.context_hash != context.context_hash:
        state.pop(_RESULT_KEY, None)
        return None
    return result


def _render_result(
    result: NewsInterpretationResult,
    *,
    context: NewsInterpretationContext,
    candidate_map: RadarCandidateMap,
    cache_hit: bool,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    status = {
        "live": "live生成",
        "fallback": "簡易ガイド",
        "disabled": "簡易ガイド",
        "validation_error": "検証NG・簡易ガイド",
    }[result.status]
    if cache_hit and result.status == "live":
        status += "（cache）"
    st.caption(f"状態: {status} / 株価予測・候補順・各Scoreの変更なし")
    st.markdown(result.summary.summary)
    labels = {section.section_id: section.title for section in context.bundle.sections}
    if result.material_notes:
        st.markdown("#### 今日の主要材料")
        for note in result.material_notes:
            with st.container(border=True):
                st.markdown(f"**{labels.get(note.material_id, note.material_id)}**")
                st.caption(
                    f"{_DIRECTION_LABELS[note.business_impact_direction]} / {_HORIZON_LABELS[note.impact_horizon]}"
                )
                st.markdown(note.reading.summary)
                if note.uncertainty is not None:
                    st.caption(f"不確実性: {note.uncertainty.summary}")
    _render_sector_notes(result, context=context)
    _render_points("背景・ノイズ・鮮度", result.noise_notes)
    _render_points("未確認事項", result.unknowns)
    _render_handoffs(result, candidate_map=candidate_map, open_symbol_callback=open_symbol_callback)
    _render_points("次に確認すること", result.next_checks)
    for warning in result.warnings:
        st.warning(warning)
    with st.expander("AI読み解きの実行情報", expanded=False):
        st.caption(f"status: {result.status} / fallback: {result.fallback_reason or 'none'}")
        st.caption(
            f"provider: {result.provider or 'unknown'} / model: {result.model or 'unknown'} / profile: {result.gateway_profile or 'unknown'}"
        )
        st.caption(
            f"schema: {result.schema_version} / prompt: {result.prompt_version} / cache_hit: {str(cache_hit).lower()}"
        )
        st.caption(
            f"context: {context.context_hash[:16]} / snapshot_as_of: {context.as_of.isoformat()}"
        )


def _render_sector_notes(
    result: NewsInterpretationResult, *, context: NewsInterpretationContext
) -> None:
    if not result.sector_notes:
        return
    labels = {
        row["sector_id"]: row["sector_label"]
        for section in context.bundle.sections
        if section.section_id == "news_sector_relations"
        for row in section.rows
    }
    st.markdown("#### 関連セクターの確認候補")
    for note in result.sector_notes:
        st.markdown(f"- **{labels.get(note.sector_id, note.sector_id)}**: {note.reading.summary}")


def _render_points(title: str, points: list[NewsInterpretationPoint]) -> None:
    if not points:
        return
    st.markdown(f"#### {title}")
    for point in points:
        st.markdown(f"- {point.summary}")


def _render_handoffs(
    result: NewsInterpretationResult,
    *,
    candidate_map: RadarCandidateMap,
    open_symbol_callback: OpenSymbolCallback,
) -> None:
    if not result.handoff_hints:
        return
    by_id = {item.candidate_id: item for item in candidate_map.candidates}
    st.markdown("#### 投資コックピットで確認")
    for hint in result.handoff_hints:
        candidate = by_id.get(hint.candidate_id)
        if candidate is None or candidate.provenance == "macro_proxy":
            continue
        with st.container(border=True):
            st.markdown(f"**{candidate.display_name or candidate.symbol}（{candidate.symbol}）**")
            st.caption(hint.reason.summary)
            st.button(
                "銘柄コックピットで確認",
                key=f"news_interpretation_open_{_safe_key(hint.candidate_id)}",
                on_click=open_symbol_callback,
                args=(candidate.symbol,),
            )
            st.caption("画面遷移だけを行い、価格取得・ニュース更新・RAG検索は開始しません。")


def _safe_key(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value)[:80]
