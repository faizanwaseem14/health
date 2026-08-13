"""
Generates and stores one plain-language explanation per result in a
report (see app/ai/explanation.py), describing only what that result's
test measures - never its value, status, or what it might mean.

Explanation content is deliberately generic per test name, so a Claude
call is only made once per DISTINCT canonical_test_name in a report
(e.g. a panel that prints "WBC" three times only costs one call) - but
every result row still gets its own Explanation row, one per
result_id, exactly as app/models/explanation.py's "explanation of one
specific result" shape expects.

A refusal or validation failure for one test name is logged and
skipped, not raised - an explanation is supplementary educational
content, not something that should block the rest of the report's
explanations or fail the job the way a bad AI extraction does.
"""

import logging

from sqlalchemy.orm import Session

from app.ai.explanation import (
    ExplanationRefusedError,
    ExplanationValidationError,
    generate_test_explanation,
)
from app.ai.explanation_prompt import EXPLANATION_MODEL, build_explanation_prompt
from app.models import Explanation, Report, Result

logger = logging.getLogger("medvault")


def generate_explanations_for_report(db: Session, report: Report) -> None:
    """
    REPLACES any previous explanations for this report's results - same
    replace-wholesale-on-retry pattern as OCR evidence and AI
    extraction.
    """
    result_ids_subquery = db.query(Result.id).filter(Result.report_id == report.id)
    db.query(Explanation).filter(Explanation.result_id.in_(result_ids_subquery)).delete(
        synchronize_session=False
    )

    results = db.query(Result).filter(Result.report_id == report.id).all()

    explanation_cache: dict[str, str | None] = {}

    for result in results:
        test_name = result.canonical_test_name
        if test_name not in explanation_cache:
            explanation_cache[test_name] = _generate_one_explanation(
                test_name, result.raw_test_name
            )

        content = explanation_cache[test_name]
        if content is None:
            continue

        db.add(
            Explanation(
                result_id=result.id,
                content=content,
                model_used=EXPLANATION_MODEL,
            )
        )

    db.commit()


def _generate_one_explanation(
    canonical_test_name: str, raw_test_name: str
) -> str | None:
    prompt_text = build_explanation_prompt(canonical_test_name, raw_test_name)
    try:
        result = generate_test_explanation(prompt_text)
    except (ExplanationValidationError, ExplanationRefusedError):
        logger.warning(
            "Explanation generation skipped for %r", canonical_test_name, exc_info=True
        )
        return None
    return result.explanation
