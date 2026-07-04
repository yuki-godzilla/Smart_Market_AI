from __future__ import annotations

import html
import secrets
from datetime import UTC, datetime
from typing import Callable, Mapping

import streamlit as st
from pydantic import ValidationError

from backend.watchlist_groups import (
    WATCHLIST_GROUP_TONES,
    GroupedWatchlistSection,
    WatchlistGroup,
    WatchlistGroupsRepository,
    WatchlistGroupsService,
    WatchlistGroupsState,
    WatchlistPlacement,
    assign_default_tone,
    build_grouped_watchlist,
)
from backend.watchlist_groups.models import WatchlistGroupTone, validate_group_name
from ui.components.watchlist_sortable import watchlist_sortable
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
EDITOR_DND_REVISION_KEY = "watchlist_groups_dnd_revision"
EDITOR_SELECTED_GROUP_KEY = "watchlist_groups_editor_selected_group"
EDITOR_SETTINGS_OPEN_KEY = "watchlist_groups_editor_settings_open"
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
TONE_SWATCHES = {
    "cyan": "🟦",
    "blue": "🔷",
    "purple": "🟪",
    "green": "🟩",
    "amber": "🟨",
    "orange": "🟧",
    "rose": "🟥",
    "slate": "⬜",
}


def tone_option_label(tone: str) -> str:
    return f"{TONE_SWATCHES[tone]}  {TONE_LABELS[tone]}"


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
    edit_col, mode_col = st.columns([1.35, 1.2])
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


def open_watchlist_groups_editor(
    state: WatchlistGroupsState,
    *,
    focus_group_id: str | None = None,
) -> None:
    st.session_state[EDITOR_DRAFT_KEY] = state.model_copy(deep=True)
    st.session_state[EDITOR_OPEN_KEY] = True
    st.session_state[EDITOR_FOCUS_KEY] = focus_group_id
    st.session_state[EDITOR_SELECTED_GROUP_KEY] = focus_group_id
    st.session_state[EDITOR_DND_REVISION_KEY] = 0
    st.session_state[EDITOR_SETTINGS_OPEN_KEY] = False
    st.session_state.pop("watchlist_groups_editor_group_selector", None)


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
                format_func=tone_option_label,
                key="watchlist_groups_editor_add_tone",
            )
            add = st.form_submit_button("追加", type="primary", use_container_width=True)
        if add:
            try:
                updated = draft_add_group(draft, name, description, tone)
                st.session_state[EDITOR_DRAFT_KEY] = updated
                st.session_state[EDITOR_SELECTED_GROUP_KEY] = updated.groups[-1].group_id
                st.session_state.pop("watchlist_groups_editor_group_selector", None)
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
                return
            st.rerun()


def _render_editor_groups(draft: WatchlistGroupsState) -> None:
    rows = st.session_state.get("watchlist_groups_editor_rows", [])
    if not isinstance(rows, list):
        rows = []
    _render_open_group_settings(draft)
    draft = _editor_draft()
    containers, item_symbols, header_groups = build_sortable_watchlist_containers(rows, draft)
    result = watchlist_sortable(
        containers,
        custom_style=sortable_watchlist_style(draft),
        key=f"watchlist_groups_dnd_board_{st.session_state.get(EDITOR_DND_REVISION_KEY, 0)}",
    )
    if result.get("type") == "action":
        _apply_group_board_action(draft, result)
        return
    updated = apply_sortable_payload(
        draft,
        result.get("containers"),
        item_symbols=item_symbols,
        header_groups=header_groups,
    )
    if updated != draft:
        st.session_state[EDITOR_DRAFT_KEY] = updated
        st.session_state[EDITOR_DND_REVISION_KEY] = (
            int(st.session_state.get(EDITOR_DND_REVISION_KEY, 0)) + 1
        )
        st.rerun()


def _apply_group_board_action(
    draft: WatchlistGroupsState,
    result: Mapping[str, object],
) -> None:
    group_id = str(result.get("groupId") or "")
    if not any(group.group_id == group_id for group in draft.groups):
        return
    action = str(result.get("action") or "")
    if action in {"up", "down"}:
        direction = -1 if action == "up" else 1
        st.session_state[EDITOR_DRAFT_KEY] = draft_move_group(draft, group_id, direction)
        _remount_dnd_board()
        st.rerun()
    if action == "edit":
        st.session_state[EDITOR_SELECTED_GROUP_KEY] = group_id
        st.session_state[EDITOR_SETTINGS_OPEN_KEY] = True
        _remount_dnd_board()
        st.rerun()


def _render_open_group_settings(draft: WatchlistGroupsState) -> None:
    if not st.session_state.get(EDITOR_SETTINGS_OPEN_KEY):
        return
    group_id = str(st.session_state.get(EDITOR_SELECTED_GROUP_KEY) or "")
    ordered_groups = list(sorted(draft.groups, key=lambda item: item.order))
    group = next((item for item in ordered_groups if item.group_id == group_id), None)
    if group is None:
        st.session_state[EDITOR_SETTINGS_OPEN_KEY] = False
        return
    _render_inline_group_settings(draft, group, ordered_groups.index(group))


def _render_inline_group_settings(
    draft: WatchlistGroupsState,
    group: WatchlistGroup,
    group_index: int,
) -> None:
    group_id = group.group_id
    with st.container(border=True):
        st.markdown(
            f'<div class="smai-watchlist-selected-group-title">'
            f"<strong>{html.escape(group.name)}</strong>"
            "<span>D&D boardのグループ設定</span></div>",
            unsafe_allow_html=True,
        )
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
                format_func=tone_option_label,
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
            st.session_state[EDITOR_SETTINGS_OPEN_KEY] = False
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
            updated = draft_delete_group(draft, group_id)
            st.session_state[EDITOR_DRAFT_KEY] = updated
            remaining = list(sorted(updated.groups, key=lambda item: item.order))
            st.session_state[EDITOR_SELECTED_GROUP_KEY] = (
                remaining[min(group_index, len(remaining) - 1)].group_id if remaining else None
            )
            st.session_state.pop("watchlist_groups_editor_group_selector", None)
            st.session_state[EDITOR_SETTINGS_OPEN_KEY] = False
            _remount_dnd_board()
            st.rerun()


def _remount_dnd_board() -> None:
    st.session_state[EDITOR_DND_REVISION_KEY] = (
        int(st.session_state.get(EDITOR_DND_REVISION_KEY, 0)) + 1
    )


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
        safe_tone = section.tone if section.tone in WATCHLIST_GROUP_TONES else "slate"
        with st.container(border=True):
            st.markdown(
                '<span class="smai-watchlist-group-panel-marker '
                f'smai-watchlist-group-panel-marker--tone-{safe_tone}"></span>',
                unsafe_allow_html=True,
            )
            _render_grouped_watchlist_section(
                section,
                section_key=section_key,
                safe_tone=safe_tone,
                is_collapsed=is_collapsed,
                collapsed=collapsed,
                symbols=symbols,
                render_card=render_card,
            )


def _render_grouped_watchlist_section(
    section: GroupedWatchlistSection,
    *,
    section_key: str,
    safe_tone: str,
    is_collapsed: bool,
    collapsed: dict[str, object],
    symbols: list[str],
    render_card: Callable[[Mapping[str, str]], None],
) -> None:
    st.markdown(
        '<span class="smai-watchlist-group-header-marker '
        f'smai-watchlist-group-header-marker--tone-{safe_tone}"></span>',
        unsafe_allow_html=True,
    )
    icon = "▶" if is_collapsed else "▼"
    if st.button(
        f"{icon} {section.name}　·　{len(section.items)}件",
        key=f"watchlist_group_tone_{safe_tone}_toggle_{section_key}",
        use_container_width=True,
        help="クリックしてグループを展開／折りたたみ",
    ):
        collapsed[section_key] = not is_collapsed
        st.rerun()
    description = section.description or (
        "まだグループに配置していないお気に入り銘柄です。" if section.is_system else ""
    )
    if description:
        st.caption(description)
    if is_collapsed:
        representative = ", ".join(symbols[:3]) or "なし"
        st.caption(f"上位: {representative}")
        return
    if not section.items:
        st.caption(
            "すべての銘柄がグループに配置されています。"
            if section.is_system
            else "このグループに配置された銘柄はありません。"
        )
        return
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


def draft_move_group(
    draft: WatchlistGroupsState,
    group_id: str,
    direction: int,
) -> WatchlistGroupsState:
    groups = list(sorted(draft.groups, key=lambda group: group.order))
    index = next(
        (position for position, group in enumerate(groups) if group.group_id == group_id),
        None,
    )
    if index is None:
        raise ValueError("グループが見つかりません。")
    target = index + direction
    if target < 0 or target >= len(groups):
        return draft
    groups[index], groups[target] = groups[target], groups[index]
    now = datetime.now(UTC)
    reordered = tuple(
        group.model_copy(update={"order": (position + 1) * 10, "updated_at": now})
        for position, group in enumerate(groups)
    )
    return draft.model_copy(update={"groups": reordered, "updated_at": now})


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
  overscroll-behavior: contain;
}
.sortable-container-header {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin: 0 0 5px; padding: 2px 4px; color: #eafcff;
  font-size: 13px; font-weight: 800;
}
.group-actions { display: inline-flex; gap: 6px; flex: 0 0 auto; }
.group-actions button {
  min-width: 38px; min-height: 34px; padding: 4px 10px;
  border: 1px solid rgba(126, 167, 211, .55); border-radius: 8px;
  background: rgba(12, 29, 53, .94); color: #f8fdff; font-weight: 800;
  cursor: pointer; touch-action: manipulation;
}
.group-actions button:last-child { min-width: 66px; }
.group-actions button:hover:not(:disabled) {
  border-color: #22d3ee; background: rgba(13, 62, 83, .95);
}
.group-actions button:disabled { opacity: .32; cursor: default; }
@media (max-width: 560px) {
  .sortable-container-header { align-items: flex-start; flex-direction: column; }
  .group-actions { width: 100%; }
  .group-actions button { flex: 1 1 0; }
}
.sortable-container-body { min-height: 42px; display: flex; flex-wrap: wrap; gap: 5px; }
.sortable-item {
  max-width: 100%; min-height: 34px; margin: 0; padding: 6px 9px;
  border: 1px solid rgba(34,211,238,.5); border-radius: 999px;
  background: rgba(8,57,79,.82); color: #f8fdff;
  font-size: 12px; line-height: 1.25; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; cursor: grab;
  touch-action: none; user-select: none; -webkit-user-select: none;
  -webkit-touch-callout: none;
}
.sortable-item::before { content: "⋮⋮ "; color: #7dd3fc; }
@media (max-width: 767px) {
  .sortable-component { display: block !important; }
  .sortable-container { width: 100% !important; }
  .sortable-item { width: 100%; }
}
"""

SORTABLE_TONE_STYLES = {
    "cyan": ("rgba(8, 67, 86, .88)", "#22d3ee"),
    "blue": ("rgba(18, 48, 94, .88)", "#60a5fa"),
    "purple": ("rgba(55, 37, 100, .88)", "#a78bfa"),
    "green": ("rgba(18, 69, 57, .88)", "#34d399"),
    "amber": ("rgba(87, 60, 13, .88)", "#fbbf24"),
    "orange": ("rgba(93, 45, 16, .88)", "#fb923c"),
    "rose": ("rgba(91, 31, 48, .88)", "#fb7185"),
    "slate": ("rgba(43, 53, 70, .88)", "#94a3b8"),
}


def sortable_watchlist_style(draft: WatchlistGroupsState) -> str:
    tones = [group.tone for group in sorted(draft.groups, key=lambda item: item.order)]
    tones.append("slate")
    tone_rules = []
    for index, tone in enumerate(tones, start=1):
        background, border = SORTABLE_TONE_STYLES[tone]
        tone_rules.append(
            f".sortable-container:nth-child({index}) "
            f"{{ background: {background}; border-color: {border}; }}"
        )
    return WATCHLIST_SORTABLE_STYLE + "\n" + "\n".join(tone_rules)


def build_sortable_watchlist_containers(
    rows: list[Mapping[str, str]],
    draft: WatchlistGroupsState,
) -> tuple[list[dict[str, object]], dict[str, str], dict[str, str | None]]:
    containers: list[dict[str, object]] = []
    item_symbols: dict[str, str] = {}
    header_groups: dict[str, str | None] = {}
    for section in build_grouped_watchlist(rows, draft):
        # Header text must stay stable across moves. Dynamic counts caused the component's
        # next payload to reference stale headers, so only the first move was accepted.
        header = section.name
        container_id = f"group:{section.group_id}" if section.group_id else "system:unclassified"
        header_groups[container_id] = section.group_id
        items: list[str] = []
        labels: dict[str, str] = {}
        for row in section.items:
            symbol = str(row.get("symbol") or "").strip().upper()
            name = str(row.get("name") or symbol).strip()
            label = f"{symbol} | {name[:34]}"
            item_symbols[symbol] = symbol
            labels[symbol] = label
            items.append(symbol)
        containers.append(
            {
                "id": container_id,
                "header": header,
                "items": items,
                "labels": labels,
                "groupId": section.group_id,
                "system": section.is_system,
                "tone": section.tone,
            }
        )
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
    if len(payload) != len(header_groups):
        return draft
    payload_container_ids: list[str] = []
    payload_item_ids: list[str] = []
    for container in payload:
        if not isinstance(container, Mapping):
            return draft
        container_id = str(container.get("id") or "")
        items = container.get("items")
        if container_id not in header_groups or not isinstance(items, list):
            return draft
        if not all(isinstance(item, str) for item in items):
            return draft
        payload_container_ids.append(container_id)
        payload_item_ids.extend(items)
    if len(payload_container_ids) != len(set(payload_container_ids)):
        return draft
    if set(payload_container_ids) != set(header_groups):
        return draft
    if len(payload_item_ids) != len(set(payload_item_ids)):
        return draft
    if set(payload_item_ids) != set(item_symbols):
        return draft

    placements = dict(draft.placements)
    now = datetime.now(UTC)
    for container in payload:
        container_id = str(container.get("id") or "")
        items = container["items"]
        group_id = header_groups[container_id]
        for index, label_value in enumerate(items):
            symbol = item_symbols.get(str(label_value))
            if not symbol:
                return draft
            if group_id is None:
                placements.pop(symbol, None)
            else:
                target_order = (index + 1) * 10
                current = placements.get(symbol)
                if current is None or current.group_id != group_id or current.order != target_order:
                    placements[symbol] = WatchlistPlacement(
                        group_id=group_id,
                        order=target_order,
                        updated_at=now,
                    )
    if placements == draft.placements:
        return draft
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
    st.session_state.pop(EDITOR_SELECTED_GROUP_KEY, None)
    st.session_state.pop(EDITOR_DND_REVISION_KEY, None)
    st.session_state.pop(EDITOR_SETTINGS_OPEN_KEY, None)


def clear_watchlist_group_transient_state() -> None:
    for key in tuple(st.session_state):
        if str(key).startswith("watchlist_group_") or key in {
            EDITOR_OPEN_KEY,
            EDITOR_DRAFT_KEY,
            EDITOR_FOCUS_KEY,
            EDITOR_SELECTED_GROUP_KEY,
            EDITOR_DND_REVISION_KEY,
            EDITOR_SETTINGS_OPEN_KEY,
            COLLAPSED_KEY,
        }:
            st.session_state.pop(key, None)


def empty_watchlist_groups_state() -> WatchlistGroupsState:
    return WatchlistGroupsState(updated_at=datetime.now(UTC))
