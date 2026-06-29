from __future__ import annotations

import html
import json

import streamlit as st
import streamlit.components.v1 as components

from backend.notifications.history_repository import NotificationHistoryRepository
from backend.notifications.settings_repository import NotificationSettingsError
from backend.notifications.trusted_devices import (
    SmaiUser,
    TrustedDeviceRepository,
    normalize_device_id,
)
from ui.notification_ui import render_notification_settings
from ui.user_icon_assets import (
    load_user_icon_assets,
    resolve_user_icon,
    user_icon_browser_source,
)

DEFAULT_NOTIFICATION_USER_ID = "local_user"
DEVICE_QUERY_KEY = "smai_device_id"
DEVICE_NAME_QUERY_KEY = "smai_device_name"
CATEGORY_LABELS = {
    "すべて": "すべて",
    "FAVORITE": "お気に入り",
    "MARKET_TREND": "市場",
    "INVESTMENT_NEWS": "ニュース",
    "SMAI_INSIGHT": "SMAI分析",
    "SYSTEM": "システム",
}
USER_AREA_VIEW_KEY = "smai_user_area_view"
USER_AREA_HOME = "main"


def trusted_device_bootstrap_html(
    *,
    icon_public_path: str | None = None,
    display_name: str = "",
    user_id: str = "",
    unread: int = 0,
) -> str:
    icon_json = json.dumps(icon_public_path or "")
    display_json = json.dumps(display_name, ensure_ascii=True)
    user_json = json.dumps(user_id, ensure_ascii=True)
    return f"""
<script>
(() => {{
  const iconUrl = {icon_json};
  const displayName = {display_json};
  const userId = {user_json};
  const unread = {max(0, unread)};
  const key = "smai_trusted_device_id";
  let id = window.parent.localStorage.getItem(key);
  if (!id) {{
    id = window.parent.crypto.randomUUID();
    window.parent.localStorage.setItem(key, id);
  }}
  const ua = window.parent.navigator.userAgent;
  const name = /iPad/.test(ua) ? "iPad Safari"
    : /iPhone/.test(ua) ? "iPhone Safari"
    : /Windows/.test(ua) ? "Windows Browser" : "Browser Device";
  const url = new URL(window.parent.location.href);
  if (url.searchParams.get("{DEVICE_QUERY_KEY}") !== id) {{
    url.searchParams.set("{DEVICE_QUERY_KEY}", id);
    url.searchParams.set("{DEVICE_NAME_QUERY_KEY}", name);
    window.parent.location.replace(url.toString());
  }}
  setTimeout(() => {{
    for (const button of window.parent.document.querySelectorAll("button")) {{
      if (button.innerText.includes("SMAI_USER_AREA")) {{
        button.textContent = "";
        button.classList.add("smai-user-trigger");
        const bell = window.parent.document.createElement("span");
        bell.className = "smai-user-bell";
        bell.textContent = `🔔 ${{unread}}`;
        const avatar = iconUrl
          ? window.parent.document.createElement("img")
          : window.parent.document.createElement("span");
        avatar.className = iconUrl ? "smai-user-avatar" : "smai-user-silhouette";
        if (iconUrl) {{
          avatar.src = iconUrl;
          avatar.alt = "";
        }} else {{
          avatar.setAttribute("aria-label", "ユーザーアイコン");
        }}
        const name = window.parent.document.createElement("span");
        name.className = "smai-user-name";
        name.textContent = displayName;
        const id = window.parent.document.createElement("span");
        id.className = "smai-user-id";
        id.textContent = userId ? ` / ${{userId}}` : "";
        button.append(bell, avatar, name, id);
        const host = button.closest('[data-testid="stPopover"]');
        if (host) {{
          host.style.position = "fixed";
          host.style.top = "0.55rem";
          host.style.right = "1rem";
          host.style.zIndex = "100000";
        }}
      }}
    }}
    if (!window.parent.document.getElementById("smai-user-area-style")) {{
      const style = window.parent.document.createElement("style");
      style.id = "smai-user-area-style";
      style.textContent = `
        .smai-user-trigger {{ min-height: 48px; gap: .42rem; border-color: #22d3ee !important; }}
        .smai-user-avatar, .smai-user-silhouette {{ width: 38px; height: 38px; border-radius: 50%;
          object-fit: cover; flex: 0 0 38px; border: 1px solid #22d3ee; background: #10243a; }}
        .smai-user-silhouette::after {{ content: ""; display: block; width: 14px; height: 14px;
          margin: 7px auto 0; border-radius: 50% 50% 42% 42%; background: #7890a8;
          box-shadow: 0 11px 0 5px #7890a8; }}
        .smai-profile-card {{ max-width: 190px; margin: 0 auto .4rem; padding: .7rem;
          border: 1px solid #24415f; border-radius: 14px; background: #0a192b;
          text-align: center; transition: border-color .18s ease, box-shadow .18s ease; }}
        .smai-profile-card:hover {{ border-color: #22d3ee; box-shadow: 0 0 20px #0891b244; }}
        .smai-profile-card img {{ width: 100%; aspect-ratio: 1; object-fit: cover;
          border-radius: 12px; display: block; }}
        .smai-profile-name {{ margin-top: .55rem; color: #e6f6ff; font-weight: 800; }}
        .smai-notification-card {{ border: 1px solid #164e63; border-left: 4px solid #22d3ee;
          border-radius: 10px; padding: .65rem .75rem; margin: .45rem 0; background: #071827; }}
        .smai-notification-card.high {{ border-left-color: #f59e0b; }}
        .smai-notification-card.critical {{ border-left-color: #ef4444; }}
        .smai-notification-card.low {{ border-left-color: #64748b; }}
        .smai-notification-asset {{ width: 34px; height: 34px; margin-right: .55rem;
          border-radius: 9px; object-fit: cover; vertical-align: middle; }}
        @media (max-width: 1024px) {{ .smai-user-id {{ display: none; }} }}
        @media (max-width: 767px) {{ .smai-user-name, .smai-user-id {{ display: none; }}
          .smai-user-trigger {{ min-width: 96px; }} .smai-profile-card {{ max-width: 156px; }} }}
      `;
      window.parent.document.head.appendChild(style);
    }}
  }}, 250);
}})();
</script>
"""


def render_user_notification_area() -> bool:
    """Resolve the active user before allowing the main SMAI surface to render."""
    components.html(trusted_device_bootstrap_html(), height=0, width=0)
    device_id = _query_value(DEVICE_QUERY_KEY)
    device_name = _query_value(DEVICE_NAME_QUERY_KEY) or "この端末"
    try:
        devices = TrustedDeviceRepository()
    except NotificationSettingsError:
        st.warning("ユーザー情報を読み込めませんでした。")
        return False
    users = devices.users()
    session_user_id = st.session_state.get("smai_current_user_id")
    user = next((item for item in users if item.user_id == session_user_id), None)
    if user is None:
        user = devices.resolve(device_id) if device_id else None
    if user is None:
        user = _select_user(devices, users, device_id, device_name)
    if user is None:
        return False

    repository = NotificationHistoryRepository()
    try:
        unread = repository.unread_count(user.user_id)
        important = len(repository.list(user.user_id, state="unread", important_only=True))
    except NotificationSettingsError:
        unread, important = 0, 0
    icon = resolve_user_icon(user.icon_id)
    with st.popover(f"SMAI_USER_AREA 🔔 {unread} {user.display_name} / {user.user_id}"):
        _render_user_menu(user, unread, important)
    components.html(
        trusted_device_bootstrap_html(
            icon_public_path=user_icon_browser_source(icon),
            display_name=user.display_name,
            user_id=user.user_id,
            unread=unread,
        ),
        height=0,
        width=0,
    )
    view = str(st.session_state.get(USER_AREA_VIEW_KEY, USER_AREA_HOME))
    if view != USER_AREA_HOME:
        _render_user_area_view(
            view,
            repository,
            devices,
            user,
            users,
            device_id,
            device_name,
        )
        return False
    return True


def _select_user(
    repository: TrustedDeviceRepository,
    users: list[SmaiUser],
    device_id: str,
    device_name: str,
) -> SmaiUser | None:
    if not users:
        return None
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
        [data-testid="stHeader"] { background: transparent !important; }
        .stApp {
          background:
            radial-gradient(circle at 50% 12%, rgba(8,145,178,.16), transparent 34rem),
            linear-gradient(180deg, #050d1a 0%, #071426 100%);
        }
        .block-container { max-width: 960px; padding: 7vh 1.5rem 4rem !important; }
        .smai-profile-gate-brand {
          color: #67e8f9; font-size: .86rem; font-weight: 900; letter-spacing: .24em;
          text-align: center; text-transform: uppercase;
        }
        .smai-profile-gate-title {
          margin: .8rem 0 .35rem; color: #f8fbff; font-size: clamp(2rem, 4vw, 3.4rem);
          font-weight: 850; text-align: center; letter-spacing: -.035em;
        }
        .smai-profile-gate-note {
          margin-bottom: 1.7rem; color: #91a8bf; text-align: center;
        }
        .smai-profile-card {
          width: min(100%, 220px); margin: 0 auto .45rem; padding: .72rem;
          border: 2px solid #203b59; border-radius: 18px; background: #0b1b30;
          cursor: pointer;
          box-shadow: 0 15px 35px rgba(0,0,0,.24);
          transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease;
        }
        .smai-profile-card:hover, .smai-profile-card.selected,
        div[data-testid="stColumn"]:has(button:hover) .smai-profile-card,
        div[data-testid="stColumn"]:has(button:hover) .smai-add-profile {
          transform: translateY(-4px); border-color: #22d3ee;
          box-shadow: 0 0 28px rgba(34,211,238,.28);
        }
        .smai-profile-card img {
          width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 12px; display: block;
        }
        .smai-profile-name {
          margin: .75rem 0 .15rem; color: #edf8ff; font-size: 1.05rem;
          font-weight: 850; text-align: center;
        }
        .smai-add-profile {
          display: grid; place-items: center; width: min(100%, 220px); aspect-ratio: 1;
          margin: 0 auto .45rem; border: 2px dashed #35516e; border-radius: 18px;
          background: #0b1b30; color: #8ca6bd; font-size: 4rem; cursor: pointer;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
          position: relative;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]
          div[data-testid="stButton"] {
          position: absolute; inset: 0 0 auto; height: calc(100% - .25rem); z-index: 2;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]
          div[data-testid="stButton"] > button {
          width: 100%; height: 100%; opacity: 0;
        }
        div[data-testid="stButton"] > button {
          display: flex; width: min(100%, 220px); min-width: 0; margin-inline: auto;
          justify-content: center;
        }
        div[data-testid="stCheckbox"] { width: fit-content; margin: 1.2rem auto .5rem; }
        div[data-testid="stCheckbox"] label { justify-content: center; }
        @media (max-width: 767px) {
          .block-container { padding-top: 3rem !important; }
          .smai-profile-card, .smai-add-profile { max-width: 280px; }
        }
        </style>
        <div class="smai-profile-gate-brand">Smart Market AI</div>
        <div class="smai-profile-gate-title">どのユーザーで使いますか？</div>
        <div class="smai-profile-gate-note">
          表示するユーザーを選択してください。これはログイン認証ではありません。
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected_user_id = str(st.session_state.get("smai_profile_candidate", ""))
    card_count = len(users) + 1
    column_count = min(5, card_count)
    columns = st.columns(column_count, gap="medium")
    for index, candidate in enumerate(users):
        icon = resolve_user_icon(candidate.icon_id)
        selected_class = " selected" if candidate.user_id == selected_user_id else ""
        source = user_icon_browser_source(icon)
        with columns[index % column_count]:
            if source:
                st.markdown(
                    f'<div class="smai-profile-card{selected_class}">'
                    f'<img src="{html.escape(source)}" alt="">'
                    f'<div class="smai-profile-name">{html.escape(candidate.display_name)}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="smai-profile-card{selected_class}">'
                    '<div class="smai-add-profile" aria-label="ユーザーアイコン"></div>'
                    f'<div class="smai-profile-name">{html.escape(candidate.display_name)}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )
            if st.button(
                f"{candidate.display_name}を選択",
                key=f"select_profile_{candidate.user_id}",
                type="primary" if candidate.user_id == selected_user_id else "secondary",
            ):
                st.session_state["smai_profile_candidate"] = candidate.user_id
                st.rerun()
    with columns[len(users) % column_count]:
        st.markdown(
            '<div class="smai-add-profile" aria-hidden="true">＋</div>'
            '<div class="smai-profile-name">ユーザー追加</div>',
            unsafe_allow_html=True,
        )
        if st.button("ユーザー追加", key="add_smai_profile"):
            st.info("ユーザー追加は次フェーズで対応予定です。")

    remember = st.checkbox(
        "この端末では次回からこのユーザーを使用する",
        value=True,
        key="remember_device_user",
    )
    selected = next((item for item in users if item.user_id == selected_user_id), None)
    if selected is not None and st.button(
        "このユーザーで開始",
        key="start_selected_profile",
        type="primary",
    ):
        if remember and normalize_device_id(device_id):
            repository.trust(device_id, selected.user_id, device_name)
        st.session_state["smai_current_user_id"] = selected.user_id
        st.session_state.pop("smai_profile_candidate", None)
        st.rerun()
    session_user = st.session_state.get("smai_current_user_id")
    return next((user for user in users if user.user_id == session_user), None)


def _render_notification_center(repository: NotificationHistoryRepository, user: SmaiUser) -> None:
    st.markdown("#### 通知センター")
    category = st.selectbox(
        "カテゴリ",
        list(CATEGORY_LABELS),
        format_func=lambda value: CATEGORY_LABELS[value],
        key="notification_center_category",
    )
    state = st.selectbox("状態", ["unread", "read", "archived"], key="notification_center_state")
    period = st.selectbox("期間", [1, 7, 30], format_func=lambda value: f"{value}日")
    severity = st.selectbox(
        "重要度",
        ["すべて", "critical", "high", "medium", "low"],
        format_func=lambda value: value.title() if value != "すべて" else value,
        key="notification_center_severity",
    )
    important = st.checkbox("重要のみ", key="notification_center_important")
    try:
        items = repository.list(
            user.user_id,
            state=state,
            category=None if category == "すべて" else category,
            days=period,
            important_only=important,
            severity=None if severity == "すべて" else severity,
        )
    except NotificationSettingsError:
        st.error("通知を読み込めませんでした。")
        return
    if not items:
        st.info("該当する通知はありません。")
    for item in items[:30]:
        notification_icon = resolve_user_icon(str((item.metadata or {}).get("icon_asset_id", "")))
        notification_icon_source = user_icon_browser_source(notification_icon)
        icon_html = (
            f'<img class="smai-notification-asset" src="{html.escape(notification_icon_source)}" '
            'alt="">'
            if notification_icon_source
            else ""
        )
        st.markdown(
            '<div class="smai-notification-card '
            f'{html.escape(item.severity)}">{icon_html}<strong>{html.escape(item.title)}</strong>'
            f"<br>{html.escape(item.summary)}<br><small>"
            f"{html.escape(item.presentation_category)} / {html.escape(item.severity)}"
            "</small></div>",
            unsafe_allow_html=True,
        )
        read_col, archive_col = st.columns(2)
        if item.state == "unread" and read_col.button(
            "既読", key=f"notification_read_{item.event_id}"
        ):
            repository.mark_read(user.user_id, item.event_id)
            st.rerun()
        if archive_col.button("アーカイブ", key=f"notification_archive_{item.event_id}"):
            repository.archive(user.user_id, item.event_id)
            st.rerun()
        if item.action_url and item.action_url.startswith(("/", "?")):
            st.link_button("詳しく確認する", item.action_url)


def _render_user_menu(user: SmaiUser, unread: int, important: int) -> None:
    st.markdown(f"**{user.display_name}**")
    st.caption(f"{user.user_id}　未読 {unread}件 / 重要 {important}件")
    links = (
        ("通知センター", "notification_center"),
        ("通知設定", "notification_settings"),
        ("ユーザー設定", "user_settings"),
        ("アイコン変更", "icon_settings"),
        ("登録済み端末", "trusted_devices"),
        ("ユーザー切替", "switch_user"),
    )
    for label, view in links:
        if st.button(label, key=f"open_user_area_{view}", use_container_width=True):
            st.session_state[USER_AREA_VIEW_KEY] = view
            st.rerun()


def _render_user_area_view(
    view: str,
    notification_repository: NotificationHistoryRepository,
    user_repository: TrustedDeviceRepository,
    user: SmaiUser,
    users: list[SmaiUser],
    device_id: str,
    device_name: str,
) -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1120px; }
        .smai-user-view-title { margin-bottom: 1.25rem; }
        @media (max-width: 767px) {
          .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button("← SMAIに戻る", key="close_user_area_view"):
        st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
        st.rerun()

    if view == "notification_center":
        unread = notification_repository.unread_count(user.user_id)
        important = len(
            notification_repository.list(user.user_id, state="unread", important_only=True)
        )
        st.title("通知センター")
        st.caption(f"未読 {unread}件 / 重要 {important}件")
        _render_notification_center(notification_repository, user)
    elif view == "notification_settings":
        st.title("通知設定")
        st.caption("通知方法、重要度、Quiet hoursを設定します。保存だけでは送信しません。")
        render_notification_settings(user.user_id)
    elif view == "user_settings":
        _render_user_settings(user_repository, user, device_id)
    elif view == "icon_settings":
        _render_icon_settings(user_repository, user)
    elif view == "trusted_devices":
        st.title("登録済み端末")
        _render_trusted_devices(user_repository, user, device_id)
    elif view == "switch_user":
        _render_user_switch(user_repository, user, users, device_id, device_name)
    else:
        st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
        st.rerun()


def _render_user_settings(
    repository: TrustedDeviceRepository, user: SmaiUser, device_id: str
) -> None:
    st.title("ユーザー設定")
    st.caption("プロフィールと、この端末で使うユーザーを管理します。")
    display_name = st.text_input("表示名", value=user.display_name, disabled=user.is_system_user)
    st.text_input("user_id", value=user.user_id, disabled=True)
    st.text_input("icon_asset_id", value=user.icon_id, disabled=True)
    if user.is_system_user:
        st.info("SMAIデフォルトはシステム標準ユーザーのため、削除・名称変更できません。")
    elif st.button("表示名を保存", key="save_smai_display_name", type="primary"):
        repository.set_display_name(user.user_id, display_name)
        st.rerun()
    if st.button("アイコンを変更", key="user_settings_open_icons"):
        st.session_state[USER_AREA_VIEW_KEY] = "icon_settings"
        st.rerun()
    st.divider()
    st.subheader("登録済み端末")
    _render_trusted_devices(repository, user, device_id)
    if st.button("ユーザーを切り替える", key="user_settings_switch_user"):
        st.session_state[USER_AREA_VIEW_KEY] = "switch_user"
        st.rerun()


def _render_icon_settings(repository: TrustedDeviceRepository, user: SmaiUser) -> None:
    st.title("アイコン変更")
    current = resolve_user_icon(user.icon_id)
    if current.file_path is not None:
        st.image(str(current.file_path), width=160, caption="現在のアイコン")
    assets = load_user_icon_assets()
    if not assets:
        st.info("選択可能なアイコンAssetはありません。")
        return
    icon_ids = [asset.icon_id for asset in assets]
    selected_icon = st.selectbox(
        "プロフィールアイコン",
        icon_ids,
        index=icon_ids.index(user.icon_id) if user.icon_id in icon_ids else 0,
        format_func=lambda value: next(
            asset.display_name for asset in assets if asset.icon_id == value
        ),
        key="smai_user_icon",
    )
    columns = st.columns(4)
    for index, asset in enumerate(assets):
        with columns[index % 4]:
            st.image(
                str(asset.file_path),
                use_container_width=True,
                caption=("選択中: " if asset.icon_id == selected_icon else "") + asset.display_name,
            )
    if st.button("アイコンを保存", key="save_smai_user_icon", type="primary"):
        repository.set_icon(user.user_id, selected_icon)
        st.rerun()


def _render_trusted_devices(
    repository: TrustedDeviceRepository, user: SmaiUser, device_id: str
) -> None:
    st.caption("端末記憶はユーザー選択の自動化であり、ログイン認証ではありません。")
    devices = repository.list(user.user_id)
    if not devices:
        st.info("登録済み端末はありません。")
        return
    for device in devices:
        label = f"{device.device_name} / {device.last_seen_at.date().isoformat()}"
        st.markdown(f"**{'現在の端末: ' if device.device_id == device_id else ''}{label}**")
        renamed = st.text_input(
            "端末名",
            value=device.device_name,
            key=f"device_name_{device.device_id}",
            label_visibility="collapsed",
        )
        rename_col, revoke_col = st.columns(2)
        if rename_col.button("名前を変更", key=f"rename_device_{device.device_id}"):
            repository.rename(user.user_id, device.device_id, renamed)
            st.rerun()
        if revoke_col.button("Trusted Deviceを解除", key=f"revoke_device_{device.device_id}"):
            repository.revoke(user.user_id, device.device_id)
            if device.device_id == device_id:
                st.session_state.pop("smai_current_user_id", None)
                st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
            st.rerun()


def _render_user_switch(
    repository: TrustedDeviceRepository,
    user: SmaiUser,
    users: list[SmaiUser],
    device_id: str,
    device_name: str,
) -> None:
    st.title("ユーザー切替")
    selected_user = st.selectbox(
        "使用するユーザー",
        [item.user_id for item in users],
        index=[item.user_id for item in users].index(user.user_id),
        format_func=lambda value: next(u.display_name for u in users if u.user_id == value),
        key="switch_smai_user",
    )
    remember_switch = st.checkbox(
        "この端末では次回からこのユーザーを使用する",
        value=True,
        key="remember_switched_user",
    )
    if st.button("このユーザーに切り替える", key="switch_smai_user_button", type="primary"):
        if remember_switch and normalize_device_id(device_id):
            repository.trust(device_id, selected_user, device_name)
        st.session_state["smai_current_user_id"] = selected_user
        st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
        st.rerun()


def _query_value(key: str) -> str:
    params = getattr(st, "query_params", {})
    value = params.get(key, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)
