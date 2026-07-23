import logging
import os
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable

from infrastructure import (
    load_job_status,
    redis_client,
    store_job_status,
)
from models import JobStatus
from operations import increment
from structured_logging import get_logger, log_event

_executor = ThreadPoolExecutor(max_workers=int(os.getenv("LOCAL_JOB_WORKERS", "3")))
_futures: dict[str, Future] = {}
_created_at: dict[str, float] = {}
logger = get_logger("jobs")


def _purge_expired_local_jobs() -> None:
    cutoff = time.monotonic() - int(os.getenv("JOB_RESULT_TTL", "3600"))
    expired = [
        job_id
        for job_id, created_at in _created_at.items()
        if created_at < cutoff
    ]
    for job_id in expired:
        _created_at.pop(job_id, None)
        _futures.pop(job_id, None)


def _run_local(
    job_id: str,
    function: Callable[..., dict],
    args: tuple[Any, ...],
) -> dict:
    store_job_status(job_id, {"id": job_id, "status": "running"})
    try:
        result = function(*args)
        status = {"id": job_id, "status": "finished", "result": result}
        increment("jobs_finished")
        log_event(logger, logging.INFO, "job_finished", job_id=job_id)
    except Exception as exc:
        status = {"id": job_id, "status": "failed", "error": str(exc)}
        increment("jobs_failed")
        log_event(
            logger,
            logging.ERROR,
            "job_failed",
            job_id=job_id,
            error_type=type(exc).__name__,
        )
    store_job_status(job_id, status)
    return status


def submit_job(
    function: Callable[..., dict],
    *args: Any,
) -> JobStatus:
    increment("jobs_queued")
    _purge_expired_local_jobs()
    client = redis_client()
    if client is not None and os.getenv("BACKGROUND_QUEUE", "local") == "rq":
        from rq import Queue

        job = Queue("predict_with_fun", connection=client).enqueue(
            function,
            *args,
            job_timeout=int(os.getenv("JOB_TIMEOUT", "600")),
            result_ttl=int(os.getenv("JOB_RESULT_TTL", "3600")),
        )
        log_event(
            logger,
            logging.INFO,
            "job_queued",
            job_id=job.id,
            queue="rq",
            task=function.__name__,
        )
        return JobStatus(id=job.id, status="queued")

    job_id = str(uuid.uuid4())
    initial = {"id": job_id, "status": "queued"}
    store_job_status(job_id, initial)
    _created_at[job_id] = time.monotonic()
    _futures[job_id] = _executor.submit(_run_local, job_id, function, args)
    log_event(
        logger,
        logging.INFO,
        "job_queued",
        job_id=job_id,
        queue="local",
        task=function.__name__,
    )
    return JobStatus(**initial)


def get_job_status(job_id: str) -> JobStatus | None:
    _purge_expired_local_jobs()
    shared = load_job_status(job_id)
    if shared:
        return JobStatus.model_validate(shared)
    future = _futures.get(job_id)
    if future is not None:
        if not future.done():
            return JobStatus(id=job_id, status="running")
        return JobStatus.model_validate(future.result())

    client = redis_client()
    if client is not None and os.getenv("BACKGROUND_QUEUE", "local") == "rq":
        from rq.job import Job

        try:
            job = Job.fetch(job_id, connection=client)
        except Exception:
            return None
        status = job.get_status(refresh=True)
        if status == "finished":
            return JobStatus(id=job_id, status="finished", result=job.result)
        if status in {"failed", "stopped", "canceled"}:
            return JobStatus(
                id=job_id,
                status="failed",
                error=job.exc_info or "Background job failed.",
            )
        return JobStatus(
            id=job_id,
            status="running" if status == "started" else "queued",
        )
    return None
