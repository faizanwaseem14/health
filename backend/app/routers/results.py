"""
Routes for a report's extracted results: reading them (with their
correction history and any already-generated explanation), generating
plain-language explanations on demand, and recording a manual
correction.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.ai.explanation_service import generate_explanations_for_report
from app.auth.dependencies import get_current_user, get_db
from app.auth.ownership import require_owned_row
from app.core.audit import record_audit_event
from app.core.responses import success_response
from app.models import Correction, Explanation, Report, Result, ResultOcrWord, User
from app.routers.reports import require_owned_report
from app.schemas.results import CORRECTABLE_FIELDS, CorrectionCreatePayload
from app.trust.numeric import parse_comparator_and_number
from app.trust.status import calculate_status

router = APIRouter()

require_owned_result = require_owned_row(Result)


def _result_response(db: Session, result: Result) -> dict:
    explanation = (
        db.query(Explanation.content)
        .filter(Explanation.result_id == result.id)
        .scalar()
    )
    corrections = (
        db.query(Correction)
        .filter(Correction.result_id == result.id)
        .order_by(Correction.created_at)
        .all()
    )
    ocr_word_ids = [
        str(row.ocr_word_id)
        for row in db.query(ResultOcrWord)
        .filter(ResultOcrWord.result_id == result.id)
        .all()
    ]

    return {
        "id": str(result.id),
        "raw_test_name": result.raw_test_name,
        "canonical_test_name": result.canonical_test_name,
        "value": result.value,
        "value_numeric": (
            float(result.value_numeric) if result.value_numeric is not None else None
        ),
        "unit": result.unit,
        "reference_range_text": result.reference_range_text,
        "reference_range_low": (
            float(result.reference_range_low)
            if result.reference_range_low is not None
            else None
        ),
        "reference_range_high": (
            float(result.reference_range_high)
            if result.reference_range_high is not None
            else None
        ),
        "flag": result.flag,
        "ai_confidence": (
            float(result.ai_confidence) if result.ai_confidence is not None else None
        ),
        "trust_status": result.trust_status,
        "trust_check_notes": result.trust_check_notes,
        "converted_value_numeric": (
            float(result.converted_value_numeric)
            if result.converted_value_numeric is not None
            else None
        ),
        "converted_unit": result.converted_unit,
        "result_date": result.result_date,
        "lab_name": result.lab_name,
        "explanation": explanation,
        "corrections": [
            {
                "id": str(correction.id),
                "field_name": correction.field_name,
                "previous_value": correction.previous_value,
                "new_value": correction.new_value,
                "reason": correction.reason,
                "created_at": correction.created_at.isoformat(),
            }
            for correction in corrections
        ],
        "ocr_word_ids": ocr_word_ids,
    }


@router.get("/reports/{row_id}/results")
def list_results(
    report: Report = Depends(require_owned_report),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: every extracted result for a report, in the order
    they were extracted - each with its correction history and its
    explanation if one has already been generated (never generates one
    itself; see POST .../explanations for that).
    """
    results = (
        db.query(Result)
        .filter(Result.report_id == report.id)
        .order_by(Result.created_at)
        .all()
    )
    data = [_result_response(db, result) for result in results]
    return success_response(data)


@router.post("/reports/{row_id}/explanations")
def generate_explanations(
    request: Request,
    report: Report = Depends(require_owned_report),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: generates (or regenerates) a plain-language
    explanation for every result in this report - only called when
    someone actually taps a result to see one (see
    generate_explanations_for_report's own docstring: a Claude call is
    made once per distinct test name in the report, not once per
    result, and never automatically). Returns every result_id in the
    report mapped to its explanation content (null for a test name
    whose explanation generation was skipped/refused).
    """
    generate_explanations_for_report(db, report)

    explanations = (
        db.query(Result.id, Explanation.content)
        .outerjoin(Explanation, Explanation.result_id == Result.id)
        .filter(Result.report_id == report.id)
        .all()
    )

    record_audit_event(
        db,
        action="generate_explanations",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="report",
        resource_id=report.id,
        user_agent=request.headers.get("user-agent"),
    )

    return success_response(
        {str(result_id): content for result_id, content in explanations}
    )


@router.post("/results/{row_id}/corrections", status_code=201)
def create_correction(
    request: Request,
    payload: CorrectionCreatePayload,
    result: Result = Depends(require_owned_result),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    PROTECTED route: records a manual correction to one field on a
    result. Never overwrites history - a Correction row is added
    recording exactly what the field held right before this edit and
    what it holds now, then the result's own column is updated to
    match, so the results screen always shows the current (possibly
    corrected) value while the full edit history stays intact
    (embedded per-result in GET .../results).
    """
    if payload.field_name not in CORRECTABLE_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=f"'{payload.field_name}' can't be corrected. "
            f"Correctable fields: {sorted(CORRECTABLE_FIELDS)}.",
        )

    previous_value = getattr(result, payload.field_name)

    correction = Correction(
        result_id=result.id,
        corrected_by_user_id=user.id,
        field_name=payload.field_name,
        previous_value=previous_value,
        new_value=payload.new_value,
        reason=payload.reason,
    )
    db.add(correction)

    setattr(result, payload.field_name, payload.new_value)
    if payload.field_name == "value":
        # Keep the deterministic status in sync with the corrected
        # value, using the exact same pure code Task 19/20 already
        # computes it with for a fresh extraction - never a guess, and
        # never touching trust_status (that's a historical record of
        # the AI extraction's own trust checks, not of this edit).
        parsed = parse_comparator_and_number(payload.new_value)
        result.value_numeric = parsed[1] if parsed is not None else None
        result.flag = calculate_status(payload.new_value, result.reference_range_text)

    db.commit()
    db.refresh(result)

    record_audit_event(
        db,
        action="correct_result",
        ip_address=request.client.host if request.client else "unknown",
        user_id=user.id,
        resource_type="result",
        resource_id=result.id,
        user_agent=request.headers.get("user-agent"),
    )

    return success_response(_result_response(db, result), status_code=201)
