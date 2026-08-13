"""
Tasks 19-20 of the trust chain: computing a result's low/normal/high
status DETERMINISTICALLY, in plain code, from the value and reference
range the report itself printed - never an AI opinion, and never a
built-in table of "normal" values for any test. There is no lookup
anywhere in this file keyed by test name; the only inputs are the two
strings a single Result row already has (its value and its printed
reference range).

A result with no printed range, or a range/value that isn't a plain
number, simply has no status - this module never invents one. That's
enforced structurally: every path either returns one of LOW/NORMAL/HIGH
computed directly from the two printed numbers, or returns None.
"""

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Result
from app.trust.numeric import parse_comparator_and_number

LOW = "low"
NORMAL = "normal"
HIGH = "high"

# Only a strict "NUMBER - NUMBER" shape is treated as a computable
# range - the exact same narrow shape
# app.trust.checks.check_reference_range_sanity validates. A range
# printed any other way ("Negative", "< 5.0", "Non-reactive", ...) has
# no low/high pair to compute against, so it yields no status - never a
# guessed or looked-up one.
_LOW_HIGH_RANGE_PATTERN = re.compile(
    r"^\s*(?P<low>-?\d+(?:\.\d+)?)\s*-\s*(?P<high>-?\d+(?:\.\d+)?)\s*$"
)


def parse_reference_range(
    reference_range_text: str | None,
) -> tuple[float, float] | None:
    """
    Parses a reference range into (low, high) floats ONLY when it's a
    strict numeric low-high pair, exactly as printed on the report.
    Returns None for a blank/missing range, free text ("Negative"),
    or a reversed pair (low > high) - there's nothing here to fall
    back on for those; the caller simply computes no status.
    """
    if reference_range_text is None or not reference_range_text.strip():
        return None

    match = _LOW_HIGH_RANGE_PATTERN.match(reference_range_text.strip())
    if match is None:
        return None

    low = float(match.group("low"))
    high = float(match.group("high"))
    if low > high:
        return None
    return low, high


def calculate_status(value: str, reference_range_text: str | None) -> str | None:
    """
    Compares the extracted value against the extracted reference range,
    both taken exactly as printed on this same report - pure comparison
    code, never an AI opinion and never a hardcoded "normal" value for
    any test.

    Returns None (no status, not a guess) whenever there isn't enough
    printed information to compute one with certainty:
      - no printed range, or a range that isn't a plain low-high pair
      - a value that doesn't parse as a number at all
      - a "<X"/">X" value whose direction can't be resolved against the
        range with certainty (see _classify_bounded_value below)
    """
    parsed_range = parse_reference_range(reference_range_text)
    if parsed_range is None:
        return None
    low, high = parsed_range

    parsed_value = parse_comparator_and_number(value)
    if parsed_value is None:
        return None
    comparator, number = parsed_value

    return _classify_bounded_value(comparator, number, low, high)


def _classify_bounded_value(
    comparator: str | None, number: float, low: float, high: float
) -> str | None:
    """
    Plain value: compare directly.

    "<X" (the true value is somewhere below X): only certain to be LOW
    when even the printed ceiling X is already at or below the range's
    low end - anything less than X is then definitely low. If X falls
    inside or above the range, the true value could be anywhere below
    X (including inside the range), so this deliberately returns None
    rather than guess.

    ">X" is the mirror image for HIGH.
    """
    if comparator is None:
        if number < low:
            return LOW
        if number > high:
            return HIGH
        return NORMAL

    if comparator == "<":
        if number <= low:
            return LOW
        return None

    if comparator == ">":
        if number >= high:
            return HIGH
        return None

    return None


def apply_status_for_report(db: Session, report_id: UUID) -> None:
    """
    Computes and stores flag/value_numeric/reference_range_low/
    reference_range_high for every result in a report, straight from
    that same result's own printed value and reference range - no
    other input. A result whose value or range doesn't parse gets
    value_numeric/reference_range_low/reference_range_high left as
    None and flag left as None; nothing here ever fills in a guess.

    Independent of trust_status (app/trust/service.py) - this is a
    separate, purely mechanical computation over whatever value and
    range text a result happens to have, run for every result in the
    report regardless of whether that result later gets flagged for
    review.
    """
    results = db.query(Result).filter(Result.report_id == report_id).all()

    for result in results:
        parsed_range = parse_reference_range(result.reference_range_text)
        parsed_value = parse_comparator_and_number(result.value)

        result.value_numeric = parsed_value[1] if parsed_value is not None else None
        result.reference_range_low = (
            parsed_range[0] if parsed_range is not None else None
        )
        result.reference_range_high = (
            parsed_range[1] if parsed_range is not None else None
        )
        result.flag = calculate_status(result.value, result.reference_range_text)

    db.commit()
