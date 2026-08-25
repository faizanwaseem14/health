"""
The `share_results` table: when a share is scoped to specific results
(rather than a whole report), one row here per result included. No
rows at all for a share means "the whole report" - see
app/sharing/service.py.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ShareResult(Base):
    __tablename__ = "share_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    share_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shares.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
