from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RankingJobStatus = Literal["running", "completed", "failed"]
RankingRows = tuple[list[dict[str, str]], list[dict[str, str]]]
RankingProgressCallback = Callable[[str, float], None]
RankingWorker = Callable[[RankingProgressCallback], RankingRows]

MAX_RANKING_JOBS = 8
RANKING_JOB_TTL_SECONDS = 2 * 60 * 60
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RankingJobSnapshot:
    job_id: str
    cache_key: str
    status: RankingJobStatus
    message: str
    ratio: float
    rows: list[dict[str, str]]
    error_rows: list[dict[str, str]]
    error_type: str
    started_at: float
    updated_at: float


@dataclass
class _RankingJob:
    job_id: str
    cache_key: str
    status: RankingJobStatus
    message: str
    ratio: float
    rows: list[dict[str, str]]
    error_rows: list[dict[str, str]]
    error_type: str
    started_at: float
    updated_at: float


_LOCK = threading.RLock()
_JOBS: dict[str, _RankingJob] = {}


def start_ranking_job(cache_key: str, worker: RankingWorker) -> RankingJobSnapshot:
    """Start one process-wide ranking worker, or reuse the active job.

    The worker owns no Streamlit state. This lets a mobile browser disconnect,
    reconnect, or rerun without cancelling the ranking calculation.
    """

    now = time.monotonic()
    with _LOCK:
        _prune_jobs(now)
        existing = _JOBS.get(cache_key)
        if existing is not None and existing.status == "running":
            return _snapshot(existing)
        job = _RankingJob(
            job_id=uuid.uuid4().hex,
            cache_key=cache_key,
            status="running",
            message="ランキング対象と取得条件を確認しています。",
            ratio=0.0,
            rows=[],
            error_rows=[],
            error_type="",
            started_at=now,
            updated_at=now,
        )
        _JOBS[cache_key] = job
        _enforce_job_limit()
        started_snapshot = _snapshot(job)
    thread = threading.Thread(
        target=_run_ranking_job,
        args=(job.job_id, cache_key, worker),
        name=f"smai-ranking-{job.job_id[:8]}",
        daemon=True,
    )
    thread.start()
    return started_snapshot


def get_ranking_job(cache_key: str) -> RankingJobSnapshot | None:
    with _LOCK:
        _prune_jobs(time.monotonic())
        job = _JOBS.get(cache_key)
        return _snapshot(job) if job is not None else None


def ranking_job_is_running(cache_key: str) -> bool:
    job = get_ranking_job(cache_key)
    return job is not None and job.status == "running"


def clear_ranking_job(cache_key: str) -> None:
    """Clear only terminal state; a running calculation is never orphaned."""

    with _LOCK:
        job = _JOBS.get(cache_key)
        if job is not None and job.status != "running":
            _JOBS.pop(cache_key, None)


def _run_ranking_job(job_id: str, cache_key: str, worker: RankingWorker) -> None:
    def report(message: str, ratio: float) -> None:
        with _LOCK:
            job = _JOBS.get(cache_key)
            if job is None or job.job_id != job_id or job.status != "running":
                return
            job.message = str(message).strip() or job.message
            job.ratio = max(0.0, min(1.0, float(ratio)))
            job.updated_at = time.monotonic()

    try:
        rows, error_rows = worker(report)
    except BaseException as exc:  # noqa: BLE001 - terminal job state must always be released.
        frames = traceback.extract_tb(exc.__traceback__)
        stack = " > ".join(
            f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}" for frame in frames[-8:]
        )
        LOGGER.error(
            "Background ranking failed job_id=%s error_type=%s stack=%s",
            job_id,
            type(exc).__name__,
            stack,
        )
        with _LOCK:
            job = _JOBS.get(cache_key)
            if job is None or job.job_id != job_id:
                return
            job.status = "failed"
            job.message = "ランキング作成を完了できませんでした。"
            job.error_type = type(exc).__name__
            job.updated_at = time.monotonic()
        return
    with _LOCK:
        job = _JOBS.get(cache_key)
        if job is None or job.job_id != job_id:
            return
        job.status = "completed"
        job.message = "ランキング更新が完了しました。"
        job.ratio = 1.0
        job.rows = list(rows)
        job.error_rows = list(error_rows)
        job.updated_at = time.monotonic()


def _snapshot(job: _RankingJob) -> RankingJobSnapshot:
    return RankingJobSnapshot(
        job_id=job.job_id,
        cache_key=job.cache_key,
        status=job.status,
        message=job.message,
        ratio=job.ratio,
        rows=list(job.rows),
        error_rows=list(job.error_rows),
        error_type=job.error_type,
        started_at=job.started_at,
        updated_at=job.updated_at,
    )


def _prune_jobs(now: float) -> None:
    for cache_key, job in tuple(_JOBS.items()):
        if job.status != "running" and now - job.updated_at > RANKING_JOB_TTL_SECONDS:
            _JOBS.pop(cache_key, None)


def _enforce_job_limit() -> None:
    terminal = sorted(
        (job for job in _JOBS.values() if job.status != "running"),
        key=lambda job: job.updated_at,
    )
    while len(_JOBS) > MAX_RANKING_JOBS and terminal:
        oldest = terminal.pop(0)
        _JOBS.pop(oldest.cache_key, None)
