"""
The `ocr_words` table: the RAW evidence OCR produced for a report - one
row per word, exactly as read off the page, before any AI or human
decides what it means. This is the ground truth every extracted value
(a later day's work) must trace back to.

Replaced wholesale, never appended to, when OCR runs again for the same
report (e.g. a retry) - see app/ocr/evidence.py.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.database import Base


class OcrWord(Base):
    __tablename__ = "ocr_words"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Which job produced this evidence - useful for debugging a
    # specific OCR run; kept even if that job row is later deleted.
    job_id = Column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )

    # 1-indexed - page 1 for a single photo, or the Nth page of a PDF.
    page_number = Column(Integer, nullable=False)
    # This word's position within its page, in reading order, starting
    # at 0 - lets the page's text be reconstructed in order without
    # relying on row insertion/query order.
    word_index = Column(Integer, nullable=False)

    text = Column(String, nullable=False)
    # 0.0-1.0 - how confident the OCR engine was in this exact word.
    confidence = Column(Numeric, nullable=False)
    # Four corner points [[x,y], [x,y], [x,y], [x,y]] (top-left,
    # top-right, bottom-right, bottom-left), in pixel coordinates of the
    # page image OCR actually ran on. A JSON column, not four separate
    # x/y columns, because this is fundamentally one geometric shape -
    # see app/ocr/types.py's BoundingBox for why 4 points, not a plain
    # rectangle.
    bounding_box = Column(JSONB, nullable=False)

    # Which OCR engine produced this row, e.g. "tesseract" - part of
    # the evidence trail: if a report is ever reprocessed with a
    # different provider, we know exactly which engine is responsible
    # for which word.
    ocr_provider = Column(String, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    report = relationship("Report", back_populates="ocr_words")
