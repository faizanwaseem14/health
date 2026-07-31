"""
The `audit_log` table: an APPEND-ONLY record of who accessed or changed
what. Nothing ever updates or deletes rows here - only inserts.

Hard rule: this table must NEVER contain health values or report
contents - only metadata about the access itself (who, when, from where,
what action). See Task 13 for the helper that writes to this table.
"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    # A plain auto-incrementing integer is fine here (and cheaper than a
    # UUID) - audit rows are never looked up by ID from a public URL, so
    # there's no need to hide how many rows exist.
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Nullable because some events happen before we know who the user is,
    # e.g. a failed login attempt.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # e.g. "login", "view_report", "download_report".
    action = Column(String, nullable=False)
    # What kind of thing was acted on, e.g. "report", "profile".
    resource_type = Column(String, nullable=True)
    resource_id = Column(UUID(as_uuid=True), nullable=True)

    ip_address = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
