"""
Job lifecycle management: creating jobs, safely CLAIMING one for
processing (the piece that makes redelivery safe), and moving a job
through its states. The `jobs` table (Day 1 schema) is the source of
truth for a job's state - Redis (app/jobs/queue.py) only ever signals
"something is ready"; it never decides what state a job is actually in.

The six states a job can ever be in - no other string is ever written
to jobs.status:

    queued          -> waiting for a worker to pick it up
    processing      -> a worker has claimed it and is working on it
    review_required -> processing finished but needs a human to look
                        (not built into any real decision yet - that
                        comes with real OCR/AI in a later group - but
                        the state itself is fully wired up now)
    completed       -> finished successfully
    failed          -> ran out of retries, or errored in a way that
                        can't be retried
    cancelled       -> explicitly cancelled before it finished
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs.queue import enqueue_job
from app.models import Job

logger = logging.getLogger("medvault")

QUEUED = "queued"
PROCESSING = "processing"
REVIEW_REQUIRED = "review_required"
COMPLETED = "completed"
FAILED = "failed"
CANCELLED = "cancelled"

_TERMINAL_STATES = {COMPLETED, FAILED, CANCELLED}

# A job gets this many total attempts before it's given up on as
# permanently failed - named here once rather than as a bare number.
MAX_JOB_ATTEMPTS = 3

# If a job has been "processing" longer than this, whatever worker
# claimed it must have crashed or hung - reap_stuck_jobs() below moves
# it along instead of leaving it stuck forever.
JOB_PROCESSING_TIMEOUT = timedelta(minutes=5)


def create_and_enqueue_job(db: Session, report_id: UUID, job_type: str) -> Job:
    """
    Creates a job row (status=queued) and puts its ID on the Redis
    queue for a worker to pick up. Called right after a report upload
    finishes successfully.

    If putting it on the queue fails (e.g. Redis is briefly
    unreachable), the job is marked failed immediately rather than left
    behind claiming to be "queued" when nothing will ever come to pick
    it up - that's exactly the "silent limbo" this whole system exists
    to avoid.
    """
    job = Job(report_id=report_id, job_type=job_type, status=QUEUED, attempts=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        enqueue_job(job.id)
    except Exception:
        logger.exception("Failed to enqueue job %s", job.id)
        job.status = FAILED
        job.error_message = "Failed to enqueue job."
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise

    return job


def claim_job(db: Session, job_id: UUID) -> Job | None:
    """
    Atomically moves a job from "queued" to "processing" - and ONLY
    succeeds if it was still "queued" at that exact moment.

    This is what makes redelivery (and even two workers racing for the
    same job) safe: it's a single UPDATE ... WHERE status = 'queued',
    so only ONE caller can ever win it, no matter how many times the
    same job ID gets handed to a worker. A plain ORM "load it, check its
    status in Python, then save it" would have a race window between
    the check and the save - this raw, atomic UPDATE has none.

    Returns the claimed Job, or None if it couldn't be claimed (already
    being processed, already finished, cancelled, or doesn't exist) -
    in which case the caller should simply do nothing.
    """
    result = db.execute(
        text(
            """
            UPDATE jobs
            SET status = :processing, started_at = :now, attempts = attempts + 1
            WHERE id = :job_id AND status = :queued
            """
        ),
        {
            "processing": PROCESSING,
            "now": datetime.now(timezone.utc),
            "job_id": job_id,
            "queued": QUEUED,
        },
    )
    claimed = result.rowcount == 1
    db.commit()

    if not claimed:
        return None
    return db.get(Job, job_id)


def complete_job(db: Session, job_id: UUID) -> None:
    """Marks a job completed. A no-op if it isn't currently processing."""
    job = db.get(Job, job_id)
    if job is None or job.status != PROCESSING:
        return
    job.status = COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def mark_needs_review(db: Session, job_id: UUID) -> None:
    """Marks a job as needing human review. A no-op if it isn't currently processing."""
    job = db.get(Job, job_id)
    if job is None or job.status != PROCESSING:
        return
    job.status = REVIEW_REQUIRED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


def fail_or_retry_job(db: Session, job_id: UUID, error_message: str) -> None:
    """
    Called when processing a job raises an error. If attempts remain,
    puts it back in the queue for another try; otherwise marks it
    permanently failed. A no-op if the job isn't currently processing.
    """
    job = db.get(Job, job_id)
    if job is None or job.status != PROCESSING:
        return

    job.error_message = error_message

    if job.attempts < MAX_JOB_ATTEMPTS:
        job.status = QUEUED
        job.started_at = None
        db.commit()
        enqueue_job(job.id)
    else:
        job.status = FAILED
        job.completed_at = datetime.now(timezone.utc)
        db.commit()


def cancel_job(db: Session, job_id: UUID) -> bool:
    """
    Cancels a job that hasn't finished yet. Returns True if it was
    actually cancelled, False if it had already reached a terminal
    state (or doesn't exist) - cancelling twice is a safe no-op.

    Unlike claim_job(), this doesn't need a raw atomic UPDATE: claiming
    has to defend against many workers racing for the same queued job,
    but cancelling is a single explicit action with no such race in
    this system, so a plain read-then-write is enough.
    """
    job = db.get(Job, job_id)
    if job is None or job.status in _TERMINAL_STATES:
        return False
    job.status = CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    return True


def reap_stuck_jobs(db: Session) -> int:
    """
    Finds jobs that have been "processing" for longer than
    JOB_PROCESSING_TIMEOUT - meaning whatever worker claimed them
    crashed or hung before finishing - and moves them along: retried if
    attempts remain, permanently failed otherwise. Nothing is ever left
    sitting in "processing" forever.

    Returns how many jobs were reaped, so the worker loop can log it.
    """
    cutoff = datetime.now(timezone.utc) - JOB_PROCESSING_TIMEOUT
    stuck_jobs = (
        db.query(Job).filter(Job.status == PROCESSING, Job.started_at < cutoff).all()
    )

    for job in stuck_jobs:
        job.error_message = "Timed out."
        if job.attempts < MAX_JOB_ATTEMPTS:
            job.status = QUEUED
            job.started_at = None
            db.commit()
            enqueue_job(job.id)
        else:
            job.status = FAILED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

    return len(stuck_jobs)
