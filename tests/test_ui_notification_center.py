from pathlib import Path

from ui.notification_center import _icon_button_overlay_html, trusted_device_bootstrap_html
from ui.user_icon_assets import load_user_icon_assets, resolve_user_icon


def test_user_area_is_fixed_responsive_and_not_in_side_menu() -> None:
    html = trusted_device_bootstrap_html()
    source = Path("ui/notification_center.py").read_text(encoding="utf-8")
    sidemenu = Path("ui/components/sidemenu.py").read_text(encoding="utf-8")

    assert 'host.style.setProperty("position", "fixed", "important")' in html
    assert 'button.style.setProperty("position", "fixed", "important")' in html
    assert '"top", "4.75rem", "important"' in html
    assert '"top", "8.4rem", "important"' in html
    assert "positionUserMenu" in html
    assert "window.setInterval" in html
    assert "@media (max-width: 767px)" in html
    assert "smai-user-name" in html
    assert "smai-user-id" in html
    assert "smai-user-avatar" in html
    assert "通知センター" in source
    assert "重要のみ" in source
    assert '"重要度"' in source
    assert "アーカイブ" in source
    assert "通知センター" not in sidemenu
    menu_source = source.split("def _render_user_menu", 1)[1].split(
        "def _render_user_area_view", 1
    )[0]
    assert "通知カード" not in menu_source
    assert "_render_notification_center" not in menu_source
    assert "selectbox" not in menu_source
    assert "expander" not in menu_source
    assert '("ユーザー設定", "user_settings")' in menu_source
    assert '("通知設定", "notification_settings")' in menu_source
    assert '("ユーザー切替", "switch_user")' in menu_source
    assert "if user.is_system_user" in menu_source
    assert "通知センター" not in menu_source
    assert "アイコン変更" not in menu_source
    assert "登録済み端末" not in menu_source
    assert "render_notification_preferences(user.user_id)" in source
    assert "render_notification_destination" not in source
    assert "smai-notification-settings-marker" in source
    assert "flex: 0 1 880px" in source


def test_notification_cta_is_navigation_only_and_icon_assets_are_selectable() -> None:
    source = Path("ui/notification_center.py").read_text(encoding="utf-8")

    assert "st.link_button" in source
    assert "update_research" not in source
    assert "create_decision_report" not in source
    assets = load_user_icon_assets()
    assert len(assets) == 12
    assert assets[0].icon_id == "smai_navi_default"
    assert all(asset.file_path.is_file() for asset in assets)
    assert resolve_user_icon("missing").icon_id == "smai_navi_default"
    assert "🐱" not in source
    assert "🐶" not in source
    overlay = _icon_button_overlay_html()
    assert "smai-icon-card" in overlay
    assert 'button.style.opacity = "0"' in overlay
    assert 'button.style.cursor = "pointer"' in overlay


def test_user_selection_gates_main_app_and_hides_sidebar() -> None:
    source = Path("ui/notification_center.py").read_text(encoding="utf-8")
    notification_source = Path("ui/notification_ui.py").read_text(encoding="utf-8")
    app_source = Path("ui/app.py").read_text(encoding="utf-8")

    assert "どのユーザーで使いますか？" in source
    assert '[data-testid="stSidebar"]' in source
    assert "smai-profile-gate-title" in source
    assert "ユーザー追加" in source
    assert "SMAIデフォルト" in Path("backend/notifications/settings_repository.py").read_text(
        encoding="utf-8"
    )
    assert "max-width: 960px" in source
    assert "smai-profile-start" in source
    assert "history.replaceState" in source
    assert "START_PROFILE_QUERY_KEY" in source
    assert "remember_device_user" not in source
    assert 'class="smai-profile-link"' in source
    assert "select_profile_" not in source
    assert "smai_icon_candidate" in source
    assert "select_smai_icon_" in source
    assert ":has(.smai-icon-card)" in source
    assert 'st.container(key="' not in source
    assert "アイコンを保存" in source
    assert "キャンセル" in source
    assert "ユーザー設定を保存" in source
    assert "flex: 0 1 760px" in source
    assert "[0.22, 0.78]" in source
    assert 'USER_AREA_VIEW_KEY] = "user_settings"' in source
    assert "← SMAIに戻る" not in source
    assert '"通知設定を保存"' in notification_source
    assert '"キャンセル"' in notification_source
    assert '"1. 通知の種類"' in notification_source
    assert '"2. 通知方法"' in notification_source
    assert '"3. 通知条件"' in notification_source
    assert "app_enabled=app_enabled" in notification_source
    assert "enabled_categories=selected_categories" in notification_source
    assert 'return "saved"' in notification_source
    assert 'return "cancelled"' in notification_source
    assert app_source.index("if not render_user_notification_area():") < app_source.index(
        "selected_page = render_sidemenu"
    )
