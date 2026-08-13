"""
Tests for the deterministic status calculation (app/trust/status.py) -
tasks 19-20 of the trust chain. calculate_status/parse_reference_range
are pure functions, tested directly with plain values; apply_status_for_report
is tested with a MagicMock db, same pattern as test_trust_service.py.
"""

import uuid
from unittest.mock import MagicMock

from app.models import Result
from app.trust.status import (
    HIGH,
    LOW,
    NORMAL,
    apply_status_for_report,
    calculate_status,
    parse_reference_range,
)

# --- parse_reference_range ---


def test_parse_reference_range_parses_a_plain_low_high_pair():
    assert parse_reference_range("12.0-15.5") == (12.0, 15.5)


def test_parse_reference_range_returns_none_for_free_text():
    assert parse_reference_range("Negative") is None
    assert parse_reference_range("< 5.0") is None


def test_parse_reference_range_returns_none_for_blank_or_missing():
    assert parse_reference_range(None) is None
    assert parse_reference_range("") is None


def test_parse_reference_range_returns_none_for_a_reversed_pair():
    assert parse_reference_range("15.5-12.0") is None


# --- calculate_status: plain (non-comparator) values ---


def test_calculate_status_is_low_when_value_is_below_the_range():
    assert calculate_status("10.0", "12.0-15.5") == LOW


def test_calculate_status_is_normal_when_value_is_within_the_range():
    assert calculate_status("13.5", "12.0-15.5") == NORMAL


def test_calculate_status_is_normal_at_the_exact_boundaries():
    assert calculate_status("12.0", "12.0-15.5") == NORMAL
    assert calculate_status("15.5", "12.0-15.5") == NORMAL


def test_calculate_status_is_high_when_value_is_above_the_range():
    assert calculate_status("20.0", "12.0-15.5") == HIGH


# --- calculate_status: no status when there isn't enough printed info ---


def test_calculate_status_is_none_when_there_is_no_printed_range():
    assert calculate_status("13.5", None) is None
    assert calculate_status("13.5", "") is None


def test_calculate_status_is_none_when_the_range_is_not_a_numeric_pair():
    assert calculate_status("13.5", "Negative") is None


def test_calculate_status_is_none_when_the_value_does_not_parse():
    assert calculate_status("Negative", "12.0-15.5") is None
    assert calculate_status("13..5x", "12.0-15.5") is None


# --- calculate_status: "<"/">" comparator values, handled conservatively ---


def test_less_than_value_at_or_below_the_low_bound_is_low():
    # "<0.01" against a range starting at 0.1: the true value is
    # somewhere below 0.01, which is already below the range - certain.
    assert calculate_status("<0.01", "0.1-1.0") == LOW


def test_less_than_value_inside_the_range_is_ambiguous_so_no_status():
    # "<5.0" against 1.0-10.0: the true value could be anywhere below
    # 5.0, including inside the range - not certain, so no guess.
    assert calculate_status("<5.0", "1.0-10.0") is None


def test_greater_than_value_at_or_above_the_high_bound_is_high():
    assert calculate_status(">100", "0-90") == HIGH


def test_greater_than_value_inside_the_range_is_ambiguous_so_no_status():
    assert calculate_status(">5.0", "1.0-10.0") is None


# --- apply_status_for_report ---


def _fake_db(results):
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.all.return_value = results
    return fake_db


def test_apply_status_for_report_populates_flag_and_numeric_fields():
    result = Result(
        id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        raw_test_name="HGB",
        value="20.0",
        reference_range_text="12.0-15.5",
    )
    fake_db = _fake_db([result])

    apply_status_for_report(fake_db, result.report_id)

    assert result.flag == HIGH
    assert result.value_numeric == 20.0
    assert result.reference_range_low == 12.0
    assert result.reference_range_high == 15.5
    fake_db.commit.assert_called_once()


def test_apply_status_for_report_leaves_everything_none_without_a_printed_range():
    result = Result(
        id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        raw_test_name="HGB",
        value="13.5",
        reference_range_text=None,
    )
    fake_db = _fake_db([result])

    apply_status_for_report(fake_db, result.report_id)

    assert result.flag is None
    assert result.reference_range_low is None
    assert result.reference_range_high is None
    # The value itself still parses even with no range to compare
    # against - value_numeric doesn't depend on having a status.
    assert result.value_numeric == 13.5
