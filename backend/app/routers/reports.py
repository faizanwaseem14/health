"""
Report upload. This is the very first step of the (future) OCR
pipeline: get a file safely onto the server, prove what it actually is,
store it untouched, and record enough about it to prove later that
nothing was tampered with. Nothing here reads the file's CONTENTS (no
OCR, no AI) - that's a later day's work.
"""

import hashlib
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.auth.ownership import require_owned_row
from app.core.audit import record_audit_event
from app.core.responses import success_response
from app.jobs.service import (
    create_and_enqueue_job,
    get_latest_job_for_report,
    retry_failed_job,
)
from app.models import Job, Profile, Report, User
from app.schemas.reports import ReportRenamePayload
from app.storage.file_validation import (
    EXTENSION_BY_MIME_TYPE,
    read_upload_within_size_limit,
    validate_file_type,
)
from app.storage.image_metadata import get_image_dimensions
from app.storage.r2 import delete_file_bytes, upload_file_bytes
from app.trends.service import compute_report_trends

logger = logging.getLogger("medvault")

router = APIRouter()

# Defined once so tests can override this EXACT dependency object (see
# tests/test_reports.py) - require_owned_row(...) builds a new function
# each time it's called, so the route and any test overriding it need
# to share this same instance.
require_owned_profile = require_owned_row(Profile)
require_owned_report = require_owned_row(Report)


@router.post("/profiles/{row_id}/reports")
async def upload_report(
    request: Request,
    file: UploadFile = File(...),
    profile: Profile = Depends(require_owned_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: uploads one report file (JPEG/PNG/HEIC/PDF, max
    25MB) under a profile the logged-in user owns.

    What this does NOT do, on purpose: read the file's contents, run
    OCR, or call any AI. It validates the file is real and safe, stores
    the ORIGINAL bytes in R2 completely untouched, and records a
    fingerprint of it (checksum, size, dimensions) in the reports table.
    If compression or any other processing is ever added later, it must
    happen on a separate copy - never on this original.
    """
    # Reads the file's bytes, stopping early if it's over the limit -
    # so we never buffer an enormous file just to reject it.
    file_bytes = await read_upload_within_size_limit(file)

    # The REAL type, from the file's own bytes - never from the
    # filename or the Content-Type header the client sent.
    mime_type = validate_file_type(file_bytes)

    checksum = hashlib.sha256(file_bytes).hexdigest()
    dimensions = get_image_dimensions(file_bytes)  # None for PDFs
    width, height = dimensions if dimensions else (None, None)

    extension = EXTENSION_BY_MIME_TYPE[mime_type]
    storage_key = f"reports/{profile.id}/{uuid.uuid4()}{extension}"

    # The untouched original, stored exactly as received.
    upload_file_bytes(storage_key, file_bytes, mime_type)

    report = Report(
        profile_id=profile.id,
        uploaded_by_user_id=user.id,
        storage_key=storage_key,
        original_filename=file.filename or "upload",
        mime_type=mime_type,
        file_size_bytes=len(file_bytes),
        original_checksum=checksum,
        original_width=width,
        original_height=height,
        status="uploaded",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    record_audit_event(
        db,
        action="upload_report",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="report",
        resource_id=report.id,
        user_agent=request.headers.get("user-agent"),
    )

    # Puts a background job on the queue for the OCR pipeline (later
    # groups). This ALWAYS succeeds from the upload's point of view: the
    # file is already safely stored above, so even if putting the job on
    # the Redis queue fails, create_and_enqueue_job() doesn't raise -
    # the job just stays "queued" and gets retried automatically in the
    # background. The user should never see an error here just because
    # a queue hiccuped.
    job = create_and_enqueue_job(db, report.id, job_type="ocr_extraction")

    return success_response(
        {
            "id": str(report.id),
            "status": report.status,
            "mime_type": report.mime_type,
            "file_size_bytes": report.file_size_bytes,
            "original_width": report.original_width,
            "original_height": report.original_height,
            "original_checksum": report.original_checksum,
            "job_id": str(job.id),
            "job_status": job.status,
        },
        status_code=201,
    )


def _report_response(report: Report, job: Job | None) -> dict:
    return {
        "id": str(report.id),
        "profile_id": str(report.profile_id),
        "status": report.status,
        "original_filename": report.original_filename,
        "display_name": report.display_name,
        "mime_type": report.mime_type,
        "created_at": report.created_at.isoformat(),
        "job_id": str(job.id) if job else None,
        # A job stuck at "review_required" leaves report.status at
        # "processing" (see app/jobs/service.py) - the frontend needs
        # job_status, not just report.status, to tell that case apart
        # from genuinely still-processing.
        "job_status": job.status if job else None,
        "job_error_message": job.error_message if job else None,
    }


@router.get("/reports/{row_id}")
def get_report(
    report: Report = Depends(require_owned_report),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: the current status of one report and its latest
    processing job - what the frontend polls while a report is
    uploading/processing, including after the user has navigated away
    and come back.
    """
    job = get_latest_job_for_report(db, report.id)
    return success_response(_report_response(report, job))


@router.get("/profiles/{row_id}/reports")
def list_reports_for_profile(
    profile: Profile = Depends(require_owned_profile),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: every report ever uploaded under a profile the
    logged-in user owns, most recent first - lets the frontend show a
    profile's upload history and let someone jump back into a report
    that's still processing.
    """
    reports = (
        db.query(Report)
        .filter(Report.profile_id == profile.id)
        .order_by(Report.created_at.desc())
        .all()
    )
    # One extra query per report to find its latest job - fine at this
    # scale (a person's own lab reports, not a bulk listing); worth
    # batching only if that ever changes.
    data = [
        _report_response(report, get_latest_job_for_report(db, report.id))
        for report in reports
    ]
    return success_response(data)


@router.post("/reports/{row_id}/retry")
def retry_report_processing(
    request: Request,
    report: Report = Depends(require_owned_report),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: retries processing for a report whose job ended up
    "failed" after exhausting its retries. This only resets and
    re-queues the background job - the original file in R2 is
    completely untouched by this and does NOT need to be re-uploaded.

    Returns 409 (via the global error handler) if the report's job
    isn't actually "failed" - e.g. it's still processing, or already
    finished - since retrying something that isn't broken isn't a
    legitimate retry.
    """
    job = get_latest_job_for_report(db, report.id)
    if job is None:
        raise HTTPException(
            status_code=404, detail="No processing job found for this report."
        )

    job = retry_failed_job(db, job.id)

    record_audit_event(
        db,
        action="retry_report_processing",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="report",
        resource_id=report.id,
        user_agent=request.headers.get("user-agent"),
    )

    return success_response(
        {
            "id": str(report.id),
            "status": report.status,
            "job_id": str(job.id),
            "job_status": job.status,
        }
    )


@router.patch("/reports/{row_id}")
def rename_report(
    request: Request,
    payload: ReportRenamePayload,
    report: Report = Depends(require_owned_report),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: gives a report a user-chosen display name (e.g.
    "IMG_4821.jpg" -> "Blood work - March"). original_filename is never
    touched - it stays the Task 6 integrity record of what was actually
    uploaded; display_name is purely a label on top of it.
    """
    report.display_name = payload.display_name.strip()
    db.commit()
    db.refresh(report)

    record_audit_event(
        db,
        action="rename_report",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="report",
        resource_id=report.id,
        user_agent=request.headers.get("user-agent"),
    )

    job = get_latest_job_for_report(db, report.id)
    return success_response(_report_response(report, job))


@router.delete("/reports/{row_id}")
def delete_report(
    request: Request,
    report: Report = Depends(require_owned_report),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: permanently deletes a report and everything
    derived from it (results, corrections, explanations, OCR evidence,
    jobs - all ON DELETE CASCADE at the database level from report_id/
    result_id). The audit log entry for this delete is the one thing
    that survives, by design (append-only, and never a health value).

    The database row is removed FIRST, inside a normal transaction that
    can still roll back on failure; the underlying R2 object is only
    deleted after that commit succeeds. If the R2 delete itself fails
    (network hiccup), it's logged and swallowed rather than failing the
    request - the user's data is already correctly gone from their own
    account either way, and a stray orphaned blob nobody can reach
    isn't worth blocking on.
    """
    report_id = report.id
    storage_key = report.storage_key

    db.delete(report)
    db.commit()

    record_audit_event(
        db,
        action="delete_report",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="report",
        resource_id=report_id,
        user_agent=request.headers.get("user-agent"),
    )

    try:
        delete_file_bytes(storage_key)
    except Exception:
        logger.exception(
            "Failed to delete R2 object %r after report delete", storage_key
        )

    return success_response({"id": str(report_id)})


@router.get("/reports/{row_id}/trends")
def get_report_trends(
    report: Report = Depends(require_owned_report),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: for every test in THIS report that's resolved to
    the test-name catalog (test_alias_id set - an unresolved raw name
    can't be safely grouped with anything from another report), returns
    its value across EVERY report in the same profile, in report-upload
    order. See app/trends/service.py for exactly what counts as a
    genuinely comparable point vs. an excluded one.
    """
    return success_response(
        {"report_id": str(report.id), "tests": compute_report_trends(db, report)}
    )
