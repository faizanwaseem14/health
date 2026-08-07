"""
Tests for the worker's dispatch logic: given each possible outcome of
claiming and processing a job, does it call the right state-transition
function? The state transitions THEMSELVES (claim_job, complete_job,
...) are mocked here - they're proven for real against a database in
the Task summary. This file is only testing run_one_job's and
run_worker_loop's control flow in isolation.
"""

import uuid
from unittest.mock import MagicMock, patch

from app.jobs.service import COMPLETED, REVIEW_REQUIRED
from app.jobs.worker import run_one_job, run_worker_loop
from app.models import Job


def _fake_job(job_id):
    job = Job(report_id=uuid.uuid4(), job_type="ocr_extraction")
    job.id = job_id
    return job


def test_run_one_job_does_nothing_when_the_job_cannot_be_claimed():
    job_id = str(uuid.uuid4())

    with (
        patch("app.jobs.worker.SessionLocal", return_value=MagicMock()),
        patch("app.jobs.worker.claim_job", return_value=None) as mock_claim,
        patch("app.jobs.worker.complete_job") as mock_complete,
        patch("app.jobs.worker.fail_or_retry_job") as mock_fail,
        patch("app.jobs.worker.mark_needs_review") as mock_review,
    ):
        run_one_job(job_id)

    mock_claim.assert_called_once()
    # This IS the idempotency guarantee: nothing else should happen for
    # a job that couldn't be claimed (already handled / duplicate
    # delivery / cancelled).
    mock_complete.assert_not_called()
    mock_fail.assert_not_called()
    mock_review.assert_not_called()


def test_run_one_job_marks_completed_on_success():
    job_id = str(uuid.uuid4())
    job = _fake_job(job_id)

    with (
        patch("app.jobs.worker.SessionLocal", return_value=MagicMock()),
        patch("app.jobs.worker.claim_job", return_value=job),
        patch("app.jobs.worker.complete_job") as mock_complete,
        patch("app.jobs.worker.mark_needs_review") as mock_review,
    ):
        run_one_job(job_id, processor=lambda job: COMPLETED)

    mock_complete.assert_called_once()
    assert mock_complete.call_args[0][1] == job.id
    mock_review.assert_not_called()


def test_run_one_job_marks_review_required_when_processor_says_so():
    job_id = str(uuid.uuid4())
    job = _fake_job(job_id)

    with (
        patch("app.jobs.worker.SessionLocal", return_value=MagicMock()),
        patch("app.jobs.worker.claim_job", return_value=job),
        patch("app.jobs.worker.complete_job") as mock_complete,
        patch("app.jobs.worker.mark_needs_review") as mock_review,
    ):
        run_one_job(job_id, processor=lambda job: REVIEW_REQUIRED)

    mock_review.assert_called_once()
    assert mock_review.call_args[0][1] == job.id
    mock_complete.assert_not_called()


def test_run_one_job_retries_when_the_processor_raises():
    job_id = str(uuid.uuid4())
    job = _fake_job(job_id)

    def failing_processor(job):
        raise ValueError("something went wrong")

    with (
        patch("app.jobs.worker.SessionLocal", return_value=MagicMock()),
        patch("app.jobs.worker.claim_job", return_value=job),
        patch("app.jobs.worker.fail_or_retry_job") as mock_fail,
        patch("app.jobs.worker.complete_job") as mock_complete,
    ):
        run_one_job(job_id, processor=failing_processor)

    mock_fail.assert_called_once()
    assert mock_fail.call_args[0][1] == job.id
    assert "something went wrong" in mock_fail.call_args[1]["error_message"]
    mock_complete.assert_not_called()


def test_run_worker_loop_processes_one_job_then_stops():
    with (
        patch("app.jobs.worker.SessionLocal", return_value=MagicMock()),
        patch("app.jobs.worker.reap_stuck_jobs", return_value=0),
        patch("app.jobs.worker.dequeue_job", side_effect=["job-1", None]),
        patch("app.jobs.worker.run_one_job") as mock_run_one_job,
        patch("app.jobs.worker.time.sleep"),
    ):
        run_worker_loop(max_iterations=2)

    mock_run_one_job.assert_called_once_with("job-1")


def test_run_worker_loop_reaps_stuck_jobs_every_iteration():
    with (
        patch("app.jobs.worker.SessionLocal", return_value=MagicMock()),
        patch("app.jobs.worker.reap_stuck_jobs", return_value=0) as mock_reap,
        patch("app.jobs.worker.dequeue_job", return_value=None),
        patch("app.jobs.worker.time.sleep"),
    ):
        run_worker_loop(max_iterations=3)

    assert mock_reap.call_count == 3
