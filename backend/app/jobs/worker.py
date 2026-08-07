"""
The background worker: a SEPARATE process from the web server that
pulls job IDs off the Redis queue and processes them, so an upload
request never has to wait on slow work.

Run it with:

    python -m app.jobs.worker

Today, "processing" a job is a placeholder stub - it doesn't do OCR or
call any AI yet (that's later groups). What this file proves is that
the whole pipeline works end to end: a job goes from the queue, gets
safely claimed exactly once even if delivered twice, moves through the
right states, retries on failure, and never gets stuck. The real
processing steps plug into `process_job_stub` later without touching
any of this file's plumbing.
"""

import logging
import time

from app.database import SessionLocal
from app.jobs.queue import dequeue_job
from app.jobs.service import (
    COMPLETED,
    REVIEW_REQUIRED,
    claim_job,
    complete_job,
    fail_or_retry_job,
    mark_needs_review,
    reap_stuck_jobs,
)
from app.models import Job

logger = logging.getLogger("medvault")

POLL_INTERVAL_SECONDS = 2


def process_job_stub(job: Job) -> str:
    """
    PLACEHOLDER for the real processing steps (OCR, AI extraction, ...)
    that later groups will add. Returns one of COMPLETED or
    REVIEW_REQUIRED, or raises an exception to signal failure - the
    same three outcomes a real processor will eventually have. For now
    it always succeeds immediately.
    """
    return COMPLETED


def run_one_job(job_id: str, processor=process_job_stub) -> None:
    """
    Claims one job by ID and runs it through `processor`, handling
    every outcome:
      - couldn't be claimed (already handled / duplicate delivery) -> do nothing
      - processor returns COMPLETED -> mark completed
      - processor returns REVIEW_REQUIRED -> mark needing review
      - processor raises -> retry (if attempts remain) or mark failed
    """
    db = SessionLocal()
    try:
        job = claim_job(db, job_id)
        if job is None:
            # This IS the idempotency guarantee in action: a job that's
            # already being processed, already finished, or was
            # cancelled simply can't be claimed again - doing nothing
            # here is the correct, safe behavior for a duplicate
            # delivery.
            logger.info("Job %s could not be claimed (already handled)", job_id)
            return

        try:
            outcome = processor(job)
        except Exception as error:
            logger.exception("Job %s failed", job_id)
            fail_or_retry_job(db, job.id, error_message=str(error))
            return

        if outcome == REVIEW_REQUIRED:
            mark_needs_review(db, job.id)
        else:
            complete_job(db, job.id)
    finally:
        db.close()


def run_worker_loop(max_iterations: int | None = None) -> None:
    """
    The main loop: on each pass, reaps any stuck jobs, then pulls the
    next job off the queue (if any) and processes it.

    We POLL rather than block-wait: Upstash's REST API is a series of
    discrete HTTPS requests, not a persistent connection that could
    block-wait for new work the way a raw Redis connection might.

    max_iterations is for tests - real usage leaves it as None, which
    loops forever.
    """
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        db = SessionLocal()
        try:
            reaped = reap_stuck_jobs(db)
            if reaped:
                logger.info("Reaped %d stuck job(s)", reaped)
        finally:
            db.close()

        job_id = dequeue_job()
        if job_id is None:
            time.sleep(POLL_INTERVAL_SECONDS)
        else:
            run_one_job(job_id)

        iterations += 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("MedVault worker starting...")
    run_worker_loop()
