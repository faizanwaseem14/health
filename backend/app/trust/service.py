"""
Runs every trust check against a report's extracted results and
records the outcome. A result is "trusted" only if it passes EVERY
check; failing any single one routes it to "review_required" instead -
never partially trusted, never silently accepted.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import OcrWord, Result, ResultOcrWord
from app.trust.checks import (
    check_confidence_threshold,
    check_evidence_traceability,
    check_reference_range_sanity,
    check_unit_sanity,
    check_value_sanity,
)

TRUSTED = "trusted"
NEEDS_REVIEW = "review_required"


def run_trust_checks_for_report(db: Session, report_id: UUID) -> bool:
    """
    Checks every Result row belonging to a report, sets each row's
    trust_status/trust_check_notes, and commits. Returns True only if
    EVERY row ended up trusted (the report has nothing left to review);
    False if any row needs review - the worker uses this to decide
    whether the job is COMPLETED or REVIEW_REQUIRED.

    A report with zero extracted rows has nothing to fail, so this
    returns True for it - there's simply nothing here that could be
    untrustworthy.
    """
    results = db.query(Result).filter(Result.report_id == report_id).all()

    all_trusted = True
    for result in results:
        reason = _check_one_result(db, result)
        if reason is None:
            result.trust_status = TRUSTED
            result.trust_check_notes = None
        else:
            result.trust_status = NEEDS_REVIEW
            result.trust_check_notes = reason
            all_trusted = False

    db.commit()
    return all_trusted


def _check_one_result(db: Session, result: Result) -> str | None:
    """Runs every check for one result, in order, stopping at (and
    returning) the first failure - a result either passes all of them
    or it doesn't; there's no need to keep checking once it's already
    routed to review."""
    evidence_text = _evidence_text_for_result(db, result.id)

    for reason in (
        check_evidence_traceability(result.value, evidence_text),
        check_value_sanity(result.value),
        check_reference_range_sanity(result.reference_range_text),
        check_unit_sanity(result.unit),
        check_confidence_threshold(
            result.ai_confidence, settings.trust_confidence_threshold
        ),
    ):
        if reason is not None:
            return reason
    return None


def _evidence_text_for_result(db: Session, result_id: UUID) -> str:
    """The combined text of every OCR word linked to this result, in
    reading order - what check_evidence_traceability compares the
    value against."""
    words = (
        db.query(OcrWord)
        .join(ResultOcrWord, ResultOcrWord.ocr_word_id == OcrWord.id)
        .filter(ResultOcrWord.result_id == result_id)
        .order_by(OcrWord.page_number, OcrWord.word_index)
        .all()
    )
    return " ".join(word.text for word in words)
