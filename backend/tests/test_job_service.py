"""
Tests for the job state machine.

The DB-critical functions here (claim_job's atomic UPDATE especially)
need a real database to prove for real - see the Task summary for the
scratch-Postgres run that verified idempotent claiming, retries, and
timeouts end to end. What's tested here without any database or Redis:
the state vocabulary itself (a regression guard - these exact six
strings are what the schema, the worker, and any future frontend all
agree on) and the sensible-defaults of the tunable constants.
"""

from datetime import timedelta

from app.jobs.service import (
    CANCELLED,
    COMPLETED,
    FAILED,
    JOB_PROCESSING_TIMEOUT,
    MAX_JOB_ATTEMPTS,
    PROCESSING,
    QUEUED,
    REVIEW_REQUIRED,
)


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
