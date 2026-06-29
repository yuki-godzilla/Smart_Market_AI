from __future__ import annotations

import html

import streamlit as st
import streamlit.components.v1 as components

from backend.notifications.history_repository import NotificationHistoryRepository
from backend.notifications.settings_repository import NotificationSettingsError
from backend.notifications.trusted_devices import (
    SmaiUser,
    TrustedDeviceRepository,
    normalize_device_id,
)

DEFAULT_NOTIFICATION_USER_ID = "local_user"
DEVICE_QUERY_KEY = "smai_device_id"
DEVICE_NAME_QUERY_KEY = "smai_device_name"
MASCOTS = {
    "smai": "🤖 SMAIくん",
    "cat": "🐱 ネコ",
    "black_cat": "🐈‍⬛ クロネコ",
    "dog": "🐶 イヌ",
    "owl": "🦉 フクロウ",
    "chick": "🐤 ヒヨコ",
    "robot": "🦾 AIロボット",
    "penguin": "🐧 ペンギン",
}


def trusted_device_bootstrap_html() -> str:
    return f"""
<script>
(() => {{
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
        const clean = button.innerText.replace("SMAI_USER_AREA", "").trim();
        const parts = clean.split(/\\s+/);
        button.textContent = "";
        button.classList.add("smai-user-trigger");
        const compact = window.parent.document.createElement("span");
        compact.className = "smai-user-compact";
        compact.textContent = parts.slice(0, 2).join(" ");
        const detail = window.parent.document.createElement("span");
        detail.className = "smai-user-detail";
        detail.textContent = " " + parts.slice(2).join(" ");
        button.append(compact, detail);
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
        .smai-user-trigger {{ min-height: 44px; border-color: #22d3ee !important; }}
        .smai-notification-card {{ border: 1px solid #164e63; border-left: 4px solid #22d3ee;
          border-radius: 10px; padding: .65rem .75rem; margin: .45rem 0; background: #071827; }}
        .smai-notification-card.high {{ border-left-color: #f59e0b; }}
        .smai-notification-card.critical {{ border-left-color: #ef4444; }}
        .smai-notification-card.low {{ border-left-color: #64748b; }}
        @media (max-width: 767px) {{ .smai-user-detail {{ display: none; }} }}
      `;
      window.parent.document.head.appendChild(style);
    }}
  }}, 250);
}})();
</script>
"""


def render_user_notification_area() -> None:
    components.html(trusted_device_bootstrap_html(), height=0, width=0)
    device_id = _query_value(DEVICE_QUERY_KEY)
    device_name = _query_value(DEVICE_NAME_QUERY_KEY) or "この端末"
    try:
        devices = TrustedDeviceRepository()
    except NotificationSettingsError:
        st.warning("ユーザー情報を読み込めませんでした。")
        return
    users = devices.users()
    session_user_id = st.session_state.get("smai_current_user_id")
    user = next((item for item in users if item.user_id == session_user_id), None)
    if user is None:
        user = devices.resolve(device_id) if device_id else None
    if user is None:
        user = _select_user(devices, users, device_id, device_name)
    if user is None:
        return

    repository = NotificationHistoryRepository()
    try:
        unread = repository.unread_count(user.user_id)
        important = len(repository.list(user.user_id, state="unread", important_only=True))
    except NotificationSettingsError:
        unread, important = 0, 0
    mascot = MASCOTS.get(user.mascot_key, MASCOTS["smai"]).split()[0]
    with st.popover(f"SMAI_USER_AREA 🔔{unread} {mascot} {user.display_name}"):
        st.caption(f"{user.display_name} / {user.user_id}　重要 {important}")
        _render_notification_center(repository, user)
        st.divider()
        _render_user_menu(devices, user, users, device_id, device_name)


def _select_user(
    repository: TrustedDeviceRepository,
    users: list[SmaiUser],
    device_id: str,
    device_name: str,
) -> SmaiUser | None:
    if not users:
        return None
    st.info("ユーザーを選択してください。これはログイン認証ではありません。")
    selected = st.selectbox(
        "表示ユーザー",
        [user.user_id for user in users],
        format_func=lambda value: next(u.display_name for u in users if u.user_id == value),
        key="initial_device_user",
    )
    remember = st.checkbox(
        "この端末では次回からこのユーザーを使用する",
        value=True,
        key="remember_device_user",
    )
    if st.button("このユーザーで開始", key="start_selected_user", type="primary"):
        user = next(user for user in users if user.user_id == selected)
        if remember and normalize_device_id(device_id):
            repository.trust(device_id, user.user_id, device_name)
        st.session_state["smai_current_user_id"] = user.user_id
        st.rerun()
    session_user = st.session_state.get("smai_current_user_id")
    return next((user for user in users if user.user_id == session_user), None)


def _render_notification_center(repository: NotificationHistoryRepository, user: SmaiUser) -> None:
    st.markdown("#### 通知センター")
    category = st.selectbox(
        "カテゴリ",
        ["すべて", "FAVORITE", "MARKET_TREND", "INVESTMENT_NEWS", "SMAI_INSIGHT", "SYSTEM"],
        key="notification_center_category",
    )
    state = st.selectbox("状態", ["unread", "read", "archived"], key="notification_center_state")
    period = st.selectbox("期間", [1, 7, 30], format_func=lambda value: f"{value}日")
    important = st.checkbox("重要のみ", key="notification_center_important")
    try:
        items = repository.list(
            user.user_id,
            state=state,
            category=None if category == "すべて" else category,
            days=period,
            important_only=important,
        )
    except NotificationSettingsError:
        st.error("通知を読み込めませんでした。")
        return
    if not items:
        st.info("該当する通知はありません。")
    for item in items[:30]:
        st.markdown(
            '<div class="smai-notification-card '
            f'{html.escape(item.severity)}"><strong>🔔 {html.escape(item.title)}</strong>'
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


def _render_user_menu(
    repository: TrustedDeviceRepository,
    user: SmaiUser,
    users: list[SmaiUser],
    device_id: str,
    device_name: str,
) -> None:
    with st.expander("ユーザーメニュー"):
        st.caption("端末記憶はユーザー選択の自動化であり、認証ではありません。")
        selected_user = st.selectbox(
            "ユーザー切替",
            [item.user_id for item in users],
            index=[item.user_id for item in users].index(user.user_id),
            format_func=lambda value: next(u.display_name for u in users if u.user_id == value),
            key="switch_smai_user",
        )
        remember_switch = st.radio(
            "この端末の既定ユーザー",
            ["変更する", "今回だけ"],
            horizontal=True,
            key="remember_switched_user",
        )
        if st.button("ユーザーを切り替える", key="switch_smai_user_button"):
            if remember_switch == "変更する" and normalize_device_id(device_id):
                repository.trust(device_id, selected_user, device_name)
            st.session_state["smai_current_user_id"] = selected_user
            st.rerun()
        if st.button("通知設定を開く", key="open_notification_settings"):
            st.session_state["sidemenu_page"] = "settings"
            st.rerun()

        mascot = st.selectbox(
            "マスコット変更",
            list(MASCOTS),
            index=list(MASCOTS).index(user.mascot_key) if user.mascot_key in MASCOTS else 0,
            format_func=lambda value: MASCOTS[value],
            key="smai_user_mascot",
        )
        if st.button("マスコットを保存", key="save_smai_user_mascot"):
            repository.set_mascot(user.user_id, mascot)
            st.rerun()

        st.markdown("##### 登録済み端末")
        for device in repository.list(user.user_id):
            label = f"{device.device_name} / {device.last_seen_at.date().isoformat()}"
            st.caption(("現在の端末: " if device.device_id == device_id else "") + label)
            renamed = st.text_input(
                "端末名",
                value=device.device_name,
                key=f"device_name_{device.device_id}",
                label_visibility="collapsed",
            )
            if st.button("名前を変更", key=f"rename_device_{device.device_id}"):
                repository.rename(user.user_id, device.device_id, renamed)
                st.rerun()
            if st.button("この端末を解除", key=f"revoke_device_{device.device_id}"):
                repository.revoke(user.user_id, device.device_id)
                if device.device_id == device_id:
                    st.session_state.pop("smai_current_user_id", None)
                st.rerun()


def _query_value(key: str) -> str:
    params = getattr(st, "query_params", {})
    value = params.get(key, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)
