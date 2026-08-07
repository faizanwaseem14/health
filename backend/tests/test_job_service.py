"""
Tests for the job state machine.

The DB-critical functions here (claim_job's atomic UPDATE especially)
need a real database to prove for real - see the Task summary for the
scratch-Postgres run that verified idempotent claiming, retries, and
timeouts end to end. What's tested here without any database or Redis:
the state vocabulary itself (a regression guard), the sensible-defaults
of the tunable constants, and the two user-friendly-failure behaviors -
that a Redis hiccup during upload never surfaces as an error, and that
retrying a genuinely failed job resets it correctly (or is refused for
a job that isn't actually failed).
"""

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.jobs.service import (
    CANCELLED,
    COMPLETED,
    FAILED,
    JOB_ENQUEUE_RETRY_DELAY,
    JOB_PROCESSING_TIMEOUT,
    MAX_JOB_ATTEMPTS,
    PROCESSING,
    QUEUED,
    REVIEW_REQUIRED,
    JobNotRetryableError,
    create_and_enqueue_job,
    retry_failed_job,
)
from app.models import Job


def test_job_states_match_the_agreed_vocabulary():
    # If any of these ever gets silently renamed, the worker, the
    # database, and anything reading job status all disagree with each
    # other - this test exists purely to catch that.
    assert QUEUED == "queued"
    assert PROCESSING == "processing"
    assert REVIEW_REQUIRED == "review_required"
    assert COMPLETED == "completed"
    assert FAILED == "failed"
    assert CANCELLED == "cancelled"


def test_max_attempts_is_a_small_positive_number():
    assert 1 <= MAX_JOB_ATTEMPTS <= 10


def test_processing_timeout_is_a_reasonable_duration():
    assert timedelta(seconds=30) <= JOB_PROCESSING_TIMEOUT <= timedelta(hours=1)


def test_enqueue_retry_delay_is_shorter_than_the_processing_timeout():
    # Otherwise a job could time out (get reaped) before we'd even
    # notice its original enqueue never went through.
    assert JOB_ENQUEUE_RETRY_DELAY < JOB_PROCESSING_TIMEOUT


# --- Change 1: a Redis hiccup during upload must never surface as an error ---


def test_create_and_enqueue_job_succeeds_even_when_redis_is_unreachable():
    fake_db = MagicMock()
    report_id = uuid.uuid4()

    with patch(
        "app.jobs.service.enqueue_job", side_effect=RuntimeError("Redis is down")
    ):
        # Must NOT raise - the file is already safely stored by the
        # time this runs, so a queue hiccup must never turn a
        # successful upload into an error.
        job = create_and_enqueue_job(fake_db, report_id, job_type="ocr_extraction")

    assert job.status == QUEUED
    assert job.report_id == report_id


def test_create_and_enqueue_job_succeeds_normally_when_redis_works():
    fake_db = MagicMock()
    report_id = uuid.uuid4()

    with patch("app.jobs.service.enqueue_job") as mock_enqueue:
        job = create_and_enqueue_job(fake_db, report_id, job_type="ocr_extraction")

    mock_enqueue.assert_called_once_with(job.id)
    assert job.status == QUEUED


# --- Change 2: retrying a genuinely failed job ---


def _fake_job_with_status(status_value):
    job = Job(id=uuid.uuid4(), report_id=uuid.uuid4(), job_type="ocr_extraction")
    job.status = status_value
    job.attempts = MAX_JOB_ATTEMPTS
    job.error_message = "processing blew up"
    return job


def test_retry_failed_job_resets_attempts_and_requeues():
    job = _fake_job_with_status(FAILED)

    def fake_get(model, id_):
        return job if model is Job else MagicMock()

    fake_db = MagicMock()
    fake_db.get.side_effect = fake_get

    with patch("app.jobs.service.enqueue_job") as mock_enqueue:
        result = retry_failed_job(fake_db, job.id)

    assert result.status == QUEUED
    assert result.attempts == 0
    assert result.error_message is None
    assert result.started_at is None
    assert result.completed_at is None
    mock_enqueue.assert_called_once_with(job.id)


def test_retry_failed_job_rejects_a_job_that_is_still_processing():
    job = _fake_job_with_status(PROCESSING)
    fake_db = MagicMock()
    fake_db.get.return_value = job

    with pytest.raises(JobNotRetryableError):
        retry_failed_job(fake_db, job.id)


def test_retry_failed_job_rejects_a_job_that_already_completed():
    job = _fake_job_with_status(COMPLETED)
    fake_db = MagicMock()
    fake_db.get.return_value = job

    with pytest.raises(JobNotRetryableError):
        retry_failed_job(fake_db, job.id)


def test_retry_failed_job_raises_for_a_job_that_does_not_exist():
    fake_db = MagicMock()
    fake_db.get.return_value = None

    with pytest.raises(JobNotRetryableError):
        retry_failed_job(fake_db, uuid.uuid4())


def test_retry_failed_job_does_not_raise_if_redis_is_down():
    # Same user-friendly-failure principle as change 1: a retry REQUEST
    # succeeding shouldn't depend on Redis being reachable at that
    # exact instant either.
    job = _fake_job_with_status(FAILED)

    def fake_get(model, id_):
        return job if model is Job else MagicMock()

    fake_db = MagicMock()
    fake_db.get.side_effect = fake_get

    with patch("app.jobs.service.enqueue_job", side_effect=RuntimeError("down")):
        result = retry_failed_job(fake_db, job.id)

    assert result.status == QUEUED
