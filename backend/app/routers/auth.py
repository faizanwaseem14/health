"""
Auth-related routes: logging in (Task 9), OTP rate limiting (Task 10),
and backup recovery codes (Task 11). All grouped under the "/auth"
prefix so it's obvious at a glance which routes need identity checks.

None of these routes catch their own errors anymore (Task 15) - the
global error handler in app/core/errors.py turns
OtpRateLimitExceededError / RecoveryCodeInvalidError / database errors
into the right status code and a clean message everywhere, once.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.auth.rate_limit import check_and_record_otp_request
from app.auth.recovery import generate_recovery_code, redeem_recovery_code
from app.core.audit import record_audit_event
from app.core.responses import success_response
from app.models import User
from app.schemas.auth import OtpRequestPayload, RecoveryCodeRedeemPayload

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
