from __future__ import annotations

import threading
import time

from ui.ranking_jobs import get_ranking_job, start_ranking_job


def _wait_for_terminal(cache_key: str, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = get_ranking_job(cache_key)
        if job is not None and job.status != "running":
            return job
        time.sleep(0.01)
    raise AssertionError("ranking job did not finish")


def test_ranking_job_completes_independently_from_the_starting_caller():
    release = threading.Event()

    def worker(progress):
        progress("ファンダメンタル情報を取得しています。", 0.31)
        release.wait(timeout=1)
        return [{"symbol": "7203.T"}], []

    started = start_ranking_job("ranking-job-complete", worker)
    running = get_ranking_job("ranking-job-complete")

    assert started.status == "running"
    assert running is not None
    assert running.message == "ファンダメンタル情報を取得しています。"
    assert running.ratio == 0.31

    release.set()
    completed = _wait_for_terminal("ranking-job-complete")
    assert completed.status == "completed"
    assert completed.rows == [{"symbol": "7203.T"}]


def test_ranking_job_reuses_the_same_running_job_for_reconnecting_clients():
    release = threading.Event()

    def worker(_progress):
        release.wait(timeout=1)
        return [], []

    first = start_ranking_job("ranking-job-reconnect", worker)
    second = start_ranking_job("ranking-job-reconnect", worker)

    assert second.job_id == first.job_id
    release.set()
    assert _wait_for_terminal("ranking-job-reconnect").status == "completed"


def test_ranking_job_records_sanitized_failure_type(caplog):
    def worker(_progress):
        raise ValueError("provider response included unsafe raw details")

    start_ranking_job("ranking-job-failure", worker)
    failed = _wait_for_terminal("ranking-job-failure")

    assert failed.status == "failed"
    assert failed.error_type == "ValueError"
    assert "unsafe raw details" not in failed.message
    assert "error_type=ValueError" in caplog.text
    assert "unsafe raw details" not in caplog.text
