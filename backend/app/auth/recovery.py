"""
Backup account recovery: a one-time code a user generates while logged
in (via phone), then can use later to prove who they are if they lose
access to that phone number.

We only ever store a HASH of the code, never the code itself - so even
someone with full database access can't read out anyone's recovery
code. Every attempt to USE a recovery code gets logged in otp_attempts,
whether it succeeds or fails.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import OtpAttempt, User

# Characters chosen to avoid visual mix-ups when someone copies the code
# down by hand: no 0/O, no 1/I/L.
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CODE_GROUP_SIZE = 4
_CODE_GROUPS = 4


class RecoveryCodeInvalidError(Exception):
    """Raised when a recovery attempt doesn't match a real, unused code."""


def _generate_code() -> str:
    """
    A random code like "A3F9-7K2M-QXZ1-8BCD" - 16 characters from a
    32-symbol alphabet is 80 bits of randomness, far beyond what anyone
    could realistically guess.
    """
    groups = [
        "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_GROUP_SIZE))
        for _ in range(_CODE_GROUPS)
    ]
    return "-".join(groups)


def _hash_code(code: str) -> str:
    """
    One-way hash of a recovery code. Recovery codes are long, random,
    and machine-generated (not something a person picks), so - unlike a
    memorized password - a plain SHA-256 hash is considered strong
    enough here: there's no realistic dictionary/guessing attack against
    80 bits of randomness.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def generate_recovery_code(user: User, db: Session) -> str:
    """
    Creates a brand new one-time recovery code for an ALREADY-LOGGED-IN
    user (call this from a route protected by get_current_user).

    Returns the real code in plain text - this is the ONLY moment it
    ever exists outside the user's own hands; only its hash is saved.
    Generating a new code replaces (invalidates) any previous one.
    """
    code = _generate_code()

    user.recovery_code_hash = _hash_code(code)
    user.recovery_code_created_at = datetime.now(timezone.utc)
    user.recovery_code_used_at = None  # a freshly generated code is always unused
    db.commit()

    return code


def _record_attempt(
    db: Session,
    phone_number: str,
    success: bool,
    user: User | None,
    ip_address: str | None,
) -> None:
    db.add(
        OtpAttempt(
            phone_number=phone_number,
            attempt_type="recovery_code",
            user_id=user.id if user else None,
            success=success,
            ip_address=ip_address,
        )
    )
    db.commit()


def redeem_recovery_code(
    phone_number: str, code: str, db: Session, ip_address: str | None = None
) -> User:
    """
    Checks a recovery code typed in by someone who's lost access to
    their phone. ALWAYS logs the attempt, success or failure.

    Raises RecoveryCodeInvalidError for any failure - wrong phone
    number, wrong code, or a code that's already been used - without
    saying which, so a wrong guess doesn't help narrow down the truth.
    """
    user = db.query(User).filter(User.phone_number == phone_number).first()

    no_active_code = (
        user is None
        or not user.recovery_code_hash
        or user.recovery_code_used_at is not None
    )
    if no_active_code:
        _record_attempt(
            db, phone_number, success=False, user=user, ip_address=ip_address
        )
        raise RecoveryCodeInvalidError("Invalid phone number or recovery code.")

    # Constant-time comparison, so a mistyped code can't be brute-forced
    # faster by timing how quickly each wrong guess gets rejected.
    if not hmac.compare_digest(user.recovery_code_hash, _hash_code(code)):
        _record_attempt(
            db, phone_number, success=False, user=user, ip_address=ip_address
        )
        raise RecoveryCodeInvalidError("Invalid phone number or recovery code.")

    user.recovery_code_used_at = datetime.now(timezone.utc)
    db.commit()
    _record_attempt(db, phone_number, success=True, user=user, ip_address=ip_address)

    return user
