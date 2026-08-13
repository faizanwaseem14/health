"""
The individual trust checks. Each function takes plain values (never a
database row) and returns None if the check passes, or a short
human-readable reason string if it fails - never raises, never decides
"is this medically normal", only "is this well-formed and traceable".
"""

import re

# Strips characters that are purely NUMERIC FORMATTING, never medical
# meaning: comparator prefixes ("<0.1" means "less than 0.1", still a
# real number), a trailing percent sign, and thousands separators.
_LEADING_COMPARATORS = "<>=≤≥"


def _looks_numeric(text: str) -> bool:
    """True if the text contains at least one digit - i.e. it's making
    SOME claim to be a number, even if it turns out malformed. Text
    with no digits at all (e.g. "Negative", "Trace", "Not Detected")
    never claims to be a number, so it's never held to that bar."""
    return any(character.isdigit() for character in text)


def _parse_number(text: str) -> float | None:
    """
    Best-effort parse of a value that LOOKS like it's meant to be a
    number, stripping only pure formatting (not meaning): a leading
    comparator, a trailing "%", and comma thousands separators. Returns
    None if what's left still isn't a real number.
    """
    cleaned = text.strip().lstrip(_LEADING_COMPARATORS).strip()
    cleaned = cleaned.rstrip("%").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_for_substring_match(text: str) -> str:
    """Lowercased, whitespace-free - so OCR tokenization quirks (a
    decimal point read as its own word, extra spacing) don't cause a
    real match to be missed."""
    return re.sub(r"\s+", "", text).lower()


def check_evidence_traceability(value: str, evidence_text: str) -> str | None:
    """
    Check 16 (the anti-hallucination guard): the result's value must
    actually appear in the OCR text of the word(s) it claims as
    evidence. A result with no linked evidence at all can never pass -
    that's exactly the case this check exists to catch.
    """
    if not evidence_text.strip():
        return "no OCR evidence is linked to this result"
    if _normalize_for_substring_match(value) not in _normalize_for_substring_match(
        evidence_text
    ):
        return f"value {value!r} does not appear in its linked OCR evidence"
    return None


def check_value_sanity(value: str) -> str | None:
    """
    Check 17a: if a value looks like it's trying to be a number (it has
    a digit in it), it must actually parse as one once ordinary
    formatting is stripped. A value with no digits at all (a genuine
    qualitative result like "Negative") is never held to this bar -
    that's not malformed, that's how real lab reports look.
    """
    stripped = value.strip()
    if not stripped:
        return "value is blank"
    if _looks_numeric(stripped) and _parse_number(stripped) is None:
        return f"value {value!r} looks numeric but doesn't parse as a number"
    return None


# Only a strict "NUMBER - NUMBER" shape is checked for internal
# consistency (low <= high). Anything else - "Negative", "< 5.0",
# "Non-reactive", or a range with a genuinely non-numeric bound - is
# treated as valid free text, exactly as app/models/result.py's
# reference_range_text already anticipates. This is a deliberately
# narrow check: it catches a reversed or malformed numeric pair, not
# every conceivable typo.
_LOW_HIGH_RANGE_PATTERN = re.compile(
    r"^\s*(?P<low>-?\d+(?:\.\d+)?)\s*-\s*(?P<high>-?\d+(?:\.\d+)?)\s*$"
)


def check_reference_range_sanity(reference_range: str | None) -> str | None:
    """Check 17b: if a reference range takes the shape of a plain
    numeric low-high pair, the low bound must not be above the high
    bound."""
    if reference_range is None or not reference_range.strip():
        return None

    match = _LOW_HIGH_RANGE_PATTERN.match(reference_range.strip())
    if match is None:
        return None

    low = float(match.group("low"))
    high = float(match.group("high"))
    if low > high:
        return (
            f"reference range {reference_range!r} has its low bound "
            "above its high bound"
        )
    return None


_MAX_REASONABLE_UNIT_LENGTH = 32


def check_unit_sanity(unit: str | None) -> str | None:
    """
    Check 17c: a present unit must actually look like a unit - not
    blank, not absurdly long, and not just a bare number (a strong
    signal the AI put the value into the wrong field).
    """
    if unit is None:
        return None

    stripped = unit.strip()
    if not stripped:
        return "unit is blank instead of null"
    if len(stripped) > _MAX_REASONABLE_UNIT_LENGTH:
        return f"unit {unit!r} is unreasonably long for a unit"
    if _parse_number(stripped) is not None:
        return f"unit {unit!r} looks like a number, not a unit"
    return None


def check_confidence_threshold(
    confidence: float | None, threshold: float
) -> str | None:
    """Check 18: the AI's own confidence in this row must meet the
    configured threshold (app.config.settings.trust_confidence_threshold)."""
    if confidence is None:
        return "no confidence score was recorded"
    confidence = float(confidence)
    if confidence < threshold:
        return f"confidence {confidence:.2f} is below the {threshold:.2f} threshold"
    return None
