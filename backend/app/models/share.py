"""
The `shares` table: a temporary, revocable link for sharing a report
(or a chosen subset of its results - see share_result.py) with someone
else, e.g. a doctor, read-only and without a HealthVault account. See
app/sharing/service.py for how a share is created and how a token
resolves to one.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Share(Base):
    __tablename__ = "shares"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Every share created today is scoped to exactly one report -
    # nullable at the DB level only because a future whole-profile share
    # was speculatively designed for here; app.sharing.service always
    # sets it.
    report_id = Column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=True
    )
    shared_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # A random, unguessable token used in the share URL.
    share_token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    access_count = Column(Integer, nullable=False, default=0)
    # None = unlimited views; otherwise the share is denied once
    # access_count reaches this.
    max_views = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
