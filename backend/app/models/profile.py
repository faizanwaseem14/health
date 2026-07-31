"""
The `profiles` table: one row per PERSON whose health records are being
tracked. A profile might be the account holder themselves, or a
dependent they manage (e.g. a child or parent).

Reports, results, etc. all belong to a profile - not directly to a user -
so that one login can manage records for a whole family.
"""

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who owns/manages this profile (who can see and edit it).
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    full_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)

    # e.g. "self", "child", "parent", "spouse", "other" - free text set
    # by the user, not restricted to a fixed list here.
    relationship_to_owner = Column(String, nullable=False, default="self")

    sex = Column(String, nullable=True)
    blood_type = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="profiles")
    reports = relationship(
        "Report", back_populates="profile", cascade="all, delete-orphan"
    )
