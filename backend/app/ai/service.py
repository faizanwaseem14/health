"""
Orchestrates AI extraction for one report: build the prompt from its
stored OCR evidence, call Claude, and persist validated rows as Result
rows - linked back to their exact source OCR word(s) via
result_ocr_words, the mechanism app/ocr/evidence.py already built.

Nothing here decides medical meaning: reference ranges, values, and
names are stored exactly as Claude read them off the OCR text; nothing
is computed, flagged, or looked up. Whether the extraction actually
succeeded (vs. needs review, vs. a real API error) is for the caller
(the worker) to decide from what extract_structured_rows raises -
this module never swallows those exceptions.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.extraction import extract_structured_rows
from app.ai.prompt import (
    EXTRACTION_MODEL,
    EXTRACTION_PROMPT_VERSION,
    build_word_list_prompt,
)
from app.ai.schema import ExtractionResult
from app.models import OcrWord, Report, Result
from app.ocr.evidence import link_result_to_ocr_words


def run_extraction_for_report(
    db: Session, report: Report, job_id: UUID
) -> ExtractionResult:
    """
    Fetches the report's stored OCR words (in the same reading order
    they were stored in), sends them to Claude, and persists the
    validated result. Raises whatever extract_structured_rows raises -
    this function doesn't catch anything itself.
    """
    ocr_words = (
        db.query(OcrWord)
        .filter(OcrWord.report_id == report.id)
        .order_by(OcrWord.page_number, OcrWord.word_index)
        .all()
    )

    word_list_prompt = build_word_list_prompt(ocr_words)
    result = extract_structured_rows(word_list_prompt)

    _store_extraction(
        db, report=report, job_id=job_id, ocr_words=ocr_words, result=result
    )

    return result


def _store_extraction(
    db: Session,
    *,
    report: Report,
    job_id: UUID,
    ocr_words: list[OcrWord],
    result: ExtractionResult,
) -> None:
    # REPLACES any previous extraction for this report - same reasoning
    # as OCR evidence: a retry re-runs extraction from scratch, and old
    # rows sitting next to freshly-extracted ones would just be stale,
    # contradictory data.
    db.query(Result).filter(Result.report_id == report.id).delete()

    for row in result.rows:
        result_row = Result(
            report_id=report.id,
            job_id=job_id,
            raw_test_name=row.raw_test_name,
            canonical_test_name=row.canonical_test_name,
            value=row.value,
            unit=row.unit,
            reference_range_text=row.reference_range,
            result_date=row.date,
            lab_name=row.lab,
            ai_confidence=row.confidence,
        )
        db.add(result_row)
        db.flush()  # assigns result_row.id without a full commit

        word_ids = [
            ocr_words[index].id
            for index in row.evidence_word_indices
            if 0 <= index < len(ocr_words)
        ]
        if word_ids:
            link_result_to_ocr_words(db, result_id=result_row.id, ocr_word_ids=word_ids)

    report.extraction_model = EXTRACTION_MODEL
    report.extraction_prompt_version = EXTRACTION_PROMPT_VERSION
    db.commit()
