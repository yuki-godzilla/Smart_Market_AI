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
