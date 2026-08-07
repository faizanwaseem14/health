"""
The background worker: a SEPARATE process from the web server that
pulls job IDs off the Redis queue and processes them, so an upload
request never has to wait on slow work.

Run it with:

    python -m app.jobs.worker

"Processing" a job now means OCR (see app/ocr/) followed by AI
extraction (see app/ai/): download the report's original file from R2,
run it through the active OCR provider and store the extracted words
as evidence, then send that evidence to Claude and store the
structured test rows it returns. The AI's job is only structured
extraction - it never decides what a value means or flags anything;
that "trust chain" verification is still a later group's work.

What this file proves, regardless of what `processor` actually does: a
job goes from the queue, gets safely claimed exactly once even if
delivered twice, moves through the right states, retries on failure,
and never gets stuck.
"""

import logging
import time

from app.ai.extraction import ExtractionRefusedError, ExtractionValidationError
from app.ai.service import run_extraction_for_report
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
    retry_unenqueued_jobs,
)
from app.models import Job, Report
from app.ocr.service import run_ocr_for_report

logger = logging.getLogger("medvault")

POLL_INTERVAL_SECONDS = 2


def process_ocr_job(job: Job) -> str:
    """
    Runs OCR on the job's report, stores the result as evidence, then
    (if OCR found any text) sends that evidence to Claude for
    structured extraction.

    Returns REVIEW_REQUIRED if OCR found no text at all (a blank page,
    or a scan too poor to read), or if Claude's response didn't
    validate against the strict schema or was refused - all genuinely
    ambiguous cases worth a human's eyes rather than silently marking
    the job "done" with nothing (or untrustworthy data) to show.
    Returns COMPLETED once real, validated rows are stored. Raising
    here (a download failure, an OCR provider error, or a genuine
    Claude API/network error) is exactly how a real, retryable failure
    signals to run_one_job below.

    Opens its own database session, separate from run_one_job's: the
    claim/complete state transitions and the actual processing work are
    two different concerns, and this stays a simple `(job) -> str`,
    matching every other processor this worker could ever be given (see
    the tests in test_worker.py).
    """
    db = SessionLocal()
    try:
        report = db.get(Report, job.report_id)
        if report is None:
            raise ValueError(f"Report {job.report_id} not found for job {job.id}.")

        ocr_result = run_ocr_for_report(db, report, job.id)
        if not ocr_result.words:
            return REVIEW_REQUIRED

        try:
            run_extraction_for_report(db, report, job.id)
        except (ExtractionValidationError, ExtractionRefusedError):
            logger.warning(
                "AI extraction for report %s needs review", report.id, exc_info=True
            )
            return REVIEW_REQUIRED
    finally:
        db.close()

    return COMPLETED


def run_one_job(job_id: str, processor=process_ocr_job) -> None:
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

            retried = retry_unenqueued_jobs(db)
            if retried:
                logger.info("Retried enqueueing %d job(s)", retried)
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
