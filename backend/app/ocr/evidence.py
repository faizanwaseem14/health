"""
Turns an in-memory OcrResult into durable rows in the `ocr_words` table
- the evidence trail every extracted value will trace back to - and the
small capability that links an extracted result to the exact OCR
word(s) it came from.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import OcrWord, ResultOcrWord
from app.ocr.types import OcrResult


def store_ocr_evidence(
    db: Session,
    *,
    report_id: UUID,
    job_id: UUID,
    provider_name: str,
    result: OcrResult,
) -> list[OcrWord]:
    """
    REPLACES whatever OCR evidence a report already has with a fresh
    set - not "adds to", because a retry re-runs OCR from scratch, and
    leaving stale words from a previous attempt sitting next to the new
    (correct) reading would just be confusing, contradictory evidence.

    `word_index` (a word's position within its page) is assigned here,
    from the order words appear in `result.words` - both providers
    already produce words in reading order, so this reconstructs each
    page's text correctly without the in-memory OcrWord needing to
    track its own index.
    """
    db.query(OcrWord).filter(OcrWord.report_id == report_id).delete()

    page_word_counts: dict[int, int] = {}
    rows = []
    for word in result.words:
        word_index = page_word_counts.get(word.page_number, 0)
        page_word_counts[word.page_number] = word_index + 1
        rows.append(
            OcrWord(
                report_id=report_id,
                job_id=job_id,
                page_number=word.page_number,
                word_index=word_index,
                text=word.text,
                confidence=word.confidence,
                bounding_box=word.bounding_box.to_json(),
                ocr_provider=provider_name,
            )
        )

    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def link_result_to_ocr_words(
    db: Session, *, result_id: UUID, ocr_word_ids: list[UUID]
) -> list[ResultOcrWord]:
    """
    Records that an extracted result's value was read from these exact
    OCR words - the mechanism a later day's AI extraction will call so
    every value can trace back to its precise source text and position.

    Nothing calls this yet: AI extraction (the only thing that could
    know which OCR words a value came from) is explicitly not built in
    this group. This exists now, tested, so that day's work is "call
    this function" instead of "design and migrate a new table".
    """
    links = [
        ResultOcrWord(result_id=result_id, ocr_word_id=ocr_word_id)
        for ocr_word_id in ocr_word_ids
    ]
    db.add_all(links)
    db.commit()
    for link in links:
        db.refresh(link)
    return links
