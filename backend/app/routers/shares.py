"""
Share links: a report (or a chosen subset of its results) exposed
read-only to anyone with the link - no HealthVault account required.
The four routes here split cleanly into "managing shares" (protected,
owned by the report's user - create, list, revoke, view access
history) and "using a share" (PUBLIC, no login - GET /public/shares/
{token}, the doctor-facing view).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.auth.ownership import require_owned_row
from app.core.audit import record_audit_event
from app.core.responses import success_response
from app.database import commit_with_retry
from app.models import AuditLog, Report, Result, Share, User
from app.routers.reports import require_owned_report
from app.schemas.shares import ShareCreatePayload
from app.sharing.service import (
    ShareUnavailableError,
    create_share,
    get_shared_report_data,
    resolve_share_access,
)

router = APIRouter()

require_owned_share = require_owned_row(Share)


def _share_status(share: Share) -> str:
    if share.revoked_at is not None:
        return "revoked"
    if share.expires_at <= datetime.now(timezone.utc):
        return "expired"
    if share.max_views is not None and share.access_count >= share.max_views:
        return "exhausted"
    return "active"


def _serialize_share(share: Share) -> dict:
    return {
        "id": str(share.id),
        "report_id": str(share.report_id),
        "share_token": share.share_token,
        "status": _share_status(share),
        "expires_at": share.expires_at.isoformat(),
        "max_views": share.max_views,
        "access_count": share.access_count,
        "created_at": share.created_at.isoformat(),
        "revoked_at": share.revoked_at.isoformat() if share.revoked_at else None,
    }


def _serialize_shared_result(result: Result) -> dict:
    return {
        "id": str(result.id),
        "raw_test_name": result.raw_test_name,
        "canonical_test_name": result.canonical_test_name,
        "value": result.value,
        "unit": result.unit,
        "reference_range_text": result.reference_range_text,
        "flag": result.flag,
    }


@router.post("/reports/{row_id}/shares", status_code=201)
def create_share_route(
    request: Request,
    payload: ShareCreatePayload,
    report: Report = Depends(require_owned_report),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: creates a share link for this report, optionally
    narrowed to specific results. Every id in `result_ids` (if given)
    must actually belong to this report - never trusted from the
    payload alone, since that's exactly the check standing between this
    endpoint and someone building a link that leaks a DIFFERENT
    report's results by guessing/reusing result ids.
    """
    if payload.result_ids:
        requested_ids = set(payload.result_ids)
        owned_ids = {
            row.id
            for row in db.query(Result.id).filter(
                Result.report_id == report.id, Result.id.in_(requested_ids)
            )
        }
        if owned_ids != requested_ids:
            raise HTTPException(
                status_code=422,
                detail="One or more result_ids don't belong to this report.",
            )

    share = create_share(
        db,
        profile_id=report.profile_id,
        report_id=report.id,
        shared_by_user_id=user.id,
        expires_in_days=payload.expires_in_days,
        max_views=payload.max_views,
        result_ids=payload.result_ids,
    )

    record_audit_event(
        db,
        action="create_share",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="share",
        resource_id=share.id,
        user_agent=request.headers.get("user-agent"),
    )

    return success_response(_serialize_share(share), status_code=201)


@router.get("/reports/{row_id}/shares")
def list_shares_route(
    report: Report = Depends(require_owned_report),
    db: Session = Depends(get_db),
):
    """PROTECTED route: every share ever created for this report, most
    recent first, each with its current status."""
    shares = (
        db.query(Share)
        .filter(Share.report_id == report.id)
        .order_by(Share.created_at.desc())
        .all()
    )
    return success_response([_serialize_share(share) for share in shares])


@router.delete("/shares/{row_id}")
def revoke_share_route(
    request: Request,
    share: Share = Depends(require_owned_share),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: revokes a share immediately - the very next
    attempt to use its link (even one already in flight, once this
    commits) is denied, since resolve_share_access re-checks
    revoked_at fresh on every access.
    """

    def apply_revoke():
        share.revoked_at = datetime.now(timezone.utc)

    commit_with_retry(db, apply_revoke)

    record_audit_event(
        db,
        action="revoke_share",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="share",
        resource_id=share.id,
        user_agent=request.headers.get("user-agent"),
    )

    return success_response(_serialize_share(share))


@router.get("/shares/{row_id}/accesses")
def list_share_accesses_route(
    share: Share = Depends(require_owned_share),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: every time this share's link was actually opened -
    from the append-only audit log (see app/core/audit.py), never a
    separately-editable table, so this history can't be quietly trimmed
    even by a bug elsewhere in the app.
    """
    accesses = (
        db.query(AuditLog)
        .filter(AuditLog.resource_type == "share", AuditLog.resource_id == share.id)
        .filter(AuditLog.action == "view_share")
        .order_by(AuditLog.created_at.desc())
        .all()
    )
    return success_response(
        [
            {
                "accessed_at": access.created_at.isoformat(),
                "ip_address": access.ip_address,
            }
            for access in accesses
        ]
    )


@router.get("/public/shares/{token}")
def view_shared_report_route(
    token: str, request: Request, db: Session = Depends(get_db)
):
    """
    PUBLIC route - no login, no HealthVault account. Resolves `token`
    to a currently-viewable share (denying it uniformly - see
    ShareUnavailableError - if it's unknown, revoked, expired, or over
    its view limit) and returns exactly the report/results data it was
    scoped to. Every successful view is recorded in the audit log
    (resource_type="share", action="view_share") - that's this route's
    entire access-history trail.
    """
    try:
        share = resolve_share_access(db, token)
    except ShareUnavailableError:
        raise HTTPException(
            status_code=404, detail="This link is no longer available."
        ) from None

    record_audit_event(
        db,
        action="view_share",
        ip_address=request.client.host if request.client else "unknown",
        resource_type="share",
        resource_id=share.id,
        user_agent=request.headers.get("user-agent"),
    )

    shared = get_shared_report_data(db, share)
    return success_response(
        {
            "report": {
                "display_name": shared.report.display_name,
                "original_filename": shared.report.original_filename,
                "report_date": (
                    shared.report.report_date.isoformat()
                    if shared.report.report_date
                    else None
                ),
                "created_at": shared.report.created_at.isoformat(),
            },
            "results": [_serialize_shared_result(result) for result in shared.results],
        }
    )
