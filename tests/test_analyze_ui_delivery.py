from scripts.analyze_ui_delivery import analyze_paths, static_asset_metrics, write_report


def test_delivery_analysis_finds_no_assistant_data_uri_download_links() -> None:
    metrics = analyze_paths(("ui/views/copilot.py",))
    assert metrics.files == 1
    assert metrics.data_uri_links == 0
    assert metrics.session_state_references > 0


def test_delivery_report_includes_static_asset_baseline() -> None:
    count, size = static_asset_metrics()
    path = write_report()
    text = path.read_text(encoding="utf-8")
    assert count >= 20
    assert size > 0
    assert "SMAIアシスタント" in text
