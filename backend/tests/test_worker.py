"""
Tests for the worker's dispatch logic: given each possible outcome of
claiming and processing a job, does it call the right state-transition
function? The state transitions THEMSELVES (claim_job, complete_job,
...) are mocked here - they're proven for real against a database in
the Task summary. This file is only testing run_one_job's and
run_worker_loop's control flow in isolation.

process_ocr_job (the real processor, replacing the old placeholder
stub) is also tested here in isolation - run_ocr_for_report and
run_extraction_for_report themselves (the actual OCR/AI work) are
tested for real in test_ocr_service.py / test_ai_service.py and the
Task summary's scratch-Postgres run.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.ai.extraction import ExtractionRefusedError, ExtractionValidationError
from app.ai.schema import ExtractionResult
from app.jobs.service import COMPLETED, REVIEW_REQUIRED
from app.jobs.worker import process_ocr_job, run_one_job, run_worker_loop
from app.models import Job, Report
from app.ocr.types import BoundingBox, OcrResult
from app.ocr.types import OcrWord as OcrWordShape


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
        patch("app.jobs.worker.retry_unenqueued_jobs", return_value=0),
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
        patch("app.jobs.worker.retry_unenqueued_jobs", return_value=0),
        patch("app.jobs.worker.dequeue_job", return_value=None),
        patch("app.jobs.worker.time.sleep"),
    ):
        run_worker_loop(max_iterations=3)

    assert mock_reap.call_count == 3


def test_run_worker_loop_retries_unenqueued_jobs_every_iteration():
    with (
        patch("app.jobs.worker.SessionLocal", return_value=MagicMock()),
        patch("app.jobs.worker.reap_stuck_jobs", return_value=0),
        patch("app.jobs.worker.retry_unenqueued_jobs", return_value=0) as mock_retry,
        patch("app.jobs.worker.dequeue_job", return_value=None),
        patch("app.jobs.worker.time.sleep"),
    ):
        run_worker_loop(max_iterations=3)

    assert mock_retry.call_count == 3


# --- process_ocr_job: the real processor, replacing the old stub ---


def test_run_one_job_defaults_to_the_real_ocr_processor():
    # Proves the OCR group actually REPLACED the placeholder stub as
    # run_one_job's default - not just added process_ocr_job alongside
    # a stub that's still secretly what runs in production.
    assert run_one_job.__defaults__[0] is process_ocr_job


def _fake_ocr_result_with_one_word() -> OcrResult:
    return OcrResult(
        words=[
            OcrWordShape(
                text="Hi",
                confidence=0.9,
                bounding_box=BoundingBox.from_rectangle(0, 0, 1, 1),
                page_number=1,
            )
        ]
    )


def test_process_ocr_job_returns_completed_when_extraction_succeeds():
    job = _fake_job(str(uuid.uuid4()))
    fake_db = MagicMock()
    fake_report = Report(id=job.report_id, storage_key="reports/x/y.png")
    fake_db.get.return_value = fake_report

    with (
        patch("app.jobs.worker.SessionLocal", return_value=fake_db),
        patch(
            "app.jobs.worker.run_ocr_for_report",
            return_value=_fake_ocr_result_with_one_word(),
        ),
        patch(
            "app.jobs.worker.run_extraction_for_report",
            return_value=ExtractionResult(rows=[]),
        ) as mock_extract,
    ):
        outcome = process_ocr_job(job)

    assert outcome == COMPLETED
    mock_extract.assert_called_once_with(fake_db, fake_report, job.id)
    fake_db.close.assert_called_once()


def test_process_ocr_job_returns_review_required_when_no_words_are_found():
    # A blank page or unreadable scan is a genuinely ambiguous outcome -
    # worth a human's eyes, not silently "done" with nothing to show.
    # AI extraction is never even attempted - there's nothing to extract from.
    job = _fake_job(str(uuid.uuid4()))
    fake_db = MagicMock()
    fake_report = Report(id=job.report_id, storage_key="reports/x/y.png")
    fake_db.get.return_value = fake_report

    with (
        patch("app.jobs.worker.SessionLocal", return_value=fake_db),
        patch("app.jobs.worker.run_ocr_for_report", return_value=OcrResult(words=[])),
        patch("app.jobs.worker.run_extraction_for_report") as mock_extract,
    ):
        outcome = process_ocr_job(job)

    assert outcome == REVIEW_REQUIRED
    mock_extract.assert_not_called()


def test_process_ocr_job_returns_review_required_when_extraction_fails_validation():
    # Malformed/schema-mismatched AI output is never saved - route to
    # review rather than trusting it.
    job = _fake_job(str(uuid.uuid4()))
    fake_db = MagicMock()
    fake_report = Report(id=job.report_id, storage_key="reports/x/y.png")
    fake_db.get.return_value = fake_report

    with (
        patch("app.jobs.worker.SessionLocal", return_value=fake_db),
        patch(
            "app.jobs.worker.run_ocr_for_report",
            return_value=_fake_ocr_result_with_one_word(),
        ),
        patch(
            "app.jobs.worker.run_extraction_for_report",
            side_effect=ExtractionValidationError("bad output"),
        ),
    ):
        outcome = process_ocr_job(job)

    assert outcome == REVIEW_REQUIRED


def test_process_ocr_job_returns_review_required_when_claude_refuses():
    job = _fake_job(str(uuid.uuid4()))
    fake_db = MagicMock()
    fake_report = Report(id=job.report_id, storage_key="reports/x/y.png")
    fake_db.get.return_value = fake_report

    with (
        patch("app.jobs.worker.SessionLocal", return_value=fake_db),
        patch(
            "app.jobs.worker.run_ocr_for_report",
            return_value=_fake_ocr_result_with_one_word(),
        ),
        patch(
            "app.jobs.worker.run_extraction_for_report",
            side_effect=ExtractionRefusedError("declined"),
        ),
    ):
        outcome = process_ocr_job(job)

    assert outcome == REVIEW_REQUIRED


def test_process_ocr_job_propagates_a_genuine_extraction_error():
    # A real API/network error (rate limit, connection failure, ...) is
    # NOT a validation or refusal outcome - it must propagate so
    # run_one_job's existing retry handling (tested above) kicks in,
    # exactly like an OCR download failure already does.
    job = _fake_job(str(uuid.uuid4()))
    fake_db = MagicMock()
    fake_report = Report(id=job.report_id, storage_key="reports/x/y.png")
    fake_db.get.return_value = fake_report

    with (
        patch("app.jobs.worker.SessionLocal", return_value=fake_db),
        patch(
            "app.jobs.worker.run_ocr_for_report",
            return_value=_fake_ocr_result_with_one_word(),
        ),
        patch(
            "app.jobs.worker.run_extraction_for_report",
            side_effect=RuntimeError("connection reset"),
        ),
    ):
        with pytest.raises(RuntimeError, match="connection reset"):
            process_ocr_job(job)

    fake_db.close.assert_called_once()


def test_process_ocr_job_raises_when_the_report_is_missing():
    # run_one_job's existing except-and-retry handling (tested above)
    # is what turns this into a normal retry - process_ocr_job itself
    # just needs to raise, not swallow it.
    job = _fake_job(str(uuid.uuid4()))
    fake_db = MagicMock()
    fake_db.get.return_value = None

    with patch("app.jobs.worker.SessionLocal", return_value=fake_db):
        with pytest.raises(ValueError):
            process_ocr_job(job)

    fake_db.close.assert_called_once()
