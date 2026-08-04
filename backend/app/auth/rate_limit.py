"""
OTP request rate limiting.

This stops one phone number from being hammered with repeated OTP
requests - which would spam someone with real text messages and cost
real money per SMS sent. Every request attempt gets logged in the
`otp_attempts` table (allowed or not); if a phone number has made too
many recent attempts, we block the request before it ever reaches
Firebase (which is what would actually send the text, on a later day).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import OtpAttempt

# The actual business rule (max 5 requests per phone number per hour),
# named here once instead of scattered as raw numbers through the code.
MAX_OTP_REQUESTS_PER_WINDOW = 5
OTP_RATE_LIMIT_WINDOW = timedelta(hours=1)


class OtpRateLimitExceededError(Exception):
    """Raised when a phone number has made too many OTP requests recently."""


def _recent_attempt_count(phone_number: str, db: Session) -> int:
    """How many "otp_request" attempts this phone number has made within the window."""
    window_start = datetime.now(timezone.utc) - OTP_RATE_LIMIT_WINDOW
    return (
        db.query(func.count(OtpAttempt.id))
        .filter(
            OtpAttempt.phone_number == phone_number,
            OtpAttempt.attempt_type == "otp_request",
            OtpAttempt.created_at >= window_start,
        )
        .scalar()
    )


def check_and_record_otp_request(
    phone_number: str, db: Session, ip_address: str | None = None
) -> None:
    """
    Call this BEFORE telling the frontend it's OK to ask Firebase to text
    a one-time code to this phone number.

    Always records this attempt (allowed or not) - that way, once a
    phone number is blocked, repeated hammering keeps counting against
    it instead of resetting. Raises OtpRateLimitExceededError if this
    phone number already has MAX_OTP_REQUESTS_PER_WINDOW or more
    requests within OTP_RATE_LIMIT_WINDOW.
    """
    already_over_limit = (
        _recent_attempt_count(phone_number, db) >= MAX_OTP_REQUESTS_PER_WINDOW
    )

    db.add(
        OtpAttempt(
            phone_number=phone_number,
            attempt_type="otp_request",
            success=not already_over_limit,
            ip_address=ip_address,
        )
    )
    db.commit()

    if already_over_limit:
        raise OtpRateLimitExceededError(
            "Too many OTP requests for this phone number. Try again later."
        )
