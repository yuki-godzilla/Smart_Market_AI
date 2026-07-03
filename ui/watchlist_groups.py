from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Callable, Mapping

import streamlit as st
from pydantic import ValidationError

from backend.watchlist_groups import (
    WATCHLIST_GROUP_TONES,
    WatchlistGroupsRepository,
    WatchlistGroupsService,
    WatchlistGroupsState,
    assign_default_tone,
    build_grouped_watchlist,
)
from ui.user_data import (
    current_user_id,
    is_default_session_user,
    session_payload,
    set_session_payload,
)

VIEW_MODE_KEY = "watchlist_groups_view_mode"
EDIT_MODE_KEY = "watchlist_groups_edit_mode"
DELETE_PENDING_KEY = "watchlist_groups_delete_pending"
UNCLASSIFIED_VALUE = "__unclassified__"
TONE_LABELS = {
    "cyan": "シアン",
    "blue": "ブルー",
    "purple": "パープル",
    "green": "グリーン",
    "amber": "アンバー",
    "orange": "オレンジ",
    "rose": "ローズ",
    "slate": "スレート",
}


class _CurrentUserRepository:
    def __init__(self) -> None:
        self._persistent = WatchlistGroupsRepository()

    def load(self, user_id: str) -> WatchlistGroupsState:
        if is_default_session_user():
            payload = session_payload("watchlist_groups", None)
            if payload is None:
                return WatchlistGroupsRepository.empty_state()
            try:
                return WatchlistGroupsState.model_validate(payload)
            except (ValidationError, ValueError, TypeError):
                return WatchlistGroupsRepository.empty_state()
        return self._persistent.load(user_id)

    def save(self, user_id: str, state: WatchlistGroupsState) -> None:
        if is_default_session_user():
            set_session_payload("watchlist_groups", state.model_dump(mode="json"))
            return
        self._persistent.save(user_id, state)


def current_watchlist_groups_service() -> tuple[WatchlistGroupsService, str]:
    return WatchlistGroupsService(_CurrentUserRepository()), current_user_id() or "default"


def render_watchlist_group_toolbar() -> tuple[str, bool, WatchlistGroupsState]:
    service, user_id = current_watchlist_groups_service()
    state = service.list_groups(user_id)
    st.markdown(
        '<div class="smai-watchlist-groups-toolbar">'
        "<strong>ウォッチリストグループ</strong>"
        "<span>お気に入り銘柄を、テーマ・市場・検討状況ごとに整理できます。</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    create_col, edit_col, mode_col = st.columns([1.25, 1.1, 1.2])
    with create_col:
        st.markdown('<span class="smai-watchlist-action-primary"></span>', unsafe_allow_html=True)
        if st.button(
            "＋ グループを作成",
            key="watchlist_groups_create",
            use_container_width=True,
        ):
            render_group_create_dialog(service, user_id, state)
    with edit_col:
        editing = bool(st.session_state.get(EDIT_MODE_KEY, False))
        marker = "secondary" if editing else "edit"
        st.markdown(
            f'<span class="smai-watchlist-action-{marker}"></span>',
            unsafe_allow_html=True,
        )
        if st.button(
            "編集を終了" if editing else "配置を編集",
            key="watchlist_groups_toggle_edit",
            use_container_width=True,
        ):
            st.session_state[EDIT_MODE_KEY] = not editing
            st.rerun()
    with mode_col:
        view_mode = st.selectbox(
            "表示",
            ["グループ別", "すべて"],
            key=VIEW_MODE_KEY,
        )
    if st.session_state.get(DELETE_PENDING_KEY):
        render_group_delete_confirm(service, user_id, state)
    return view_mode, bool(st.session_state.get(EDIT_MODE_KEY, False)), state


@st.dialog("グループを作成")
def render_group_create_dialog(
    service: WatchlistGroupsService,
    user_id: str,
    state: WatchlistGroupsState,
) -> None:
    default_tone = assign_default_tone(state)
    with st.form("watchlist_group_create_form"):
        name = st.text_input("グループ名", max_chars=32)
        description = st.text_area("説明（任意）", max_chars=200, height=80)
        tone = st.selectbox(
            "トーン",
            list(WATCHLIST_GROUP_TONES),
            index=list(WATCHLIST_GROUP_TONES).index(default_tone),
            format_func=lambda value: TONE_LABELS[value],
        )
        st.markdown(
            group_preview_html(name or "新しいグループ", description, tone), unsafe_allow_html=True
        )
        create_col, cancel_col = st.columns(2)
        create = create_col.form_submit_button(
            "作成する",
            type="primary",
            use_container_width=True,
        )
        cancel = cancel_col.form_submit_button("キャンセル", use_container_width=True)
    if cancel:
        st.rerun()
    if not create:
        return
    try:
        service.create_group(user_id, name, description, tone)
    except (ValueError, RuntimeError) as exc:
        st.error(str(exc))
        return
    st.toast("グループを作成しました。")
    st.rerun()


@st.dialog("グループ編集")
def render_group_edit_dialog(
    service: WatchlistGroupsService,
    user_id: str,
    group_id: str,
) -> None:
    state = service.list_groups(user_id)
    group = next((item for item in state.groups if item.group_id == group_id), None)
    if group is None:
        st.error("グループが見つかりません。")
        return
    with st.form(f"watchlist_group_edit_form_{group_id}"):
        name = st.text_input("グループ名", value=group.name, max_chars=32)
        description = st.text_area(
            "説明（任意）",
            value=group.description or "",
            max_chars=200,
            height=80,
        )
        tone = st.selectbox(
            "トーン",
            list(WATCHLIST_GROUP_TONES),
            index=list(WATCHLIST_GROUP_TONES).index(group.tone),
            format_func=lambda value: TONE_LABELS[value],
        )
        st.markdown(group_preview_html(name, description, tone), unsafe_allow_html=True)
        save_col, cancel_col = st.columns(2)
        save = save_col.form_submit_button(
            "保存する",
            type="primary",
            use_container_width=True,
        )
        cancel = cancel_col.form_submit_button("キャンセル", use_container_width=True)
    order_up, order_down = st.columns(2)
    if order_up.button("↑ 上へ", key=f"watchlist_group_up_{group_id}", use_container_width=True):
        service.move_group(user_id, group_id, -1)
        st.rerun()
    if order_down.button(
        "↓ 下へ",
        key=f"watchlist_group_down_{group_id}",
        use_container_width=True,
    ):
        service.move_group(user_id, group_id, 1)
        st.rerun()
    st.markdown('<span class="smai-watchlist-action-danger"></span>', unsafe_allow_html=True)
    if st.button(
        "削除する",
        key=f"watchlist_group_delete_request_{group_id}",
        use_container_width=True,
    ):
        st.session_state[DELETE_PENDING_KEY] = group_id
        st.rerun()
    if cancel:
        st.rerun()
    if not save:
        return
    try:
        service.update_group(
            user_id,
            group_id,
            name=name,
            description=description,
            tone=tone,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    st.toast("グループを更新しました。")
    st.rerun()


@st.dialog("グループを削除")
def render_group_delete_confirm(
    service: WatchlistGroupsService,
    user_id: str,
    state: WatchlistGroupsState,
) -> None:
    group_id = str(st.session_state.get(DELETE_PENDING_KEY) or "")
    group = next((item for item in state.groups if item.group_id == group_id), None)
    if group is None:
        st.session_state.pop(DELETE_PENDING_KEY, None)
        st.warning("対象のグループは既にありません。")
        return
    count = sum(1 for placement in state.placements.values() if placement.group_id == group_id)
    st.warning(
        f"「{group.name}」を削除します。中の銘柄 {count}件はお気に入りから削除されず、"
        "「未分類」に移動します。"
    )
    delete_col, cancel_col = st.columns(2)
    with delete_col:
        st.markdown('<span class="smai-watchlist-action-danger"></span>', unsafe_allow_html=True)
        delete = st.button(
            "削除する",
            key=f"watchlist_group_delete_confirm_{group_id}",
            use_container_width=True,
        )
    cancel = cancel_col.button(
        "キャンセル",
        key=f"watchlist_group_delete_cancel_{group_id}",
        use_container_width=True,
    )
    if cancel:
        st.session_state.pop(DELETE_PENDING_KEY, None)
        st.rerun()
    if delete:
        service.delete_group(user_id, group_id)
        st.session_state.pop(DELETE_PENDING_KEY, None)
        st.toast("グループを削除しました。銘柄は未分類に移動しました。")
        st.rerun()


def render_grouped_watchlist(
    rows: list[Mapping[str, str]],
    state: WatchlistGroupsState,
    *,
    editing: bool,
    on_open: Callable[[str], None],
    on_remove: Callable[[str], None],
) -> None:
    service, user_id = current_watchlist_groups_service()
    sections = build_grouped_watchlist(rows, state)
    group_options = [(UNCLASSIFIED_VALUE, "未分類")] + [
        (group.group_id, group.name) for group in sorted(state.groups, key=lambda item: item.order)
    ]
    option_values = [value for value, _ in group_options]
    option_labels = dict(group_options)
    if editing:
        st.markdown(
            '<div class="smai-watchlist-edit-mode-banner"><strong>配置編集モード中です</strong>'
            "<span>銘柄カードの移動先を選択して保存してください。</span></div>",
            unsafe_allow_html=True,
        )
    for section in sections:
        st.markdown(
            group_section_header_html(
                section.name,
                section.description,
                section.tone,
                len(section.items),
                section.is_system,
            ),
            unsafe_allow_html=True,
        )
        if not section.is_system:
            st.markdown('<span class="smai-watchlist-action-edit"></span>', unsafe_allow_html=True)
            if st.button(
                "グループ編集",
                key=f"watchlist_group_edit_{section.group_id}",
            ):
                render_group_edit_dialog(service, user_id, str(section.group_id))
        if not section.items:
            message = (
                "すべての銘柄がグループに配置されています。"
                if section.is_system
                else "まだ銘柄はありません。配置を編集して銘柄を移動できます。"
            )
            st.caption(message)
            continue
        for start in range(0, len(section.items), 3):
            columns = st.columns(3)
            for column, row in zip(columns, section.items[start : start + 3]):
                symbol = str(row.get("symbol") or "")
                with column:
                    st.markdown(compact_watchlist_card_html(row), unsafe_allow_html=True)
                    if editing:
                        current = state.placements.get(symbol)
                        selected_value = current.group_id if current else UNCLASSIFIED_VALUE
                        selected = st.selectbox(
                            "移動先",
                            option_values,
                            index=option_values.index(selected_value),
                            format_func=lambda value: option_labels[value],
                            key=f"watchlist_group_move_{user_id}_{symbol}",
                        )
                        st.markdown(
                            '<span class="smai-watchlist-action-save"></span>',
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "移動を保存",
                            key=f"watchlist_group_move_save_{user_id}_{symbol}",
                            use_container_width=True,
                        ):
                            service.move_symbol(
                                user_id,
                                symbol,
                                None if selected == UNCLASSIFIED_VALUE else selected,
                            )
                            st.toast("配置を更新しました。")
                            st.rerun()
                    else:
                        open_col, remove_col = st.columns([1.35, 0.85])
                        if open_col.button(
                            "現在確認",
                            key=f"watchlist_group_open_{symbol}",
                            use_container_width=True,
                        ):
                            on_open(symbol)
                        if remove_col.button(
                            "☆ 解除",
                            key=f"watchlist_group_remove_{symbol}",
                            use_container_width=True,
                        ):
                            on_remove(symbol)


def group_section_header_html(
    name: str,
    description: str | None,
    tone: str,
    count: int,
    is_system: bool,
) -> str:
    safe_tone = tone if tone in WATCHLIST_GROUP_TONES else "slate"
    description_text = description or (
        "まだグループに配置していないお気に入り銘柄です。" if is_system else ""
    )
    return (
        f'<section class="smai-watchlist-group-section '
        f'smai-watchlist-group-section--tone-{safe_tone}">'
        '<div class="smai-watchlist-group-header">'
        f"<strong>{html.escape(name)}</strong>"
        f'<span class="smai-watchlist-group-count-badge">{count}件</span>'
        "</div>"
        f"<p>{html.escape(description_text)}</p>"
        "</section>"
    )


def compact_watchlist_card_html(row: Mapping[str, str]) -> str:
    name = html.escape(str(row.get("name") or row.get("symbol") or "未取得"))
    symbol = html.escape(str(row.get("symbol") or "未取得"))
    metrics = [
        ("AI総合", row.get("ai_score")),
        ("上昇気配", row.get("upside")),
        ("下振れ警戒", row.get("downside")),
    ]
    metric_html = "".join(
        f"<span>{label} <strong>{html.escape(str(value))}</strong></span>"
        for label, value in metrics
        if value and str(value) != "未取得"
    )
    if not metric_html:
        metric_html = "<span>評価データは未取得です</span>"
    return (
        '<article class="smai-watchlist-compact-card">'
        f'<h4>{name}</h4><div class="smai-watchlist-compact-symbol">{symbol}</div>'
        f'<div class="smai-watchlist-compact-metrics">{metric_html}</div>'
        "</article>"
    )


def group_preview_html(name: str, description: str, tone: str) -> str:
    return group_section_header_html(name, description or None, tone, 0, False)


def clear_watchlist_group_transient_state() -> None:
    for key in tuple(st.session_state):
        if str(key).startswith("watchlist_group_") or key in {
            EDIT_MODE_KEY,
            DELETE_PENDING_KEY,
        }:
            st.session_state.pop(key, None)


def empty_watchlist_groups_state() -> WatchlistGroupsState:
    return WatchlistGroupsState(updated_at=datetime.now(UTC))
