"""
Auth-related routes: logging in (Task 9), OTP rate limiting (Task 10),
and backup recovery codes (Task 11). All grouped under the "/auth"
prefix so it's obvious at a glance which routes need identity checks.

None of these routes catch their own errors anymore (Task 15) - the
global error handler in app/core/errors.py turns
OtpRateLimitExceededError / RecoveryCodeInvalidError / database errors
into the right status code and a clean message everywhere, once.
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.auth.firebase import delete_firebase_user
from app.auth.rate_limit import check_and_record_otp_request
from app.auth.recovery import generate_recovery_code, redeem_recovery_code
from app.core.audit import record_audit_event
from app.core.responses import success_response
from app.database import commit_with_retry
from app.models import Profile, Report, User
from app.schemas.auth import OtpRequestPayload, RecoveryCodeRedeemPayload
from app.storage.r2 import delete_file_bytes

logger = logging.getLogger("medvault")

router = APIRouter(prefix="/auth")


@router.post("/otp/request")
def request_otp(
    payload: OtpRequestPayload, request: Request, db: Session = Depends(get_db)
):
    """
    PUBLIC route. Called by the frontend BEFORE it asks Firebase to text
    a one-time code to this phone number. This does NOT send any SMS
    itself - that stays Firebase's job, on the frontend, on a later day.
    All this route does is check (and record) whether this phone number
    has requested too many codes recently, so we can say no before
    Firebase ever sends a text.
    """
    client_ip = request.client.host if request.client else None
    check_and_record_otp_request(payload.phone_number, db, ip_address=client_ip)
    return success_response()


@router.get("/me")
def read_current_user(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: requires a valid Firebase ID token in the
    "Authorization: Bearer <token>" header. Proves Task 9's login flow
    end to end - verify the token, then look up (or create) the matching
    MedVault user.
    """
    record_audit_event(
        db,
        action="view_own_profile",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        user_agent=request.headers.get("user-agent"),
    )
    return success_response(
        {"id": str(user.id), "phone_number": user.phone_number, "email": user.email}
    )


@router.post("/recovery/generate")
def generate_recovery_code_route(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    PROTECTED route: an already-logged-in user asks for a backup
    recovery code. Returns the real code exactly once - after this
    response, only its hash is stored, so save it somewhere safe now.
    Generating a new code invalidates any earlier one.
    """
    code = generate_recovery_code(user, db)
    return success_response({"recovery_code": code})


@router.post("/recovery/redeem")
def redeem_recovery_code_route(
    payload: RecoveryCodeRedeemPayload, request: Request, db: Session = Depends(get_db)
):
    """
    PUBLIC route: lets someone who's lost access to their phone prove
    who they are with a saved recovery code instead. Every attempt is
    logged, whether it succeeds or fails.
    """
    client_ip = request.client.host if request.client else None
    user = redeem_recovery_code(
        payload.phone_number, payload.recovery_code, db, ip_address=client_ip
    )
    return success_response({"id": str(user.id), "phone_number": user.phone_number})


@router.delete("/me")
def delete_account_route(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: permanently deletes this account and EVERYTHING
    under it - every profile the user owns, and everything derived
    from each one (reports, results, corrections, explanations, OCR
    evidence, jobs, share links - all ON DELETE CASCADE at the database
    level from `users`, the same chain a single report's delete already
    relies on, just starting one level higher).

    Order matters here in a way a single report's delete didn't need to
    worry about: the audit log entry for this delete is written AFTER
    the user row is gone, with user_id=None - inserting it beforehand
    with user_id=user.id would be fine too, but None is the more
    honest statement of what's actually true once this commits (the
    account that did this no longer exists - see audit_log.user_id's
    ON DELETE SET NULL, the same thing that already happens if this
    row outlives the user for any other reason).

    The database rows are removed FIRST, inside a transaction that can
    still roll back on failure; the R2 objects for every report this
    user had, and the Firebase Authentication identity itself, are only
    cleaned up after that commit succeeds - both best-effort (logged,
    never failing the request), exactly like a single report's R2
    cleanup, for the same reason: the account is already correctly gone
    from our own database either way.
    """
    user_id = user.id
    firebase_uid = user.firebase_uid
    storage_keys = [
        row.storage_key
        for row in db.query(Report.storage_key)
        .join(Profile, Profile.id == Report.profile_id)
        .filter(Profile.user_id == user_id)
        .all()
    ]

    commit_with_retry(db, lambda: db.delete(user))

    record_audit_event(
        db,
        action="delete_account",
        ip_address=request.client.host if request.client else "unknown",
        user_id=None,
        resource_type="user",
        resource_id=user_id,
        user_agent=request.headers.get("user-agent"),
    )

    for storage_key in storage_keys:
        try:
            delete_file_bytes(storage_key)
        except Exception:
            logger.exception(
                "Failed to delete R2 object %r during account deletion", storage_key
            )

    try:
        delete_firebase_user(firebase_uid)
    except Exception:
        logger.exception(
            "Failed to delete Firebase user %r during account deletion", firebase_uid
        )

    return success_response({"deleted": True})
