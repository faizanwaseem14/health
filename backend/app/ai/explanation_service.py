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

Two distinct failure modes get retried before being given up on:
- The advice-language guard rejects a response (common - a small model
  asked to describe a test in one sentence will sometimes reach for
  words like "diagnose" or "treatment" even when told not to). Retried
  with a corrective note appended to the prompt naming the mistake, so
  the model gets a real chance to self-correct instead of being skipped
  on the first slip.
- A transient Anthropic API error (rate limit, timeout, connection
  drop, or a 5xx/overloaded response) - retried with a short backoff.
Anything else (a refusal, a non-retryable API error) is logged and
skipped immediately, same as before.
"""

import logging
import time

import anthropic
from sqlalchemy.orm import Session

from app.ai.explanation import (
    ExplanationRefusedError,
    ExplanationValidationError,
    generate_test_explanation,
)
from app.ai.explanation_prompt import EXPLANATION_MODEL, build_explanation_prompt
from app.models import Explanation, Report, Result

logger = logging.getLogger("medvault")

MAX_ATTEMPTS = 3
_TRANSIENT_ANTHROPIC_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


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
            try:
                explanation_cache[test_name] = _generate_one_explanation(
                    test_name, result.raw_test_name
                )
            except Exception:
                # A true safety net: _generate_one_explanation already
                # handles every failure mode we know about (refusals,
                # validation failures, transient API errors). Anything
                # that still reaches here is an unanticipated case for
                # THIS test name specifically - it must not cost every
                # other test name in the report its explanation too.
                logger.exception(
                    "Unexpected error generating an explanation for %r",
                    test_name,
                )
                explanation_cache[test_name] = None

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
    needs_correction = False
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt_text = build_explanation_prompt(
            canonical_test_name, raw_test_name, needs_correction=needs_correction
        )
        try:
            result = generate_test_explanation(prompt_text)
            return result.explanation
        except ExplanationRefusedError as error:
            # A refusal is a policy decision, not a transient hiccup or a
            # fixable wording problem - retrying the same request won't
            # change the outcome.
            last_error = error
            logger.warning(
                "Explanation generation refused for %r: %s",
                canonical_test_name,
                error,
            )
            break
        except ExplanationValidationError as error:
            last_error = error
            logger.warning(
                "Explanation for %r failed the advice-language/schema guard "
                "(attempt %d/%d): %s",
                canonical_test_name,
                attempt,
                MAX_ATTEMPTS,
                error,
            )
            needs_correction = True
        except _TRANSIENT_ANTHROPIC_ERRORS as error:
            last_error = error
            logger.warning(
                "Explanation generation for %r hit a transient API error "
                "(attempt %d/%d): %s",
                canonical_test_name,
                attempt,
                MAX_ATTEMPTS,
                error,
            )
            if attempt < MAX_ATTEMPTS:
                time.sleep(min(2 ** (attempt - 1), 4))
        except anthropic.APIError as error:
            # A non-transient API error (bad request, auth failure, ...) -
            # retrying the identical request won't help.
            last_error = error
            logger.error(
                "Explanation generation for %r hit a non-retryable API " "error: %s",
                canonical_test_name,
                error,
                exc_info=True,
            )
            break

    logger.error(
        "Giving up on an explanation for %r after %d attempt(s): %s",
        canonical_test_name,
        MAX_ATTEMPTS,
        last_error,
    )
    return None
