from pathlib import Path


def test_external_access_guide_covers_six_environments_and_pwa_artifacts() -> None:
    text = Path("docs/EXTERNAL_ACCESS_STABILITY.md").read_text(encoding="utf-8")
    for phrase in (
        "LAN / Windows Chrome",
        "Tailscale / Windows Chrome",
        "Tailscale / iPhone Safari",
        "Tailscale / iPad Safari",
        "Tailscale / iPhone PWA",
        "Tailscale / iPad PWA",
        "JSON",
        "CSV",
        "Markdown",
        "PDF",
        "ZIP",
        "Network",
        "Console",
    ):
        assert phrase in text


def test_lan_pwa_guide_points_to_diagnostics_and_detailed_checklist() -> None:
    text = Path("docs/LAN_PWA_ACCESS_GUIDE.md").read_text(encoding="utf-8")
    assert "外部接続診断" in text
    assert "EXTERNAL_ACCESS_STABILITY.md" in text
    assert "Quick Look" in text
