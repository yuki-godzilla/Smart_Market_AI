from pathlib import Path

from ui.notification_center import MASCOTS, trusted_device_bootstrap_html


def test_user_area_is_fixed_responsive_and_not_in_side_menu() -> None:
    html = trusted_device_bootstrap_html()
    source = Path("ui/notification_center.py").read_text(encoding="utf-8")
    sidemenu = Path("ui/components/sidemenu.py").read_text(encoding="utf-8")

    assert 'host.style.position = "fixed"' in html
    assert "@media (max-width: 767px)" in html
    assert "smai-user-detail" in html
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
    assert len(MASCOTS) >= 8
