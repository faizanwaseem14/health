"""
The `corrections` table: an audit trail of manual edits a user makes to
an extracted result (e.g. fixing a typo OCR introduced). Nothing writes
to this table yet - the correction UI comes on a later day.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    corrected_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Which column on `results` this correction changed, e.g. "value".
    field_name = Column(String, nullable=False)
    previous_value = Column(String, nullable=True)
    new_value = Column(String, nullable=False)
    reason = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
