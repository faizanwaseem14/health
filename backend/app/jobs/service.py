"""
Job lifecycle management: creating jobs, safely CLAIMING one for
processing (the piece that makes redelivery safe), moving a job through
its states, and keeping the REPORT's own status in sync with what its
job is doing - so a report's status always tells the truth about
whether its file is safe (always) and whether processing worked.

The `jobs` table (Day 1 schema) is the source of truth for a job's
state - Redis (app/jobs/queue.py) only ever signals "something is
ready"; it never decides what state a job is actually in.

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

IMPORTANT: nothing in this module ever fails an upload, and nothing
here re-processes or re-touches the ORIGINAL FILE. A Redis hiccup or a
processing failure is always something that happens to the JOB - the
file in R2 is untouched either way, and never needs re-uploading.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs.queue import enqueue_job
from app.models import Job, Report

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

# How long a job is allowed to sit "queued" with zero attempts before we
# suspect its original enqueue() call to Redis silently failed, and try
# pushing it again. Long enough that a normal enqueue+claim (which
# happens in milliseconds under normal conditions) never triggers this.
JOB_ENQUEUE_RETRY_DELAY = timedelta(seconds=30)

# The report.status values this module keeps in sync with job outcomes
# (the Report model's own comment already anticipated exactly these).
REPORT_UPLOADED = "uploaded"
REPORT_PROCESSING = "processing"
REPORT_PROCESSED = "processed"
REPORT_FAILED = "failed"


class JobNotRetryableError(Exception):
    """Raised when trying to retry a job that isn't actually 'failed'."""


def _enqueue_or_log(job_id) -> None:
    """
    Puts a job on the Redis queue, but NEVER lets a transient failure
    propagate as an error to whoever called us - a successful upload
    (or a retry request) should never turn into an error just because
    Redis hiccuped for a moment. The job simply stays "queued" in the
    database, and retry_unenqueued_jobs() (called every pass of the
    worker loop) will notice and try again shortly.
    """
    try:
        enqueue_job(job_id)
    except Exception:
        logger.exception(
            "Failed to enqueue job %s - will retry automatically in the background",
            job_id,
        )


def _sync_report_status(db: Session, job: Job, report_status: str) -> None:
    """Keeps the report's status lined up with what its job just did."""
    report = db.get(Report, job.report_id)
    if report is not None:
        report.status = report_status
        db.commit()


def create_and_enqueue_job(db: Session, report_id: UUID, job_type: str) -> Job:
    """
    Creates a job row (status=queued) and puts its ID on the Redis
    queue for a worker to pick up. Called right after a report upload
    finishes successfully.

    The upload NEVER fails because of this step: the file is already
    safely stored in R2 by the time this runs, so if Redis is briefly
    unreachable, the job just stays "queued" (see _enqueue_or_log) and
    gets automatically retried in the background - the caller (the
    upload route) always gets a job back and the request succeeds.
    """
    job = Job(report_id=report_id, job_type=job_type, status=QUEUED, attempts=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    _enqueue_or_log(job.id)

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

    job = db.get(Job, job_id)
    _sync_report_status(db, job, REPORT_PROCESSING)
    return job


def complete_job(db: Session, job_id: UUID) -> None:
    """Marks a job completed. A no-op if it isn't currently processing."""
    job = db.get(Job, job_id)
    if job is None or job.status != PROCESSING:
        return
    job.status = COMPLETED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    _sync_report_status(db, job, REPORT_PROCESSED)


def mark_needs_review(db: Session, job_id: UUID) -> None:
    """Marks a job as needing human review. A no-op if it isn't currently processing."""
    job = db.get(Job, job_id)
    if job is None or job.status != PROCESSING:
        return
    job.status = REVIEW_REQUIRED
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    # report.status intentionally stays "processing" here - Day 1's
    # anticipated report statuses (uploaded/processing/processed/failed)
    # don't include a review state of their own, and adding one isn't
    # part of this change.


def fail_or_retry_job(db: Session, job_id: UUID, error_message: str) -> None:
    """
    Called when processing a job raises an error. If attempts remain,
    puts it back in the queue for another try; otherwise marks it
    permanently failed AND updates the report's status to match, so the
    frontend can tell the user processing failed - while the file
    itself was never touched and needs no re-upload. A no-op if the
    job isn't currently processing.
    """
    job = db.get(Job, job_id)
    if job is None or job.status != PROCESSING:
        return

    job.error_message = error_message

    if job.attempts < MAX_JOB_ATTEMPTS:
        job.status = QUEUED
        job.started_at = None
        db.commit()
        _enqueue_or_log(job.id)
    else:
        job.status = FAILED
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        _sync_report_status(db, job, REPORT_FAILED)


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
    attempts remain, permanently failed (with the report updated to
    match) otherwise. Nothing is ever left sitting in "processing"
    forever.

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
            _enqueue_or_log(job.id)
        else:
            job.status = FAILED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            _sync_report_status(db, job, REPORT_FAILED)

    return len(stuck_jobs)


def retry_unenqueued_jobs(db: Session) -> int:
    """
    Finds jobs that are still "queued" but have sat unclaimed for a
    suspiciously long time - a sign the original enqueue() call may
    have silently failed right after a report was uploaded (or a
    failed job was retried) - and puts their ID on the queue again.

    This is always safe to call even if the original enqueue actually
    DID succeed: claim_job()'s atomic UPDATE means a job can only ever
    be claimed once, so a duplicate entry in the Redis queue for a job
    that's already being processed (or already finished) is simply
    ignored once it's eventually dequeued.

    Returns how many jobs were retried, so the worker loop can log it.
    """
    cutoff = datetime.now(timezone.utc) - JOB_ENQUEUE_RETRY_DELAY
    stale_jobs = (
        db.query(Job)
        .filter(Job.status == QUEUED, Job.attempts == 0, Job.created_at < cutoff)
        .all()
    )
    for job in stale_jobs:
        _enqueue_or_log(job.id)
    return len(stale_jobs)


def get_latest_job_for_report(db: Session, report_id: UUID) -> Job | None:
    """The most recent job created for a report - what a retry acts on."""
    return (
        db.query(Job)
        .filter(Job.report_id == report_id)
        .order_by(Job.created_at.desc())
        .first()
    )


def retry_failed_job(db: Session, job_id: UUID) -> Job:
    """
    Resets a permanently-failed job back to "queued" with a brand new
    set of attempts, and puts it back on the queue. Only works on a job
    that's genuinely "failed" - retrying one that's still in progress,
    already succeeded, or was cancelled would be a mistake, not a
    legitimate retry, so that raises JobNotRetryableError instead.

    The original file in R2 was never touched by any of this and does
    not need to be re-uploaded - only the processing job is reset.
    """
    job = db.get(Job, job_id)
    if job is None:
        raise JobNotRetryableError("Job not found.")
    if job.status != FAILED:
        raise JobNotRetryableError(
            f"Job is '{job.status}', not 'failed' - only a failed job can be retried."
        )

    job.status = QUEUED
    job.attempts = 0
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    db.commit()

    _sync_report_status(db, job, REPORT_PROCESSING)
    _enqueue_or_log(job.id)

    return job
