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


def test_notification_cta_is_navigation_only_and_mascots_are_selectable() -> None:
    source = Path("ui/notification_center.py").read_text(encoding="utf-8")

    assert "st.link_button" in source
    assert "update_research" not in source
    assert "create_decision_report" not in source
    assets = load_user_icon_assets()
    assert [asset.icon_id for asset in assets] == ["smai_default"]
    assert assets[0].file_path.is_file()
    assert resolve_user_icon("missing").icon_id == "smai_default"
    assert "🐱" not in source
    assert "🐶" not in source
