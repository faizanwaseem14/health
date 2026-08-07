"""
The `result_ocr_words` table: links one extracted result (a later day's
AI extraction work) to the exact OCR word(s) it was read from - the
"trace back to exact text and position" piece of the trust chain. A
single result can span more than one OCR word (e.g. "13.5" and "g/dL"
as two separate words feeding one result), hence a many-to-many join
table rather than a single foreign key column on either side.

Nothing writes to this table yet - AI extraction (the only thing that
would populate it) is explicitly not built in this group. It exists now
so that capability is ready and already tested (see
test_ocr_evidence.py), instead of retrofitting traceability later.
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class ResultOcrWord(Base):
    __tablename__ = "result_ocr_words"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    result_id = Column(
        UUID(as_uuid=True),
        ForeignKey("results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ocr_word_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ocr_words.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    result = relationship("Result", back_populates="ocr_word_links")
    ocr_word = relationship("OcrWord")
