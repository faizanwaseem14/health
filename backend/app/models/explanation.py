"""
The `explanations` table: a plain-language, AI-written explanation of a
report or a single result (e.g. "what does high cholesterol mean?").
Nothing generates these yet - that's Day 2+ AI work.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Explanation(Base):
    __tablename__ = "explanations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Exactly one of these two is expected to be set: a whole-report
    # summary, or an explanation of one specific result. Not enforced at
    # the database level yet since nothing writes here today.
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("results.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    content = Column(Text, nullable=False)
    # Which AI model produced this, e.g. "claude-sonnet-5" - useful for
    # future debugging/audits.
    model_used = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
