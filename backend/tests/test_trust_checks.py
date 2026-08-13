"""
Unit tests for each individual trust check function (app/trust/checks.py).
No database, no mocking - these are pure functions, tested directly with
plain values.
"""

from app.trust.checks import (
    check_confidence_threshold,
    check_evidence_traceability,
    check_reference_range_sanity,
    check_unit_sanity,
    check_value_sanity,
)

# --- check_evidence_traceability (check 16: anti-hallucination guard) ---


def test_evidence_traceability_passes_when_value_appears_in_evidence():
    assert check_evidence_traceability("13.5", "HGB 13.5 g/dL") is None


def test_evidence_traceability_passes_ignoring_whitespace_and_case():
    assert check_evidence_traceability("13.5", "HGB 1 3 . 5 g / dL") is None


def test_evidence_traceability_fails_when_value_is_not_in_evidence():
    reason = check_evidence_traceability("99.9", "HGB 13.5 g/dL")
    assert reason is not None
    assert "99.9" in reason


def test_evidence_traceability_fails_when_there_is_no_evidence_at_all():
    reason = check_evidence_traceability("13.5", "")
    assert reason is not None
    assert "no OCR evidence" in reason


# --- check_value_sanity (check 17a) ---


def test_value_sanity_passes_for_a_clean_number():
    assert check_value_sanity("13.5") is None


def test_value_sanity_passes_for_qualitative_text_with_no_digits():
    assert check_value_sanity("Negative") is None


def test_value_sanity_passes_for_a_comparator_prefixed_number():
    assert check_value_sanity("<0.1") is None


def test_value_sanity_passes_for_less_than_notation():
    assert check_value_sanity("<0.01") is None


def test_value_sanity_passes_for_greater_than_notation():
    assert check_value_sanity(">100") is None


def test_value_sanity_fails_for_a_malformed_numeric_looking_value():
    reason = check_value_sanity("13..5x")
    assert reason is not None
    assert "13..5x" in reason


def test_value_sanity_still_fails_for_a_malformed_value_with_a_comparator():
    # The comparator notation fix only accepts a real number after the
    # comparator - it doesn't loosen the "must actually parse" rule.
    reason = check_value_sanity("<13..5x")
    assert reason is not None
    assert "<13..5x" in reason


def test_value_sanity_fails_for_a_blank_value():
    reason = check_value_sanity("   ")
    assert reason is not None
    assert "blank" in reason


# --- check_reference_range_sanity (check 17b) ---


def test_reference_range_sanity_passes_for_a_valid_low_high_pair():
    assert check_reference_range_sanity("12.0-15.5") is None


def test_reference_range_sanity_passes_for_free_text_ranges():
    assert check_reference_range_sanity("Negative") is None
    assert check_reference_range_sanity("< 5.0") is None


def test_reference_range_sanity_passes_for_a_blank_or_missing_range():
    assert check_reference_range_sanity(None) is None
    assert check_reference_range_sanity("") is None


def test_reference_range_sanity_fails_when_low_bound_is_above_high_bound():
    reason = check_reference_range_sanity("15.5-12.0")
    assert reason is not None
    assert "15.5-12.0" in reason


# --- check_unit_sanity (check 17c) ---


def test_unit_sanity_passes_for_a_normal_unit():
    assert check_unit_sanity("g/dL") is None


def test_unit_sanity_passes_when_unit_is_null():
    assert check_unit_sanity(None) is None


def test_unit_sanity_fails_when_unit_is_blank_instead_of_null():
    reason = check_unit_sanity("   ")
    assert reason is not None
    assert "blank" in reason


def test_unit_sanity_fails_when_unit_is_actually_a_number():
    reason = check_unit_sanity("13.5")
    assert reason is not None
    assert "13.5" in reason


def test_unit_sanity_fails_when_unit_is_unreasonably_long():
    reason = check_unit_sanity("x" * 40)
    assert reason is not None
    assert "long" in reason


# --- check_confidence_threshold (check 18) ---


def test_confidence_threshold_passes_at_or_above_the_threshold():
    assert check_confidence_threshold(0.8, threshold=0.8) is None
    assert check_confidence_threshold(0.95, threshold=0.8) is None


def test_confidence_threshold_fails_below_the_threshold():
    reason = check_confidence_threshold(0.62, threshold=0.8)
    assert reason is not None
    assert "0.62" in reason
    assert "0.80" in reason


def test_confidence_threshold_fails_when_confidence_is_missing():
    reason = check_confidence_threshold(None, threshold=0.8)
    assert reason is not None
    assert "no confidence score" in reason
