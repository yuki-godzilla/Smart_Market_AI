from pathlib import Path

from ui.notification_center import trusted_device_bootstrap_html
from ui.user_icon_assets import load_user_icon_assets, resolve_user_icon


def test_user_area_is_fixed_responsive_and_not_in_side_menu() -> None:
    html = trusted_device_bootstrap_html()
    source = Path("ui/notification_center.py").read_text(encoding="utf-8")
    sidemenu = Path("ui/components/sidemenu.py").read_text(encoding="utf-8")

    assert 'host.style.position = "fixed"' in html
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


def test_user_selection_gates_main_app_and_hides_sidebar() -> None:
    source = Path("ui/notification_center.py").read_text(encoding="utf-8")
    app_source = Path("ui/app.py").read_text(encoding="utf-8")

    assert "どのユーザーで使いますか？" in source
    assert '[data-testid="stSidebar"]' in source
    assert "smai-profile-gate-title" in source
    assert "ユーザー追加" in source
    assert "SMAIデフォルト" in Path("backend/notifications/settings_repository.py").read_text(
        encoding="utf-8"
    )
    assert "max-width: 960px" in source
    assert '"このユーザーで開始"' in source
    assert app_source.index("if not render_user_notification_area():") < app_source.index(
        "selected_page = render_sidemenu"
    )
