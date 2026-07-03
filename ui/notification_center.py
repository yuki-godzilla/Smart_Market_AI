from __future__ import annotations

import html
import json
import os
from datetime import UTC, datetime
from typing import Any, MutableMapping, cast

import streamlit as st
import streamlit.components.v1 as components

from backend.notifications.catalog import NOTIFICATION_TEMPLATES
from backend.notifications.history_repository import NotificationHistoryRepository
from backend.notifications.producer import CatalogNotificationProducer
from backend.notifications.settings_repository import (
    NotificationSettingsError,
    NotificationSettingsRepository,
)
from backend.notifications.trusted_devices import (
    SmaiUser,
    TrustedDeviceRepository,
)
from backend.users import UserRepository
from ui.last_session import restore_last_session
from ui.notification_ui import render_notification_preferences
from ui.user_data import migrate_legacy_user_data
from ui.user_icon_assets import (
    load_user_icon_assets,
    resolve_user_icon,
    user_icon_browser_source,
)
from ui.watchlist_groups import clear_watchlist_group_transient_state

DEFAULT_NOTIFICATION_USER_ID = "local_user"
DEVICE_QUERY_KEY = "smai_device_id"
DEVICE_NAME_QUERY_KEY = "smai_device_name"
PROFILE_QUERY_KEY = "smai_profile"
START_PROFILE_QUERY_KEY = "smai_start_profile"
ADD_PROFILE_QUERY_KEY = "smai_add_profile"
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
ICON_PAGE_SIZE = 8


def trusted_device_bootstrap_html(
    *,
    icon_public_path: str | None = None,
    display_name: str = "",
    user_id: str = "",
    unread: int = 0,
    notifications_enabled: bool = True,
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
  const notificationsEnabled = {str(notifications_enabled).lower()};
  const decorateUserArea = Boolean(iconUrl || displayName || userId);
  const positionUserMenu = () => {{
    const bodies = window.parent.document.querySelectorAll('[data-testid="stPopoverBody"]');
    const panels = bodies.length
      ? bodies
      : window.parent.document.querySelectorAll('[data-baseweb="popover"]');
    for (const panel of panels) {{
      if (!panel.innerText.includes("ユーザー切替")) continue;
      panel.style.setProperty("position", "fixed", "important");
      panel.style.setProperty("top", "8.4rem", "important");
      panel.style.setProperty("right", "1.25rem", "important");
      panel.style.setProperty("left", "auto", "important");
      panel.style.setProperty("transform", "none", "important");
      panel.style.setProperty("z-index", "2147482999", "important");
      panel.style.setProperty("max-width", "min(22rem, calc(100vw - 2rem))", "important");
    }}
  }};
  const decorate = () => {{
    let found = false;
    for (const button of window.parent.document.querySelectorAll("button")) {{
      if (decorateUserArea && (
        button.innerText.includes("SMAI_USER_AREA")
        || button.classList.contains("smai-user-trigger")
      )) {{
        found = true;
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
        if (notificationsEnabled) button.append(bell);
        button.append(avatar, name, id);
        button.style.setProperty("position", "fixed", "important");
        button.style.setProperty("top", "4.75rem", "important");
        button.style.setProperty("right", "1.25rem", "important");
        button.style.setProperty("z-index", "2147483000", "important");
        if (button.dataset.smaiMenuBound !== "1") {{
          button.dataset.smaiMenuBound = "1";
          button.addEventListener("click", () => {{
            window.setTimeout(positionUserMenu, 0);
            window.setTimeout(positionUserMenu, 80);
            window.setTimeout(positionUserMenu, 220);
          }});
        }}
        const host = button.closest('[data-testid="stPopover"]');
        if (host) {{
          host.style.setProperty("position", "fixed", "important");
          host.style.setProperty("top", "4.75rem", "important");
          host.style.setProperty("right", "1.25rem", "important");
          host.style.setProperty("z-index", "2147483000", "important");
          host.style.setProperty("width", "fit-content", "important");
        }}
      }}
    }}
    if (!window.parent.document.getElementById("smai-user-area-style")) {{
      const style = window.parent.document.createElement("style");
      style.id = "smai-user-area-style";
      style.textContent = `
        .smai-user-trigger {{ position: fixed !important; top: 4.75rem !important;
          right: 1.25rem !important; z-index: 2147483000 !important;
          min-height: 48px; gap: .42rem; border-color: #22d3ee !important;
          background: #08182a !important; box-shadow: 0 8px 24px rgba(0,0,0,.35); }}
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
    const profileLinks = window.parent.document.querySelectorAll(
      ".smai-profile-link[data-user-id]"
    );
    for (const link of profileLinks) {{
      if (link.dataset.smaiBound === "1") continue;
      link.dataset.smaiBound = "1";
      link.addEventListener("click", (event) => {{
        event.preventDefault();
        const selectedId = link.dataset.userId || "";
        const url = new URL(window.parent.location.href);
        url.searchParams.set("{PROFILE_QUERY_KEY}", selectedId);
        url.searchParams.delete("{ADD_PROFILE_QUERY_KEY}");
        window.parent.history.replaceState({{}}, "", url.toString());
        for (const candidateLink of profileLinks) {{
          const isSelected = candidateLink.dataset.userId === selectedId;
          candidateLink.setAttribute("aria-current", isSelected ? "true" : "false");
        }}
        for (const card of window.parent.document.querySelectorAll(
          ".smai-profile-card[data-user-id]"
        )) {{
          const isSelected = card.dataset.userId === selectedId;
          card.classList.toggle("selected", isSelected);
          card.dataset.selected = isSelected ? "true" : "false";
        }}
        const start = window.parent.document.getElementById("smai-profile-start");
        if (start) {{
          const startUrl = new URL(window.parent.location.href);
          startUrl.searchParams.delete("{PROFILE_QUERY_KEY}");
          startUrl.searchParams.set("{START_PROFILE_QUERY_KEY}", selectedId);
          start.href = startUrl.toString();
          start.classList.remove("disabled");
          start.removeAttribute("aria-disabled");
        }}
      }});
    }}
    if (profileLinks.length) found = true;
    const startButton = window.parent.document.getElementById("smai-profile-start");
    if (startButton && startButton.dataset.smaiLoadingBound !== "1") {{
      startButton.dataset.smaiLoadingBound = "1";
      startButton.addEventListener("click", () => {{
        if (startButton.classList.contains("disabled")) return;
        const overlay = window.parent.document.createElement("div");
        overlay.id = "smai-profile-start-loading";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-modal", "true");
        overlay.setAttribute("aria-label", "アプリを準備しています");
        overlay.innerHTML = `
          <div class="smai-profile-start-loading-panel">
            <div class="smai-profile-start-spinner" aria-hidden="true"></div>
            <strong>アプリを準備しています</strong>
            <span>画面が表示されるまで、そのままお待ちください。</span>
          </div>
        `;
        const style = window.parent.document.createElement("style");
        style.id = "smai-profile-start-loading-style";
        style.textContent = `
          #smai-profile-start-loading {{
            position: fixed; inset: 0; z-index: 2147483647; display: grid; place-items: center;
            padding: 1.25rem; background: rgba(2, 8, 23, .78); backdrop-filter: blur(5px);
          }}
          .smai-profile-start-loading-panel {{
            display: grid; justify-items: center; gap: .7rem; width: min(100%, 24rem);
            padding: 1.6rem; border: 1px solid #22d3ee; border-radius: 16px;
            background: #08182a; color: #f8fbff; text-align: center;
            box-shadow: 0 18px 60px rgba(0, 0, 0, .45);
          }}
          .smai-profile-start-loading-panel span {{ color: #a9bfd2; font-size: .92rem; }}
          .smai-profile-start-spinner {{
            width: 2.4rem; height: 2.4rem; border: 3px solid rgba(103, 232, 249, .22);
            border-top-color: #67e8f9; border-radius: 50%;
            animation: smai-profile-start-spin .8s linear infinite;
          }}
          @keyframes smai-profile-start-spin {{ to {{ transform: rotate(360deg); }} }}
        `;
        window.parent.document.head.appendChild(style);
        window.parent.document.body.appendChild(overlay);
      }});
    }}
    positionUserMenu();
    return found;
  }};
  let attempts = 0;
  const timer = window.setInterval(() => {{
    attempts += 1;
    decorate();
    if (attempts >= 40) window.clearInterval(timer);
  }}, 125);
  decorate();
}})();
</script>
"""


def render_user_notification_area() -> bool:
    """Resolve the active user before allowing the main SMAI surface to render."""
    components.html(trusted_device_bootstrap_html(), height=0, width=0)
    try:
        devices = TrustedDeviceRepository()
    except NotificationSettingsError:
        st.warning("ユーザー情報を読み込めませんでした。")
        return False
    users = devices.users()
    migrate_legacy_user_data(
        [candidate.user_id for candidate in users if not candidate.is_system_user]
    )
    restore_last_session(
        cast(MutableMapping[str, Any], st.session_state),
        valid_user_ids={candidate.user_id for candidate in users},
        query_params=getattr(st, "query_params", None),
        restore_selected_user=False,
        restore_active_page=False,
    )
    start_user_id = _query_value(START_PROFILE_QUERY_KEY)
    start_user = next((item for item in users if item.user_id == start_user_id), None)
    if start_user is not None:
        clear_watchlist_group_transient_state()
        st.session_state["smai_current_user_id"] = start_user.user_id
        st.session_state.pop("smai_profile_candidate", None)
        _clear_query_value(START_PROFILE_QUERY_KEY)
        _clear_query_value(PROFILE_QUERY_KEY)
    session_user_id = st.session_state.get("smai_current_user_id")
    user = next((item for item in users if item.user_id == session_user_id), None)
    if user is None:
        if not _query_value("smai_page"):
            st.session_state.pop("sidemenu_page", None)
        user = _select_user(users)
    if user is None:
        return False
    unread, important = 0, 0
    if not user.is_system_user:
        repository = NotificationHistoryRepository()
        try:
            unread = repository.unread_count(user.user_id)
            important = len(repository.list(user.user_id, state="unread", important_only=True))
        except NotificationSettingsError:
            pass
    icon = resolve_user_icon(user.icon_id)
    trigger = (
        f"SMAI_USER_AREA 🔔 {unread} {user.display_name} / {user.user_id}"
        if not user.is_system_user
        else f"SMAI_USER_AREA {user.display_name} / {user.user_id}"
    )
    with st.popover(trigger):
        _render_user_menu(user, unread, important)
    components.html(
        trusted_device_bootstrap_html(
            icon_public_path=user_icon_browser_source(icon),
            display_name=user.display_name,
            user_id=user.user_id,
            unread=unread,
            notifications_enabled=not user.is_system_user,
        ),
        height=0,
        width=0,
    )
    view = str(st.session_state.get(USER_AREA_VIEW_KEY, USER_AREA_HOME))
    if view != USER_AREA_HOME:
        _render_user_area_view(
            view,
            devices,
            user,
        )
        return False
    return True


def _select_user(
    users: list[SmaiUser],
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
        .smai-profile-card:hover,
        div[data-testid="stColumn"]:has(button:hover) .smai-profile-card,
        div[data-testid="stColumn"]:has(button:hover) .smai-add-profile {
          transform: translateY(-4px); border-color: #22d3ee;
          box-shadow: 0 0 28px rgba(34,211,238,.28);
        }
        .smai-profile-card.selected,
        .smai-profile-card[data-selected="true"],
        .smai-profile-link[aria-current="true"] .smai-profile-card {
          transform: translateY(-4px);
          border-color: #22d3ee !important;
          outline: 1px solid rgba(34,211,238,.9);
          outline-offset: 3px;
          box-shadow: 0 0 0 1px rgba(34,211,238,.36),
            0 0 30px rgba(34,211,238,.38), 0 16px 38px rgba(0,0,0,.34) !important;
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
        .smai-profile-link { display: block; color: inherit; text-decoration: none !important; }
        .smai-start-button {
          display: flex; align-items: center; justify-content: center;
          width: min(100%, 260px); min-height: 44px; margin: 1.1rem auto 0;
          border: 1px solid #22d3ee; border-radius: .55rem; background: #0891b2;
          color: #fff !important; font-weight: 800; text-decoration: none !important;
          box-shadow: 0 0 18px rgba(34,211,238,.2);
        }
        .smai-start-button.disabled {
          opacity: .42; pointer-events: none; box-shadow: none;
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
    query_candidate = _query_value(PROFILE_QUERY_KEY)
    selected_user_id = (
        query_candidate
        if any(candidate.user_id == query_candidate for candidate in users)
        else str(st.session_state.get("smai_profile_candidate", ""))
    )
    if selected_user_id:
        st.session_state["smai_profile_candidate"] = selected_user_id
    card_count = len(users) + 1
    column_count = min(5, card_count)
    columns = st.columns(column_count, gap="medium")
    for index, candidate in enumerate(users):
        icon = resolve_user_icon(candidate.icon_id)
        selected_class = " selected" if candidate.user_id == selected_user_id else ""
        selected_value = "true" if candidate.user_id == selected_user_id else "false"
        source = user_icon_browser_source(icon)
        with columns[index % column_count]:
            if source:
                st.markdown(
                    f'<a class="smai-profile-link" href="?{PROFILE_QUERY_KEY}='
                    f'{html.escape(candidate.user_id)}" target="_self" '
                    f'data-user-id="{html.escape(candidate.user_id)}" '
                    f'aria-current="{selected_value}" '
                    f'aria-label="{html.escape(candidate.display_name)}を選択">'
                    f'<div class="smai-profile-card{selected_class}" '
                    f'data-user-id="{html.escape(candidate.user_id)}" '
                    f'data-selected="{selected_value}">'
                    f'<img src="{html.escape(source)}" alt="">'
                    f'<div class="smai-profile-name">{html.escape(candidate.display_name)}</div>'
                    "</div></a>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="smai-profile-card{selected_class}" '
                    f'data-user-id="{html.escape(candidate.user_id)}" '
                    f'data-selected="{selected_value}">'
                    '<div class="smai-add-profile" aria-label="ユーザーアイコン"></div>'
                    f'<div class="smai-profile-name">{html.escape(candidate.display_name)}</div>'
                    "</div>",
                    unsafe_allow_html=True,
                )
    with columns[len(users) % column_count]:
        st.markdown(
            f'<a class="smai-profile-link" href="?{ADD_PROFILE_QUERY_KEY}=1" '
            'target="_self" aria-label="ユーザー追加">'
            '<div class="smai-add-profile" aria-hidden="true">＋</div>'
            '<div class="smai-profile-name">ユーザー追加</div></a>',
            unsafe_allow_html=True,
        )
    if _query_value(ADD_PROFILE_QUERY_KEY) == "1":
        _render_add_user_form()

    selected = next((item for item in users if item.user_id == selected_user_id), None)
    start_href = (
        f"?{START_PROFILE_QUERY_KEY}={html.escape(selected.user_id)}"
        if selected is not None
        else "#"
    )
    disabled_class = "" if selected is not None else " disabled"
    disabled_attr = "" if selected is not None else ' aria-disabled="true"'
    st.markdown(
        f'<a id="smai-profile-start" class="smai-start-button{disabled_class}" '
        f'href="{start_href}" target="_self"{disabled_attr}>このユーザーで開始</a>',
        unsafe_allow_html=True,
    )
    session_user = st.session_state.get("smai_current_user_id")
    return next((user for user in users if user.user_id == session_user), None)


def _render_add_user_form() -> None:
    st.subheader("ユーザーを追加")
    st.caption("この端末内で使うローカルプロフィールを作成します。ログイン認証ではありません。")
    icons = load_user_icon_assets()
    icon_ids = [asset.icon_id for asset in icons] or ["smai_navi_default"]
    icon_labels = {asset.icon_id: asset.display_name for asset in icons}
    with st.form("smai_add_user_form", clear_on_submit=False):
        display_name = st.text_input(
            "表示名",
            max_chars=32,
            placeholder="例: Haru",
        )
        icon_id = st.selectbox(
            "アイコン",
            icon_ids,
            format_func=lambda value: icon_labels.get(value, "SMAIデフォルト"),
        )
        create_col, cancel_col = st.columns(2)
        create = create_col.form_submit_button(
            "作成して開始",
            type="primary",
            use_container_width=True,
        )
        cancel = cancel_col.form_submit_button("キャンセル", use_container_width=True)
    if cancel:
        _clear_query_value(ADD_PROFILE_QUERY_KEY)
        st.rerun()
    if not create:
        return
    try:
        user = UserRepository().create_user(display_name, icon_id)
    except (ValueError, RuntimeError, NotificationSettingsError) as exc:
        st.error(str(exc))
        return
    clear_watchlist_group_transient_state()
    st.session_state["smai_current_user_id"] = user.user_id
    st.session_state.pop("smai_profile_candidate", None)
    _clear_query_value(ADD_PROFILE_QUERY_KEY)
    st.rerun()


def _render_notification_center(repository: NotificationHistoryRepository, user: SmaiUser) -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none !important; }
        .block-container { max-width: 1320px !important; padding-inline: 1.25rem !important; }
        .smai-notification-summary { border: 1px solid #24415f; border-radius: 14px;
          padding: 1rem 1.15rem; background: #0b1b30; }
        .smai-notification-summary strong { color: #f4fbff; font-size: 1.8rem; }
        .smai-notification-row { display: grid; grid-template-columns: 72px 1fr auto;
          gap: 1rem; align-items: center; border: 1px solid #24415f; border-radius: 12px;
          padding: .75rem 1rem; margin: .55rem 0; background: #08172a; }
        .smai-notification-row.unread { border-left: 4px solid #22d3ee;
          box-shadow: 0 0 18px rgba(34,211,238,.12); }
        .smai-notification-row.high { border-color: #d97706; }
        .smai-notification-row.critical { border-color: #ef4444; }
        .smai-notification-row img { width: 64px; height: 64px; object-fit: cover;
          border-radius: 12px; }
        .smai-notification-badges { display: flex; gap: .4rem; flex-wrap: wrap; }
        .smai-notification-badge { border: 1px solid #27728a; border-radius: 6px;
          padding: .12rem .45rem; color: #8ee8fa; font-size: .78rem; }
        .smai-notification-time { color: #9db0c5; white-space: nowrap; }
        @media (max-width: 767px) {
          .smai-notification-row { grid-template-columns: 52px 1fr; }
          .smai-notification-row img { width: 48px; height: 48px; }
          .smai-notification-time { grid-column: 2; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if st.button("← SMAIホームへ戻る", key="notification_center_back"):
        st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
        st.rerun()
    st.title("通知センター")
    st.caption("受け取った通知を確認し、関連画面で詳しい材料を確認できます。")
    counts = repository.counts(user.user_id)
    summary_values = (
        ("未読", counts["unread"]),
        ("既読", counts["read"]),
        ("今日の通知", counts["today"]),
        ("今週の通知", counts["week"]),
    )
    for column, (label, value) in zip(st.columns(4), summary_values):
        column.markdown(
            f'<div class="smai-notification-summary">{html.escape(label)}<br>'
            f"<strong>{value}件</strong></div>",
            unsafe_allow_html=True,
        )
    filter_col, state_col, period_col, sort_col = st.columns(4)
    category = filter_col.selectbox(
        "通知の種類",
        list(CATEGORY_LABELS),
        format_func=lambda value: CATEGORY_LABELS[value],
        key="notification_center_category",
    )
    state = state_col.selectbox(
        "状態",
        ["すべて", "unread", "read", "archived"],
        format_func=lambda value: {
            "すべて": "すべて",
            "unread": "未読",
            "read": "既読",
            "archived": "アーカイブ",
        }[value],
        key="notification_center_state",
    )
    period = period_col.selectbox(
        "期間", [1, 7, 30], format_func=lambda value: {1: "今日", 7: "今週", 30: "30日"}[value]
    )
    sort_order = sort_col.selectbox(
        "並び替え",
        ["new", "old", "severity"],
        format_func=lambda value: {"new": "新しい順", "old": "古い順", "severity": "重要度順"}[
            value
        ],
    )
    try:
        items = repository.list(
            user.user_id,
            state=None if state == "すべて" else state,
            category=None if category == "すべて" else category,
            days=period,
        )
    except NotificationSettingsError:
        st.error("通知を読み込めませんでした。")
        return
    if not items:
        st.info("該当する通知はありません。")
    if sort_order == "old":
        items.reverse()
    elif sort_order == "severity":
        priority = {"critical": 0, "high": 1, "medium": 2, "low": 3, "silent": 4}
        items.sort(key=lambda item: (priority.get(item.severity, 9), -item.created_at.timestamp()))
    for item in items:
        notification_icon = resolve_user_icon(str((item.metadata or {}).get("icon_asset_id", "")))
        notification_icon_source = user_icon_browser_source(notification_icon)
        icon_html = (
            f'<img class="smai-notification-asset" src="{html.escape(notification_icon_source)}" '
            'alt="">'
            if notification_icon_source
            else ""
        )
        age = _relative_notification_time(item.created_at)
        st.markdown(
            f'<div class="smai-notification-row {html.escape(item.state)} '
            f'{html.escape(item.severity)}">{icon_html}<div>'
            f'<div class="smai-notification-badges"><span class="smai-notification-badge">'
            f"{html.escape(CATEGORY_LABELS.get(item.presentation_category, item.presentation_category))}"
            f'</span><span class="smai-notification-badge">{html.escape(item.severity.title())}</span>'
            f"</div><strong>{html.escape(item.title)}</strong><br>"
            f'{html.escape(item.summary)}</div><div class="smai-notification-time">{age}</div></div>',
            unsafe_allow_html=True,
        )
        read_col, archive_col, cta_col = st.columns([1, 1, 3])
        if item.state == "unread" and read_col.button(
            "既読", key=f"notification_read_{item.event_id}"
        ):
            repository.mark_read(user.user_id, item.event_id)
            st.rerun()
        if archive_col.button("アーカイブ", key=f"notification_archive_{item.event_id}"):
            repository.archive(user.user_id, item.event_id)
            st.rerun()
        if item.action_url and item.action_url.startswith(("/", "?")):
            cta_col.link_button("関連画面で確認", item.action_url)
        metadata = item.metadata or {}
        with st.expander("通知の詳細", expanded=False):
            for label, key in (
                ("何が起きたか", "what_happened"),
                ("なぜ確認したいか", "why_it_matters"),
                ("SMAIの見方", "smai_assessment"),
                ("次に見ること", "next_check"),
            ):
                if metadata.get(key):
                    st.markdown(f"**{label}**  \n{metadata[key]}")
    if os.getenv("SMAI_NOTIFICATION_DEBUG") == "1":
        _render_notification_catalog(repository, user)


def _render_notification_catalog(repository: NotificationHistoryRepository, user: SmaiUser) -> None:
    st.divider()
    st.subheader("通知カタログ（開発用）")
    producer = CatalogNotificationProducer(
        repository,
        NotificationSettingsRepository(str(repository.database_path)),
    )
    for template in NOTIFICATION_TEMPLATES:
        with st.expander(f"{template.display_name} / {template.template_id}"):
            st.caption(
                f"{template.presentation_category} / {template.default_severity} / "
                f"{template.icon_asset_id} / {template.default_schedule or 'event'}"
            )
            st.markdown(f"**{template.title_template}**")
            st.write(template.summary_template.format_map(template.sample_data))
            st.code(
                f"SMAI\n{template.title_template}\n"
                f"{template.summary_template.format_map(template.sample_data)}",
                language=None,
            )
            if st.button(
                "このサンプル通知を生成",
                key=f"manual_notification_{template.template_id}",
            ):
                producer.produce(
                    template.template_id,
                    user_id=user.user_id,
                    dedupe_key=f"manual:{template.template_id}:{datetime.now(UTC).isoformat()}",
                )
                st.rerun()


def _relative_notification_time(created_at: datetime) -> str:
    elapsed = datetime.now(UTC) - created_at.astimezone(UTC)
    seconds = max(0, int(elapsed.total_seconds()))
    if seconds < 60:
        return "たった今"
    if seconds < 3600:
        return f"{seconds // 60}分前"
    if seconds < 86400:
        return f"{seconds // 3600}時間前"
    return f"{seconds // 86400}日前"


def _render_user_menu(user: SmaiUser, unread: int, important: int) -> None:
    st.markdown(f"**{user.display_name}**")
    st.caption(f"{user.user_id}　未読 {unread}件 / 重要 {important}件")
    links = (
        (("ユーザー切替", "switch_user"),)
        if user.is_system_user
        else (
            ("通知センター", "notification_center"),
            ("ユーザー設定", "user_settings"),
            ("通知設定", "notification_settings"),
            ("ユーザー切替", "switch_user"),
        )
    )
    for label, view in links:
        if st.button(label, key=f"open_user_area_{view}", use_container_width=True):
            st.session_state[USER_AREA_VIEW_KEY] = view
            st.rerun()


def _render_user_area_view(
    view: str,
    user_repository: TrustedDeviceRepository,
    user: SmaiUser,
) -> None:
    if user.is_system_user and view in {
        "notification_center",
        "user_settings",
        "notification_settings",
        "icon_settings",
    }:
        st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
        st.rerun()
    st.markdown(
        """
        <style>
        .block-container { max-width: 1120px; }
        .smai-user-view-title { margin-bottom: 1.25rem; }
        div[data-testid="stHorizontalBlock"]:has(.smai-notification-settings-marker) {
          justify-content: center;
        }
        div[data-testid="stColumn"]:has(.smai-notification-settings-marker) {
          flex: 0 1 880px !important; max-width: 880px !important;
        }
        @media (max-width: 767px) {
          .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    if view == "notification_center":
        _render_notification_center(NotificationHistoryRepository(), user)
    elif view == "notification_settings":
        _, notification_col, _ = st.columns([1, 5, 1])
        with notification_col:
            st.markdown(
                '<span class="smai-notification-settings-marker"></span>',
                unsafe_allow_html=True,
            )
            st.title("通知設定")
            st.caption("受け取る通知、通知方法、通知条件をユーザーごとに設定します。")
            action = render_notification_preferences(user.user_id)
            if action in {"saved", "cancelled"}:
                st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
                st.rerun()
    elif view == "user_settings":
        _render_user_settings(user_repository, user)
    elif view == "icon_settings":
        _render_icon_settings(user_repository, user)
    elif view == "switch_user":
        clear_watchlist_group_transient_state()
        st.session_state.pop("smai_current_user_id", None)
        st.session_state.pop("smai_profile_candidate", None)
        st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
        _clear_query_value(PROFILE_QUERY_KEY)
        st.rerun()
    else:
        st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
        st.rerun()


def _render_user_settings(repository: TrustedDeviceRepository, user: SmaiUser) -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"]:has(.smai-user-settings-marker) {
          justify-content: center;
        }
        div[data-testid="stColumn"]:has(.smai-user-settings-marker) {
          flex: 0 1 760px !important; max-width: 760px !important;
        }
        div[data-testid="stColumn"]:has(.smai-user-settings-marker) [data-testid="stImage"] img {
          width: 128px; height: 128px; object-fit: cover; border-radius: 16px;
          border: 1px solid #22d3ee;
        }
        div[data-testid="stColumn"]:has(.smai-user-settings-marker)
          div[data-testid="stButton"] > button {
          width: min(100%, 220px);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, settings_col, _ = st.columns([1, 4, 1])
    with settings_col:
        st.markdown(
            '<span class="smai-user-settings-marker"></span>',
            unsafe_allow_html=True,
        )
        st.title("ユーザー設定")
        st.caption("選択中ユーザーのプロフィールを編集します。")
        icon_col, action_col = st.columns([0.22, 0.78], gap="small", vertical_alignment="center")
        current_icon = resolve_user_icon(user.icon_id)
        with icon_col:
            if current_icon.file_path is not None:
                st.image(str(current_icon.file_path), width=128)
        with action_col:
            st.markdown("**選択中のアイコン**")
            if st.button("アイコンを変更", key="user_settings_open_icons"):
                st.session_state["smai_icon_candidate"] = user.icon_id
                st.session_state[USER_AREA_VIEW_KEY] = "icon_settings"
                st.rerun()

        display_name = st.text_input(
            "表示名", value=user.display_name, disabled=user.is_system_user
        )
        st.text_input("user_id", value=user.user_id, disabled=True)
        if user.is_system_user:
            st.info("SMAIデフォルトはシステム標準ユーザーのため、名称変更できません。")

        save_col, cancel_col = st.columns(2)
        save_clicked = save_col.button(
            "ユーザー設定を保存", key="save_smai_user_settings", type="primary"
        )
        cancel_clicked = cancel_col.button("キャンセル", key="cancel_smai_user_settings")
        if save_clicked:
            if not user.is_system_user and not display_name.strip():
                st.warning("表示名を入力してください。")
            elif not user.is_system_user:
                repository.set_display_name(user.user_id, display_name)
                st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
                st.rerun()
            else:
                st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
                st.rerun()
        if cancel_clicked:
            st.session_state[USER_AREA_VIEW_KEY] = USER_AREA_HOME
            st.rerun()


def _render_icon_settings(repository: TrustedDeviceRepository, user: SmaiUser) -> None:
    st.title("アイコン変更")
    assets = load_user_icon_assets()
    if not assets:
        st.info("選択可能なアイコンAssetはありません。")
        return
    valid_icon_ids = {asset.icon_id for asset in assets}
    candidate = str(st.session_state.get("smai_icon_candidate", user.icon_id))
    selected_icon = candidate if candidate in valid_icon_ids else user.icon_id
    visible_count = int(st.session_state.get("smai_icon_visible_count", ICON_PAGE_SIZE))
    visible_assets = assets[: max(ICON_PAGE_SIZE, visible_count)]
    st.markdown(
        """
        <style>
        div[data-testid="stColumn"]:has(.smai-icon-card) { position: relative; }
        .smai-icon-card { width: min(100%, 200px); margin: 0 auto; padding: .65rem;
          border: 2px solid #24415f; border-radius: 14px;
          background: #0a192b; transition: border-color .18s ease, box-shadow .18s ease; }
        .smai-icon-card:hover, .smai-icon-card.selected { border-color: #22d3ee;
          box-shadow: 0 0 24px rgba(34,211,238,.28); }
        .smai-icon-card img { width: 100%; aspect-ratio: 1; object-fit: cover;
          border-radius: 10px; display: block; }
        .smai-icon-label { margin-top: .45rem; text-align: center; font-weight: 700; }
        div[data-testid="stColumn"]:has(.smai-icon-card) [data-testid="stButton"] {
          position: absolute; inset: 0; z-index: 2;
        }
        div[data-testid="stColumn"]:has(.smai-icon-card) [data-testid="stButton"] > button {
          width: 100%; height: 100%; opacity: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _, grid_col, _ = st.columns([1, 10, 1])
    with grid_col:
        for row_start in range(0, len(visible_assets), 4):
            columns = st.columns(4)
            for column, asset in zip(columns, visible_assets[row_start : row_start + 4]):
                with column:
                    source = user_icon_browser_source(resolve_user_icon(asset.icon_id))
                    if source is None:
                        continue
                    selected_class = " selected" if asset.icon_id == selected_icon else ""
                    st.markdown(
                        f'<div class="smai-icon-card{selected_class}">'
                        f'<img src="{html.escape(source)}" alt="">'
                        f'<div class="smai-icon-label">{html.escape(asset.display_name)}</div>'
                        "</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        f"{asset.display_name}を選択",
                        key=f"select_smai_icon_{asset.icon_id}",
                    ):
                        st.session_state["smai_icon_candidate"] = asset.icon_id
                        st.rerun()
        if len(visible_assets) < len(assets):
            if st.button(
                f"もっと見る（残り {len(assets) - len(visible_assets)} 件）",
                key="show_more_smai_icons",
                use_container_width=True,
            ):
                st.session_state["smai_icon_visible_count"] = visible_count + ICON_PAGE_SIZE
                st.rerun()
    components.html(_icon_button_overlay_html(), height=0, width=0)

    _, actions_col, _ = st.columns([1, 2, 1])
    with actions_col:
        save_col, cancel_col = st.columns(2)
        save_clicked = save_col.button("アイコンを保存", key="save_smai_user_icon", type="primary")
        cancel_clicked = cancel_col.button("キャンセル", key="cancel_smai_user_icon")
        if save_clicked:
            try:
                with st.spinner("アイコンを保存しています…"):
                    repository.set_icon(user.user_id, selected_icon)
            except (OSError, ValueError, RuntimeError, NotificationSettingsError) as exc:
                st.error(f"アイコンを保存できませんでした。現在の設定を維持します: {exc}")
                return
            st.session_state.pop("smai_icon_candidate", None)
            st.session_state.pop("smai_icon_visible_count", None)
            st.session_state[USER_AREA_VIEW_KEY] = "user_settings"
            st.rerun()
        if cancel_clicked:
            st.session_state.pop("smai_icon_candidate", None)
            st.session_state.pop("smai_icon_visible_count", None)
            st.session_state[USER_AREA_VIEW_KEY] = "user_settings"
            st.rerun()


def _icon_button_overlay_html() -> str:
    return """
<script>
(() => {
  const bind = () => {
    const cards = window.parent.document.querySelectorAll(".smai-icon-card");
    for (const card of cards) {
      const column = card.closest('[data-testid="stColumn"]');
      const button = column?.querySelector('[data-testid="stButton"] > button');
      const buttonHost = button?.closest('[data-testid="stButton"]');
      if (!column || !button || !buttonHost) continue;
      column.style.position = "relative";
      buttonHost.style.position = "absolute";
      buttonHost.style.top = `${card.offsetTop}px`;
      buttonHost.style.left = `${card.offsetLeft}px`;
      buttonHost.style.width = `${card.offsetWidth}px`;
      buttonHost.style.height = `${card.offsetHeight}px`;
      buttonHost.style.zIndex = "3";
      button.style.width = "100%";
      button.style.height = "100%";
      button.style.opacity = "0";
      button.style.cursor = "pointer";
      button.setAttribute("aria-label", card.innerText.trim() + "を選択");
    }
    return cards.length > 0;
  };
  let attempts = 0;
  const timer = window.setInterval(() => {
    attempts += 1;
    if (bind() || attempts >= 40) window.clearInterval(timer);
  }, 125);
  bind();
})();
</script>
"""


def _query_value(key: str) -> str:
    params = getattr(st, "query_params", {})
    value = params.get(key, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def _clear_query_value(key: str) -> None:
    params = getattr(st, "query_params", None)
    if params is not None and key in params:
        del params[key]
