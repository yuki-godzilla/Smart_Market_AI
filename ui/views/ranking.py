from __future__ import annotations

from collections.abc import MutableMapping
from typing import cast

import streamlit as st
from pydantic import ValidationError

from backend.core.config import get_settings
from backend.interpretation import (
    RankingInterpretationContext,
    RankingInterpretationPoint,
    RankingInterpretationResult,
    build_deterministic_ranking_interpretation,
    build_ranking_interpretation_from_settings,
)
from ui.content.ranking_interpretation_texts import (
    RANKING_INTERPRETATION_DISABLED_NOTE,
    RANKING_INTERPRETATION_GENERATE_LABEL,
    RANKING_INTERPRETATION_INTRO,
    RANKING_INTERPRETATION_LOADING,
    RANKING_INTERPRETATION_PENDING_NOTE,
    RANKING_INTERPRETATION_REGENERATE_LABEL,
    RANKING_INTERPRETATION_TITLE,
)
from ui.styles import (
    badge_html,
    metric_progress_from_value,
    render_metric_card,
    render_section_heading,
)

_OWNER_KEY = "ranking_interpretation_owner"
_RESULT_KEY = "ranking_interpretation_result"
_CACHE_HIT_KEY = "ranking_interpretation_cache_hit"


def render_ranking_summary_cards(cards: list[dict[str, str]]) -> None:
    if not cards:
        return
    columns = st.columns(3)
    for index, card in enumerate(cards):
        with columns[index % len(columns)]:
            badge = _metric_badge_for_card(card)
            render_metric_card(
                card["label"],
                card["value"],
                caption=card.get("help", ""),
                badges=(badge,) if badge else (),
                tone=_metric_card_tone(card),
                progress=_metric_card_progress(card),
            )


def render_ranking_interpretation_panel(
    context: RankingInterpretationContext,
    *,
    user_id: str,
    session_state: MutableMapping[str, object] | None = None,
) -> None:
    state = (
        session_state
        if session_state is not None
        else cast(MutableMapping[str, object], st.session_state)
    )
    owner = ranking_interpretation_state_owner(user_id=user_id, context_hash=context.context_hash)
    _clear_stale_interpretation_state(state, owner=owner)
    settings = get_settings()
    config = settings.llm_interpretation.ranking

    render_section_heading(RANKING_INTERPRETATION_TITLE)
    st.caption(RANKING_INTERPRETATION_INTRO)
    result = _stored_result(state, context=context)
    if not config.enabled or config.execution_mode == "off":
        st.caption(RANKING_INTERPRETATION_DISABLED_NOTE)
        result = build_deterministic_ranking_interpretation(
            context,
            status="disabled",
            fallback_reason="disabled",
        )
    else:
        st.caption(RANKING_INTERPRETATION_PENDING_NOTE)
        label = (
            RANKING_INTERPRETATION_REGENERATE_LABEL
            if result is not None
            else RANKING_INTERPRETATION_GENERATE_LABEL
        )
        if st.button(label, key=f"ranking_interpretation_generate_{context.context_hash[:12]}"):
            with st.spinner(RANKING_INTERPRETATION_LOADING):
                service_result = build_ranking_interpretation_from_settings(
                    context,
                    settings=settings,
                )
            result = service_result.result
            state[_OWNER_KEY] = owner
            state[_RESULT_KEY] = result.model_dump(mode="json")
            state[_CACHE_HIT_KEY] = service_result.cache.cache_hit
    if result is not None:
        _render_interpretation_result(
            result,
            context=context,
            cache_hit=bool(state.get(_CACHE_HIT_KEY, False)),
        )


def ranking_interpretation_state_owner(*, user_id: str, context_hash: str) -> str:
    return f"{user_id.strip() or 'default'}|{context_hash}"


def _clear_stale_interpretation_state(state: MutableMapping[str, object], *, owner: str) -> None:
    if state.get(_OWNER_KEY) in {None, owner}:
        return
    for key in (_OWNER_KEY, _RESULT_KEY, _CACHE_HIT_KEY):
        state.pop(key, None)


def _stored_result(
    state: MutableMapping[str, object], *, context: RankingInterpretationContext
) -> RankingInterpretationResult | None:
    raw = state.get(_RESULT_KEY)
    if raw is None:
        return None
    try:
        result = RankingInterpretationResult.model_validate(raw)
    except ValidationError:
        state.pop(_RESULT_KEY, None)
        return None
    if result.context_hash != context.context_hash:
        state.pop(_RESULT_KEY, None)
        return None
    return result


def _render_interpretation_result(
    result: RankingInterpretationResult,
    *,
    context: RankingInterpretationContext,
    cache_hit: bool,
) -> None:
    status_label = {
        "live": "live生成",
        "fallback": "簡易ガイド",
        "disabled": "簡易ガイド",
        "validation_error": "検証NG・簡易ガイド",
    }[result.status]
    if cache_hit and result.status == "live":
        status_label += "（cache）"
    st.caption(f"状態: {status_label} / 順位・スコア・Forecastの変更なし")
    st.markdown(result.overall_reading)
    _render_points("共通する強み", result.common_strengths)
    _render_points("共通する注意点", result.common_cautions)
    _render_points("効いている指標", result.metric_notes)
    _render_points("セクターの見方", result.sector_notes)
    if result.status != "disabled":
        _render_candidate_notes(result, context=context)
    _render_points("次の確認事項", result.next_checks)
    for warning in result.warnings:
        st.warning(warning)
    _render_runtime_details(result, cache_hit=cache_hit)


def _render_points(title: str, points: list[RankingInterpretationPoint]) -> None:
    if not points:
        return
    st.markdown(f"#### {title}")
    for point in points:
        st.markdown(f"- {point.summary}")


def _render_candidate_notes(
    result: RankingInterpretationResult,
    *,
    context: RankingInterpretationContext,
) -> None:
    if not result.candidate_notes:
        return
    labels = {
        section.section_id: section.title
        for section in context.bundle.sections
        if section.source_kind == "ranking_candidate"
    }
    st.markdown("#### 上位候補ごとの読み方")
    for note in result.candidate_notes:
        with st.expander(labels.get(note.candidate_id, note.candidate_id), expanded=False):
            st.markdown(note.reading.summary)
            if note.caution is not None:
                st.markdown(f"注意: {note.caution.summary}")
            st.markdown(f"次に確認: {note.next_check.summary}")


def _render_runtime_details(result: RankingInterpretationResult, *, cache_hit: bool) -> None:
    with st.expander("AI解釈の実行情報", expanded=False):
        st.caption(f"status: {result.status} / fallback: {result.fallback_reason or 'none'}")
        st.caption(
            f"provider: {result.provider or 'unknown'} / model: {result.model or 'unknown'} / "
            f"profile: {result.gateway_profile or 'unknown'}"
        )
        st.caption(
            f"schema: {result.schema_version} / prompt: {result.prompt_version} / "
            f"cache_hit: {str(cache_hit).lower()}"
        )
        if result.generated_at is not None:
            st.caption(f"generated_at: {result.generated_at.isoformat()}")


def _metric_badge_for_card(card: dict[str, str]) -> str:
    label = card.get("label", "")
    value = card.get("value", "")
    if "信頼度" in label and value not in {"0", "-", "未計算"}:
        return badge_html("データ", "success")
    if "ランキング" in label or "対象範囲" in label:
        return badge_html("条件", "info")
    return ""


def _metric_card_tone(card: dict[str, str]) -> str:
    label = card.get("label", "")
    if "スコア" in label:
        return "score"
    if "信頼度" in label:
        return "success"
    if "ランキング" in label or "対象範囲" in label:
        return "info"
    if "候補" in label or "銘柄" in label:
        return "forecast"
    return "neutral"


def _metric_card_progress(card: dict[str, str]) -> int | None:
    label = card.get("label", "")
    if "スコア" in label or "信頼度" in label:
        return metric_progress_from_value(card.get("value"))
    return None
