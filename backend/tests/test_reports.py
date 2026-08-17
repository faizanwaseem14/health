"""
Tests for the report upload route.

Validation failures (oversized file, wrong file type, no login) never
touch the database - they're rejected before any DB code runs - so
those are tested for real, with no live database needed. The full
happy path (file -> R2 -> a real database row) needs a real database
for the "id"/timestamps SQLAlchemy only fills in at actual flush time;
that's verified for real against a throwaway local Postgres (see the
Task summary), with R2 itself mocked since this sandbox has no real R2
credentials.

Here, for the happy-path shape check, we mock the database session too
- enough to prove the file was correctly validated, fingerprinted, and
handed to R2 with the right bytes and key, even though the response's
"id" field won't be a real value in this particular test. Job creation
(app.jobs.service.create_and_enqueue_job) is mocked here too, since it
would otherwise make a real HTTP call to Upstash - see test_job_service.py,
test_worker.py, and the Task summaries for the real, end-to-end proof of
the queue/worker pipeline (including retries) against a throwaway local
Postgres.

The retry route's own logic (get_latest_job_for_report,
retry_failed_job) is mocked here too, for the same reason.
"""

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from app.auth.dependencies import get_current_user
from app.jobs.service import (
    COMPLETED,
    FAILED,
    PROCESSING,
    QUEUED,
    REVIEW_REQUIRED,
    JobNotRetryableError,
)
from app.main import app
from app.models import Job, Profile, Report, User
from app.routers.reports import require_owned_profile, require_owned_report

client = TestClient(app)

_REAL_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def _make_real_png_bytes(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color="green")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _override_auth(user: User, profile: Profile):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_profile] = lambda: profile


def _clear_overrides():
    app.dependency_overrides.clear()


def test_upload_requires_login():
    response = client.post(
        f"/profiles/{uuid.uuid4()}/reports",
        files={"file": ("photo.png", _REAL_PNG_BYTES, "image/png")},
    )

    assert response.status_code == 401


def test_upload_rejects_a_file_over_25mb():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    profile = Profile(id=uuid.uuid4(), user_id=user.id, full_name="Alice")
    _override_auth(user, profile)

    try:
        oversized = b"\x89PNG\r\n\x1a\n" + (b"0" * (26 * 1024 * 1024))
        response = client.post(
            f"/profiles/{profile.id}/reports",
            files={"file": ("photo.png", oversized, "image/png")},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 413
    assert response.json()["status"] == "error"


def test_upload_rejects_a_file_whose_real_bytes_dont_match_its_claimed_type():
    # The core requirement: a file claiming (via filename AND
    # Content-Type header) to be a JPEG, but whose actual bytes are
    # plain text - the real-type check must catch this regardless.
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    profile = Profile(id=uuid.uuid4(), user_id=user.id, full_name="Alice")
    _override_auth(user, profile)

    try:
        response = client.post(
            f"/profiles/{profile.id}/reports",
            files={
                "file": (
                    "totally_a_real_photo.jpg",
                    b"this is just plain text, not a jpeg",
                    "image/jpeg",
                )
            },
        )
    finally:
        _clear_overrides()

    assert response.status_code == 415
    assert response.json()["status"] == "error"


def test_upload_rejects_someone_elses_profile():
    # require_owned_row already 404s for a profile you don't own
    # (proven generically in Task 12) - this just confirms the upload
    # route actually uses that guard rather than skipping it.
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    app.dependency_overrides[get_current_user] = lambda: user
    # Deliberately NOT overriding require_owned_profile - it will try a
    # real (fake, localhost) database lookup and fail fast, which is a
    # fine proxy for "not overridden" here since we only care that
    # SOME rejection happens before any file processing.
    try:
        response = client.post(
            f"/profiles/{uuid.uuid4()}/reports",
            files={"file": ("photo.png", _REAL_PNG_BYTES, "image/png")},
        )
    finally:
        _clear_overrides()

    assert response.status_code in (404, 503)


def test_upload_succeeds_for_a_real_valid_png():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    profile = Profile(id=uuid.uuid4(), user_id=user.id, full_name="Alice")
    _override_auth(user, profile)

    png_bytes = _make_real_png_bytes(64, 48)
    fake_db = MagicMock()
    fake_job = Job(id=uuid.uuid4(), report_id=uuid.uuid4(), job_type="ocr_extraction")
    fake_job.status = QUEUED

    from app.auth.dependencies import get_db

    def fake_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = fake_get_db

    try:
        with (
            patch("app.routers.reports.upload_file_bytes") as mock_upload,
            patch(
                "app.routers.reports.create_and_enqueue_job", return_value=fake_job
            ) as mock_create_job,
        ):
            response = client.post(
                f"/profiles/{profile.id}/reports",
                files={"file": ("photo.png", png_bytes, "image/png")},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["mime_type"] == "image/png"
    assert body["data"]["file_size_bytes"] == len(png_bytes)
    assert body["data"]["original_width"] == 64
    assert body["data"]["original_height"] == 48
    assert body["data"]["job_id"] == str(fake_job.id)
    assert body["data"]["job_status"] == QUEUED

    # R2 was called with the file's REAL bytes, unmodified, and a
    # storage key that's not derived from anything the client sent.
    mock_upload.assert_called_once()
    called_key, called_bytes, called_content_type = mock_upload.call_args[0]
    assert called_bytes == png_bytes
    assert called_content_type == "image/png"
    assert called_key.startswith(f"reports/{profile.id}/")
    assert called_key.endswith(".png")

    # A job was created for the report that was actually just made.
    mock_create_job.assert_called_once()
    called_db, called_report_id = mock_create_job.call_args[0][:2]
    assert called_db is fake_db
    assert mock_create_job.call_args[1]["job_type"] == "ocr_extraction"


# --- POST /reports/{row_id}/retry ---


def test_retry_requires_login():
    response = client.post(f"/reports/{uuid.uuid4()}/retry")

    assert response.status_code == 401


def test_retry_rejects_someone_elses_report():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    app.dependency_overrides[get_current_user] = lambda: user
    # Deliberately NOT overriding require_owned_report - same reasoning
    # as the upload ownership test: it hits a real (fake, localhost) DB
    # lookup and fails fast, which is a fine proxy for "not overridden".
    try:
        response = client.post(f"/reports/{uuid.uuid4()}/retry")
    finally:
        _clear_overrides()

    assert response.status_code in (404, 503)


def test_retry_returns_404_when_the_report_has_no_job():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4(), status=FAILED)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_report] = lambda: report

    try:
        with patch("app.routers.reports.get_latest_job_for_report", return_value=None):
            response = client.post(f"/reports/{report.id}/retry")
    finally:
        _clear_overrides()

    assert response.status_code == 404


def test_retry_returns_409_when_the_job_is_not_actually_failed():
    # The core requirement: retrying only makes sense for a job that's
    # genuinely "failed" - the global JobNotRetryableError handler
    # turns this into a clear 409, not a crash.
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4(), status="processing")
    job = Job(id=uuid.uuid4(), report_id=report.id, job_type="ocr_extraction")
    job.status = COMPLETED
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_report] = lambda: report

    try:
        with (
            patch("app.routers.reports.get_latest_job_for_report", return_value=job),
            patch(
                "app.routers.reports.retry_failed_job",
                side_effect=JobNotRetryableError(
                    "Job is 'completed', not 'failed' - "
                    "only a failed job can be retried."
                ),
            ),
        ):
            response = client.post(f"/reports/{report.id}/retry")
    finally:
        _clear_overrides()

    assert response.status_code == 409
    assert response.json()["status"] == "error"


def test_retry_succeeds_for_a_genuinely_failed_job():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4(), status=FAILED)
    old_job = Job(id=uuid.uuid4(), report_id=report.id, job_type="ocr_extraction")
    old_job.status = FAILED
    retried_job = Job(id=old_job.id, report_id=report.id, job_type="ocr_extraction")
    retried_job.status = QUEUED

    fake_db = MagicMock()
    from app.auth.dependencies import get_db

    def fake_get_db():
        yield fake_db

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_report] = lambda: report
    app.dependency_overrides[get_db] = fake_get_db

    try:
        with (
            patch(
                "app.routers.reports.get_latest_job_for_report", return_value=old_job
            ),
            patch(
                "app.routers.reports.retry_failed_job", return_value=retried_job
            ) as mock_retry,
        ):
            response = client.post(f"/reports/{report.id}/retry")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["job_id"] == str(retried_job.id)
    assert body["data"]["job_status"] == QUEUED
    mock_retry.assert_called_once_with(fake_db, old_job.id)


# --- GET /reports/{row_id} ---


def test_get_report_requires_login():
    response = client.get(f"/reports/{uuid.uuid4()}")

    assert response.status_code == 401


def test_get_report_rejects_someone_elses_report():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    app.dependency_overrides[get_current_user] = lambda: user
    # Same reasoning as the retry route's equivalent test: not
    # overriding require_owned_report hits a real (fake, localhost) DB
    # lookup and fails fast - a fine proxy for "not overridden".
    try:
        response = client.get(f"/reports/{uuid.uuid4()}")
    finally:
        _clear_overrides()

    assert response.status_code in (404, 503)


def test_get_report_returns_the_reports_status_and_its_latest_job():
    report = Report(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        status="processing",
        original_filename="labs.pdf",
        mime_type="application/pdf",
        created_at=datetime.now(timezone.utc),
    )
    job = Job(id=uuid.uuid4(), report_id=report.id, job_type="ocr_extraction")
    job.status = PROCESSING
    app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
    app.dependency_overrides[require_owned_report] = lambda: report

    try:
        with patch("app.routers.reports.get_latest_job_for_report", return_value=job):
            response = client.get(f"/reports/{report.id}")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["id"] == str(report.id)
    assert body["status"] == "processing"
    assert body["original_filename"] == "labs.pdf"
    assert body["job_id"] == str(job.id)
    assert body["job_status"] == PROCESSING
    assert body["job_error_message"] is None


def test_get_report_tells_review_required_apart_from_still_processing():
    # report.status stays "processing" while a job is review_required
    # (see app/jobs/service.py) - the frontend needs job_status, not
    # just report.status, to show the right screen.
    report = Report(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        status="processing",
        original_filename="labs.pdf",
        mime_type="application/pdf",
        created_at=datetime.now(timezone.utc),
    )
    job = Job(id=uuid.uuid4(), report_id=report.id, job_type="ocr_extraction")
    job.status = REVIEW_REQUIRED
    app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
    app.dependency_overrides[require_owned_report] = lambda: report

    try:
        with patch("app.routers.reports.get_latest_job_for_report", return_value=job):
            response = client.get(f"/reports/{report.id}")
    finally:
        _clear_overrides()

    assert response.json()["data"]["job_status"] == REVIEW_REQUIRED


def test_get_report_surfaces_the_jobs_error_message_when_failed():
    report = Report(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        status=FAILED,
        original_filename="labs.pdf",
        mime_type="application/pdf",
        created_at=datetime.now(timezone.utc),
    )
    job = Job(id=uuid.uuid4(), report_id=report.id, job_type="ocr_extraction")
    job.status = FAILED
    job.error_message = "OCR provider timed out."
    app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
    app.dependency_overrides[require_owned_report] = lambda: report

    try:
        with patch("app.routers.reports.get_latest_job_for_report", return_value=job):
            response = client.get(f"/reports/{report.id}")
    finally:
        _clear_overrides()

    assert response.json()["data"]["job_error_message"] == "OCR provider timed out."


def test_get_report_handles_no_job_existing_yet():
    report = Report(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        status="uploaded",
        original_filename="labs.pdf",
        mime_type="application/pdf",
        created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
    app.dependency_overrides[require_owned_report] = lambda: report

    try:
        with patch("app.routers.reports.get_latest_job_for_report", return_value=None):
            response = client.get(f"/reports/{report.id}")
    finally:
        _clear_overrides()

    body = response.json()["data"]
    assert body["job_id"] is None
    assert body["job_status"] is None


# --- GET /profiles/{row_id}/reports ---


def test_list_reports_for_profile_requires_login():
    response = client.get(f"/profiles/{uuid.uuid4()}/reports")

    assert response.status_code == 401


def test_list_reports_for_profile_returns_each_reports_status():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    profile = Profile(id=uuid.uuid4(), user_id=user.id, full_name="Alice")
    older_report = Report(
        id=uuid.uuid4(),
        profile_id=profile.id,
        status=COMPLETED,
        original_filename="old.pdf",
        mime_type="application/pdf",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    newer_report = Report(
        id=uuid.uuid4(),
        profile_id=profile.id,
        status="processing",
        original_filename="new.pdf",
        mime_type="application/pdf",
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
    )
    fake_db = MagicMock()
    query_chain = fake_db.query.return_value.filter.return_value.order_by.return_value
    query_chain.all.return_value = [newer_report, older_report]

    from app.auth.dependencies import get_db

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_profile] = lambda: profile
    app.dependency_overrides[get_db] = lambda: fake_db

    def fake_latest_job(db, report_id):
        return None

    try:
        with patch(
            "app.routers.reports.get_latest_job_for_report", side_effect=fake_latest_job
        ):
            response = client.get(f"/profiles/{profile.id}/reports")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()["data"]
    assert [row["id"] for row in body] == [str(newer_report.id), str(older_report.id)]
    assert body[0]["status"] == "processing"
    assert body[1]["status"] == COMPLETED
