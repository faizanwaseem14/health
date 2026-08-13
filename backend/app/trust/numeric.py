"""
Shared numeric-parsing helpers for the trust chain: turning a printed
value into a plain number, stripping only FORMATTING (a leading
comparator like "<" or ">", a trailing "%", comma thousands
separators) - never medical meaning. Used by both the structural
checks (app/trust/checks.py) and the deterministic status calculation
(app/trust/status.py), so there is exactly one place that decides what
counts as a parseable number.
"""

# "<0.01" means "less than 0.01" and ">100" means "greater than 100" -
# both are still real numbers, just with a comparator printed in front.
# "=", "≤" (<=) and "≥" (>=) are accepted the same way for
# the same reason. This is pure numeric-format handling, not a medical
# assumption about any value.
_COMPARATOR_CHARS = "<>=≤≥"


def parse_number(text: str) -> float | None:
    """
    Best-effort parse of a value that LOOKS like it's meant to be a
    number: strips a leading comparator, a trailing "%", and comma
    thousands separators, then tries to parse what's left as a float.
    Returns None if what's left still isn't a real number.
    """
    cleaned = text.strip().lstrip(_COMPARATOR_CHARS).strip()
    cleaned = cleaned.rstrip("%").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_comparator_and_number(text: str) -> tuple[str | None, float] | None:
    """
    Splits a value into its comparator ("<" for a less-than/at-most
    value, ">" for a greater-than/at-least value, or None for a plain
    number) and the number that follows it, e.g. "<0.01" -> ("<", 0.01),
    "13.5" -> (None, 13.5). "≤"/"≥" collapse to "<"/">" -
    treating "at most"/"at least" the same as strict "less than"/
    "greater than" is the conservative choice for status calculation
    (see app/trust/status.py), not a claim that they mean the same
    thing.

    Returns None if the text doesn't parse as a number at all once the
    comparator is stripped.
    """
    stripped = text.strip()

    comparator = None
    if stripped.startswith("<") or stripped.startswith("≤"):
        comparator = "<"
    elif stripped.startswith(">") or stripped.startswith("≥"):
        comparator = ">"

    number = parse_number(stripped)
    if number is None:
        return None
    return comparator, number
