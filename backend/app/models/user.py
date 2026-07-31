"""
The `users` table: one row per login identity (a phone number that has
verified with Firebase).

A user can manage one or more `profiles` - themselves, plus maybe a
child or parent they take care of. Login/auth info lives here on `users`;
actual health data lives under `profiles`.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The unique ID Firebase assigns after verifying a phone number.
    firebase_uid = Column(String, unique=True, nullable=False, index=True)

    # E.164 format, e.g. "+15551234567".
    phone_number = Column(String, unique=True, nullable=False, index=True)

    # Lets us disable an account without deleting its data.
    is_active = Column(Boolean, nullable=False, default=True)

    # --- Backup recovery code (Task 11) ---
    # A one-time code the user can use to regain access if they lose
    # their phone. We only ever store its HASH, never the code itself.
    recovery_code_hash = Column(String, nullable=True)
    recovery_code_created_at = Column(DateTime(timezone=True), nullable=True)
    # Set the moment the code is used - a recovery code only ever works once.
    recovery_code_used_at = Column(DateTime(timezone=True), nullable=True)

    last_login_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    profiles = relationship(
        "Profile", back_populates="user", cascade="all, delete-orphan"
    )
