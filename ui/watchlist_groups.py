from __future__ import annotations

import html
import secrets
from datetime import UTC, datetime
from typing import Callable, Mapping

import streamlit as st
from pydantic import ValidationError
from streamlit_sortables import sort_items

from backend.watchlist_groups import (
    WATCHLIST_GROUP_TONES,
    WatchlistGroup,
    WatchlistGroupsRepository,
    WatchlistGroupsService,
    WatchlistGroupsState,
    WatchlistPlacement,
    assign_default_tone,
    build_grouped_watchlist,
)
from backend.watchlist_groups.models import WatchlistGroupTone, validate_group_name
from ui.user_data import (
    current_user_id,
    is_default_session_user,
    session_payload,
    set_session_payload,
)

VIEW_MODE_KEY = "watchlist_groups_view_mode"
EDITOR_OPEN_KEY = "watchlist_groups_editor_open"
EDITOR_DRAFT_KEY = "watchlist_groups_edit_draft"
EDITOR_FOCUS_KEY = "watchlist_groups_editor_focus"
COLLAPSED_KEY = "watchlist_groups_collapsed"
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


def render_watchlist_group_toolbar() -> tuple[str, WatchlistGroupsState]:
    service, user_id = current_watchlist_groups_service()
    state = service.list_groups(user_id)
    st.markdown(
        '<div class="smai-watchlist-groups-toolbar">'
        "<strong>ウォッチリストグループ</strong>"
        "<span>通常画面は確認用です。グループ分けは専用編集画面でまとめて変更できます。</span>"
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
        st.markdown('<span class="smai-watchlist-action-edit"></span>', unsafe_allow_html=True)
        if st.button(
            "グループを編集",
            key="watchlist_groups_open_editor",
            use_container_width=True,
        ):
            open_watchlist_groups_editor(state)
            st.rerun()
    with mode_col:
        view_mode = st.selectbox("表示", ["グループ別", "すべて"], key=VIEW_MODE_KEY)
    if st.session_state.get(EDITOR_OPEN_KEY):
        render_watchlist_groups_editor(service, user_id)
    return view_mode, state


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
            group_preview_html(name or "新しいグループ", description, tone),
            unsafe_allow_html=True,
        )
        create_col, cancel_col = st.columns(2)
        create = create_col.form_submit_button("作成する", type="primary", use_container_width=True)
        cancel = cancel_col.form_submit_button("キャンセル", use_container_width=True)
    if cancel:
        st.rerun()
    if create:
        try:
            service.create_group(user_id, name, description, tone)
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.toast("グループを作成しました。")
        st.rerun()


def open_watchlist_groups_editor(
    state: WatchlistGroupsState,
    *,
    focus_group_id: str | None = None,
) -> None:
    st.session_state[EDITOR_DRAFT_KEY] = state.model_copy(deep=True)
    st.session_state[EDITOR_OPEN_KEY] = True
    st.session_state[EDITOR_FOCUS_KEY] = focus_group_id


@st.dialog("ウォッチリストグループを編集", width="large")
def render_watchlist_groups_editor(
    service: WatchlistGroupsService,
    user_id: str,
) -> None:
    st.markdown('<span class="smai-watchlist-editor-marker"></span>', unsafe_allow_html=True)
    draft = st.session_state.get(EDITOR_DRAFT_KEY)
    if not isinstance(draft, WatchlistGroupsState):
        draft = service.list_groups(user_id).model_copy(deep=True)
        st.session_state[EDITOR_DRAFT_KEY] = draft
    st.caption("銘柄チップをドラッグしてグループへ移動できます。")
    _render_editor_add_group(draft)
    draft = _editor_draft()
    _render_editor_groups(draft)
    save_col, cancel_col = st.columns(2)
    with save_col:
        st.markdown('<span class="smai-watchlist-action-save"></span>', unsafe_allow_html=True)
        save = st.button(
            "保存して閉じる",
            key="watchlist_groups_editor_save",
            use_container_width=True,
        )
    with cancel_col:
        st.markdown(
            '<span class="smai-watchlist-action-secondary"></span>',
            unsafe_allow_html=True,
        )
        cancel = st.button(
            "キャンセル",
            key="watchlist_groups_editor_cancel",
            use_container_width=True,
        )
    if cancel:
        _close_editor()
        st.rerun()
    if save:
        service.save_state(user_id, _editor_draft())
        _close_editor()
        st.toast("ウォッチリストグループを保存しました。")
        st.rerun()


def _render_editor_add_group(draft: WatchlistGroupsState) -> None:
    with st.expander("＋ グループ追加"):
        with st.form("watchlist_groups_editor_add_form", clear_on_submit=True):
            name = st.text_input("新しいグループ名", max_chars=32)
            description = st.text_input("説明（任意）", max_chars=200)
            default_tone = assign_default_tone(draft)
            tone = st.selectbox(
                "トーン",
                list(WATCHLIST_GROUP_TONES),
                index=list(WATCHLIST_GROUP_TONES).index(default_tone),
                format_func=lambda value: TONE_LABELS[value],
                key="watchlist_groups_editor_add_tone",
            )
            add = st.form_submit_button("追加", type="primary", use_container_width=True)
        if add:
            try:
                st.session_state[EDITOR_DRAFT_KEY] = draft_add_group(draft, name, description, tone)
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
                return
            st.rerun()


def _render_editor_groups(draft: WatchlistGroupsState) -> None:
    rows = st.session_state.get("watchlist_groups_editor_rows", [])
    if not isinstance(rows, list):
        rows = []
    sections = build_grouped_watchlist(rows, draft)
    for section in sections:
        if not section.is_system:
            _render_editor_group_settings(draft, str(section.group_id))
            draft = _editor_draft()
    containers, item_symbols, header_groups = build_sortable_watchlist_containers(rows, draft)
    sorted_containers = sort_items(
        containers,
        multi_containers=True,
        direction="horizontal",
        custom_style=WATCHLIST_SORTABLE_STYLE,
        key="watchlist_groups_dnd_board",
    )
    updated = apply_sortable_payload(
        draft,
        sorted_containers,
        item_symbols=item_symbols,
        header_groups=header_groups,
    )
    if updated != draft:
        st.session_state[EDITOR_DRAFT_KEY] = updated


def _render_editor_group_settings(draft: WatchlistGroupsState, group_id: str) -> None:
    group = next(item for item in draft.groups if item.group_id == group_id)
    with st.expander(
        f"{group.name} を編集",
        expanded=st.session_state.get(EDITOR_FOCUS_KEY) == group_id,
    ):
        with st.form(f"watchlist_groups_editor_group_{group_id}"):
            name = st.text_input(
                "グループ名",
                value=group.name,
                max_chars=32,
                key=f"watchlist_groups_editor_name_{group_id}",
            )
            description = st.text_input(
                "説明",
                value=group.description or "",
                max_chars=200,
                key=f"watchlist_groups_editor_description_{group_id}",
            )
            tone = st.selectbox(
                "トーン",
                list(WATCHLIST_GROUP_TONES),
                index=list(WATCHLIST_GROUP_TONES).index(group.tone),
                format_func=lambda value: TONE_LABELS[value],
                key=f"watchlist_groups_editor_tone_{group_id}",
            )
            update = st.form_submit_button("変更をdraftへ反映", use_container_width=True)
        if update:
            try:
                st.session_state[EDITOR_DRAFT_KEY] = draft_update_group(
                    draft, group_id, name, description, tone
                )
            except ValueError as exc:
                st.error(str(exc))
                return
            st.rerun()
        confirm = st.checkbox(
            "削除を確認しました。中の銘柄はお気に入りから削除されず、未分類へ移動します。",
            key=f"watchlist_groups_editor_delete_confirm_{group_id}",
        )
        st.markdown('<span class="smai-watchlist-action-danger"></span>', unsafe_allow_html=True)
        if st.button(
            "このグループを削除",
            key=f"watchlist_groups_editor_delete_{group_id}",
            disabled=not confirm,
            use_container_width=True,
        ):
            st.session_state[EDITOR_DRAFT_KEY] = draft_delete_group(draft, group_id)
            st.rerun()


def render_grouped_watchlist(
    rows: list[Mapping[str, str]],
    state: WatchlistGroupsState,
    *,
    render_card: Callable[[Mapping[str, str]], None],
) -> None:
    st.session_state["watchlist_groups_editor_rows"] = rows
    collapsed = st.session_state.setdefault(COLLAPSED_KEY, {})
    if not isinstance(collapsed, dict):
        collapsed = {}
        st.session_state[COLLAPSED_KEY] = collapsed
    for section in build_grouped_watchlist(rows, state):
        section_key = section.group_id or UNCLASSIFIED_VALUE
        is_collapsed = bool(collapsed.get(section_key, False))
        symbols = [str(item.get("symbol") or "") for item in section.items]
        st.markdown(
            group_section_header_html(
                section.name,
                section.description,
                section.tone,
                len(section.items),
                section.is_system,
                collapsed=is_collapsed,
                representative_symbols=symbols[:3],
            ),
            unsafe_allow_html=True,
        )
        toggle_col, edit_col = st.columns([1.2, 1])
        if toggle_col.button(
            "▶ 展開する" if is_collapsed else "▼ 閉じる",
            key=f"watchlist_group_toggle_{section_key}",
            use_container_width=True,
        ):
            collapsed[section_key] = not is_collapsed
            st.rerun()
        if not section.is_system and edit_col.button(
            "グループを編集",
            key=f"watchlist_group_edit_{section_key}",
            use_container_width=True,
        ):
            open_watchlist_groups_editor(state, focus_group_id=str(section.group_id))
            st.rerun()
        if is_collapsed:
            continue
        if not section.items:
            st.caption(
                "すべての銘柄がグループに配置されています。"
                if section.is_system
                else "このグループに配置された銘柄はありません。"
            )
            continue
        for start in range(0, len(section.items), 3):
            columns = st.columns(3)
            for column, row in zip(columns, section.items[start : start + 3]):
                with column:
                    render_card(row)


def draft_add_group(
    draft: WatchlistGroupsState,
    name: str,
    description: str | None,
    tone: WatchlistGroupTone,
) -> WatchlistGroupsState:
    if len(draft.groups) >= 20:
        raise ValueError("ウォッチリストグループは20件まで作成できます。")
    clean_name = validate_group_name(name)
    if any(group.name == clean_name for group in draft.groups):
        raise ValueError("同じ名前のグループは作成できません。")
    now = datetime.now(UTC)
    group = WatchlistGroup(
        group_id=f"wg_{secrets.token_hex(6)}",
        name=clean_name,
        description=description,
        tone=tone,
        order=max((item.order for item in draft.groups), default=0) + 10,
        created_at=now,
        updated_at=now,
    )
    return draft.model_copy(update={"groups": (*draft.groups, group), "updated_at": now})


def draft_update_group(
    draft: WatchlistGroupsState,
    group_id: str,
    name: str,
    description: str | None,
    tone: WatchlistGroupTone,
) -> WatchlistGroupsState:
    clean_name = validate_group_name(name)
    if any(group.name == clean_name and group.group_id != group_id for group in draft.groups):
        raise ValueError("同じ名前のグループは作成できません。")
    now = datetime.now(UTC)
    groups = tuple(
        (
            group.model_copy(
                update={
                    "name": clean_name,
                    "description": description,
                    "tone": tone,
                    "updated_at": now,
                }
            )
            if group.group_id == group_id
            else group
        )
        for group in draft.groups
    )
    if not any(group.group_id == group_id for group in draft.groups):
        raise ValueError("グループが見つかりません。")
    return WatchlistGroupsState(updated_at=now, groups=groups, placements=draft.placements)


def draft_delete_group(
    draft: WatchlistGroupsState,
    group_id: str,
) -> WatchlistGroupsState:
    now = datetime.now(UTC)
    return WatchlistGroupsState(
        updated_at=now,
        groups=tuple(group for group in draft.groups if group.group_id != group_id),
        placements={
            symbol: placement
            for symbol, placement in draft.placements.items()
            if placement.group_id != group_id
        },
    )


def draft_move_symbol(
    draft: WatchlistGroupsState,
    symbol: str,
    group_id: str | None,
) -> WatchlistGroupsState:
    placements = dict(draft.placements)
    now = datetime.now(UTC)
    if group_id is None:
        placements.pop(symbol, None)
    else:
        if not any(group.group_id == group_id for group in draft.groups):
            raise ValueError("グループが見つかりません。")
        previous = placements.get(symbol)
        placements[symbol] = WatchlistPlacement(
            group_id=group_id,
            order=previous.order if previous else 10,
            updated_at=now,
        )
    return draft.model_copy(update={"placements": placements, "updated_at": now})


def group_section_header_html(
    name: str,
    description: str | None,
    tone: str,
    count: int,
    is_system: bool,
    *,
    collapsed: bool = False,
    representative_symbols: list[str] | None = None,
) -> str:
    safe_tone = tone if tone in WATCHLIST_GROUP_TONES else "slate"
    description_text = description or (
        "まだグループに配置していないお気に入り銘柄です。" if is_system else ""
    )
    representative = ""
    if collapsed:
        symbols = ", ".join(representative_symbols or []) or "なし"
        representative = (
            f'<div class="smai-watchlist-group-representative">上位: {html.escape(symbols)}</div>'
        )
    icon = "▶" if collapsed else "▼"
    return (
        f'<section class="smai-watchlist-group-section '
        f'smai-watchlist-group-section--tone-{safe_tone}">'
        '<div class="smai-watchlist-group-header">'
        f"<strong>{icon} {html.escape(name)}</strong>"
        f'<span class="smai-watchlist-group-count-badge">{count}件</span>'
        "</div>"
        f"<p>{html.escape(description_text)}</p>{representative}</section>"
    )


WATCHLIST_SORTABLE_STYLE = """
.sortable-component { gap: 8px; }
.sortable-container {
  min-width: 0; margin: 0 0 8px; padding: 6px;
  border: 1px solid rgba(100,149,190,.45); border-radius: 10px;
  background: rgba(7,18,34,.88);
}
.sortable-container-header {
  margin: 0 0 5px; padding: 2px 4px; color: #eafcff;
  font-size: 13px; font-weight: 800;
}
.sortable-container-body { min-height: 42px; display: flex; flex-wrap: wrap; gap: 5px; }
.sortable-item {
  max-width: 100%; min-height: 34px; margin: 0; padding: 6px 9px;
  border: 1px solid rgba(34,211,238,.5); border-radius: 999px;
  background: rgba(8,57,79,.82); color: #f8fdff;
  font-size: 12px; line-height: 1.25; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; cursor: grab;
}
.sortable-item::before { content: "⋮⋮ "; color: #7dd3fc; }
@media (max-width: 767px) {
  .sortable-component { display: block !important; }
  .sortable-container { width: 100% !important; }
  .sortable-item { width: 100%; }
}
"""


def build_sortable_watchlist_containers(
    rows: list[Mapping[str, str]],
    draft: WatchlistGroupsState,
) -> tuple[list[dict[str, object]], dict[str, str], dict[str, str | None]]:
    containers: list[dict[str, object]] = []
    item_symbols: dict[str, str] = {}
    header_groups: dict[str, str | None] = {}
    for section in build_grouped_watchlist(rows, draft):
        header = f"{section.name}　{len(section.items)}件"
        header_groups[header] = section.group_id
        items: list[str] = []
        for row in section.items:
            symbol = str(row.get("symbol") or "").strip().upper()
            name = str(row.get("name") or symbol).strip()
            label = f"{symbol} | {name[:34]}"
            item_symbols[label] = symbol
            items.append(label)
        containers.append({"header": header, "items": items})
    return containers, item_symbols, header_groups


def apply_sortable_payload(
    draft: WatchlistGroupsState,
    payload: object,
    *,
    item_symbols: Mapping[str, str],
    header_groups: Mapping[str, str | None],
) -> WatchlistGroupsState:
    if not isinstance(payload, list):
        return draft
    placements = dict(draft.placements)
    seen: set[str] = set()
    now = datetime.now(UTC)
    for container in payload:
        if not isinstance(container, Mapping):
            return draft
        header = str(container.get("header") or "")
        if header not in header_groups:
            return draft
        items = container.get("items")
        if not isinstance(items, list):
            return draft
        group_id = header_groups[header]
        for index, label_value in enumerate(items):
            symbol = item_symbols.get(str(label_value))
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            if group_id is None:
                placements.pop(symbol, None)
            else:
                placements[symbol] = WatchlistPlacement(
                    group_id=group_id,
                    order=(index + 1) * 10,
                    updated_at=now,
                )
    return draft.model_copy(update={"placements": placements, "updated_at": now})


def compact_watchlist_card_html(row: Mapping[str, str]) -> str:
    """Legacy helper retained for tests; editor now uses sortable text chips."""
    symbol = html.escape(str(row.get("symbol") or "未取得"))
    name = html.escape(str(row.get("name") or symbol))
    return f'<span class="smai-watchlist-editor-chip">{symbol} | {name}</span>'


def group_preview_html(name: str, description: str, tone: str) -> str:
    return group_section_header_html(name, description or None, tone, 0, False)


def _editor_draft() -> WatchlistGroupsState:
    draft = st.session_state.get(EDITOR_DRAFT_KEY)
    if not isinstance(draft, WatchlistGroupsState):
        raise RuntimeError("編集内容を読み込めません。")
    return draft


def _close_editor() -> None:
    st.session_state.pop(EDITOR_DRAFT_KEY, None)
    st.session_state.pop(EDITOR_OPEN_KEY, None)
    st.session_state.pop(EDITOR_FOCUS_KEY, None)


def clear_watchlist_group_transient_state() -> None:
    for key in tuple(st.session_state):
        if str(key).startswith("watchlist_group_") or key in {
            EDITOR_OPEN_KEY,
            EDITOR_DRAFT_KEY,
            EDITOR_FOCUS_KEY,
            COLLAPSED_KEY,
        }:
            st.session_state.pop(key, None)


def empty_watchlist_groups_state() -> WatchlistGroupsState:
    return WatchlistGroupsState(updated_at=datetime.now(UTC))
