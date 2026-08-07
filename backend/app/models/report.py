"""
The `reports` table: one row per uploaded file (e.g. a lab PDF or a photo
of a prescription).

Nothing here handles the actual upload yet (that's Task 7 - signed URLs)
or reads the file's contents (that's OCR, a later day). Today this table
just has a place to record WHERE the file lives and PROVE it hasn't been
tampered with (Task 6's integrity fields, below).
"""

import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Whose health record this report belongs to.
    profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Who actually performed the upload (usually the profile owner, but
    # kept separate in case a family account uploads on someone's behalf).
    uploaded_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- Where the file lives (Cloudflare R2) ---
    storage_key = Column(String, nullable=False)

    # --- File integrity fields (Task 6) ---
    # These let us prove the file we show you later is EXACTLY the file
    # that was uploaded - nothing corrupted or swapped in between.
    original_filename = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    # SHA-256 hex digest of the original file's bytes.
    original_checksum = Column(String, nullable=False)
    # Only meaningful for image uploads; NULL for PDFs etc.
    original_width = Column(Integer, nullable=True)
    original_height = Column(Integer, nullable=True)

    # A free-text label like "lab_result" or "prescription" - just a
    # note for now; nothing reads or enforces this yet.
    report_type = Column(String, nullable=True)
    # The date printed ON the report itself (not the upload date).
    report_date = Column(Date, nullable=True)

    # "uploaded" -> "processing" -> "processed" or "failed", kept in
    # sync with the report's OCR job (see app/jobs/service.py).
    status = Column(String, nullable=False, default="uploaded")

    # Which AI model and prompt version produced this report's results
    # (see app/ai/prompt.py) - set once extraction succeeds, so every
    # processed report can be traced back to exactly what produced it.
    extraction_model = Column(String, nullable=True)
    extraction_prompt_version = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    profile = relationship("Profile", back_populates="reports")
    results = relationship(
        "Result", back_populates="report", cascade="all, delete-orphan"
    )
    ocr_words = relationship(
        "OcrWord", back_populates="report", cascade="all, delete-orphan"
    )
