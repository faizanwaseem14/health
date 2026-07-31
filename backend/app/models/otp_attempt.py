"""
The `otp_attempts` table: one row per phone-verification or account-
recovery attempt. Used for two things later:
  - Task 10: rate limiting OTP requests (max 5 per phone number per hour)
  - Task 11: logging every recovery-code attempt

We track by phone number (not user_id) because some attempts happen
before we know who the user is yet - e.g. someone mistyping a number, or
trying a recovery code for a phone with no account.
"""

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class OtpAttempt(Base):
    __tablename__ = "otp_attempts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # E.164 phone number this attempt was for. Always set, even if we
    # never find/create a matching user (e.g. a mistyped number).
    phone_number = Column(String, nullable=False, index=True)

    # "otp_verify" (Task 9/10) or "recovery_code" (Task 11).
    attempt_type = Column(String, nullable=False)

    # Filled in only if the attempt succeeded and we know who the user is.
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    success = Column(Boolean, nullable=False)
    ip_address = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
