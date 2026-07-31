"""
The `test_aliases` table: maps messy, inconsistent test names as printed
on real lab reports (e.g. "Hgb", "HGB", "Hemoglobin") to one standard
name ("Hemoglobin"). Nothing populates or uses this yet - it exists so
`results.test_alias_id` has somewhere to point once normalization is
built.
"""

import uuid

from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class TestAlias(Base):
    __tablename__ = "test_aliases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The variant name as it might appear on a report.
    raw_name = Column(String, unique=True, nullable=False, index=True)
    # The one standardized name we group all variants under.
    canonical_name = Column(String, nullable=False, index=True)

    category = Column(String, nullable=True)
    default_unit = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
