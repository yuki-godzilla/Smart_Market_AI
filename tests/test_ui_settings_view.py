from datetime import time
from pathlib import Path

from ui.notification_ui import _time_value
from ui.views.settings import (
    _external_fetch_source_rows,
    _external_fetch_summary_caption,
    _external_fetch_summary_overview_rows,
)


def test_external_fetch_summary_helpers_shape_source_rows():
    summary = {
        "performance_profile": "workstation",
        "symbol": "7203.T",
        "elapsed_ms": 8200,
        "success_count": 4,
        "failed_count": 1,
        "timeout_count": 0,
        "no_result_count": 1,
        "cache_hit_count": 0,
        "sources": [
            {
                "source": "news",
                "provider": "google_news_rss",
                "status": "success",
                "elapsed_ms": 2800,
                "retry_attempts": 1,
                "result_count": 5,
                "error_message_short": "",
            }
        ],
    }

    caption = _external_fetch_summary_caption(summary)
    overview_rows = _external_fetch_summary_overview_rows(summary)
    source_rows = _external_fetch_source_rows(summary)

    assert "profile=workstation" in caption
    assert "elapsed=8.2s" in caption
    assert all(row["field"] != "sources" for row in overview_rows)
    assert source_rows == [
        {
            "source": "news",
            "provider": "google_news_rss",
            "status": "success",
            "elapsed_ms": "2800",
            "results": "5",
            "retry": "1",
            "error": "",
        }
    ]


def test_notification_ui_keeps_topic_secret_and_sends_only_in_button_branch():
    source = Path("ui/notification_ui.py").read_text(encoding="utf-8")

    assert 'type="password"' in source
    assert "完全な暗号化秘匿ではありません" in source
    assert "if test_clicked:" in source
    assert source.index("if test_clicked:") < source.index(
        "result = send_saved_test_notification(current)"
    )
    assert "render_notification_settings()" in Path("ui/views/settings.py").read_text(
        encoding="utf-8"
    )


def test_notification_quiet_time_helper_uses_safe_fallback():
    assert _time_value("22:30", time(0, 0)) == time(22, 30)
    assert _time_value("broken", time(7, 0)) == time(7, 0)
