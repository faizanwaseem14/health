"""
Tests for apply_unit_conversion_for_report (app/units/service.py) - the
orchestration that computes a derived converted value/unit for a
report's results. No live database - db is a MagicMock, same pattern
as test_trust_service.py.
"""

import uuid
from unittest.mock import MagicMock

from app.models import Result, TestAlias
from app.units.service import apply_unit_conversion_for_report


def _alias(default_unit):
    return TestAlias(
        id=uuid.uuid4(),
        raw_name="Hemoglobin",
        canonical_name="Hemoglobin",
        default_unit=default_unit,
    )


def _result(report_id, value, unit, test_alias_id=None):
    return Result(
        id=uuid.uuid4(),
        report_id=report_id,
        raw_test_name="HGB",
        value=value,
        unit=unit,
        test_alias_id=test_alias_id,
    )


def _fake_db(results, aliases):
    fake_db = MagicMock()

    def query_side_effect(model):
        mock = MagicMock()
        if model is Result:
            mock.filter.return_value.all.return_value = results
        elif model is TestAlias:
            mock.filter.return_value.all.return_value = aliases
        return mock

    fake_db.query.side_effect = query_side_effect
    return fake_db


def test_stores_a_derived_value_for_a_convertible_unit():
    report_id = uuid.uuid4()
    alias = _alias(default_unit="g/dL")
    result = _result(report_id, "1000", "mg/dL", test_alias_id=alias.id)
    fake_db = _fake_db([result], [alias])

    apply_unit_conversion_for_report(fake_db, report_id)

    assert result.converted_value_numeric == 1.0
    assert result.converted_unit == "g/dL"
    fake_db.commit.assert_called_once()


def test_leaves_derived_fields_none_when_unit_already_matches_default():
    report_id = uuid.uuid4()
    alias = _alias(default_unit="g/dL")
    result = _result(report_id, "13.5", "g/dL", test_alias_id=alias.id)
    fake_db = _fake_db([result], [alias])

    apply_unit_conversion_for_report(fake_db, report_id)

    assert result.converted_value_numeric is None
    assert result.converted_unit is None


def test_leaves_derived_fields_none_when_units_are_incompatible():
    report_id = uuid.uuid4()
    alias = _alias(default_unit="g/dL")
    # A unit that doesn't belong to any known conversion family at all.
    result = _result(report_id, "13.5", "furlongs", test_alias_id=alias.id)
    fake_db = _fake_db([result], [alias])

    apply_unit_conversion_for_report(fake_db, report_id)

    assert result.converted_value_numeric is None
    assert result.converted_unit is None


def test_leaves_derived_fields_none_when_there_is_no_resolved_alias():
    report_id = uuid.uuid4()
    result = _result(report_id, "1000", "mg/dL", test_alias_id=None)
    fake_db = _fake_db([result], [])

    apply_unit_conversion_for_report(fake_db, report_id)

    assert result.converted_value_numeric is None
    assert result.converted_unit is None


def test_leaves_derived_fields_none_when_the_alias_has_no_default_unit():
    report_id = uuid.uuid4()
    alias = _alias(default_unit=None)
    result = _result(report_id, "1000", "mg/dL", test_alias_id=alias.id)
    fake_db = _fake_db([result], [alias])

    apply_unit_conversion_for_report(fake_db, report_id)

    assert result.converted_value_numeric is None
    assert result.converted_unit is None


def test_never_overwrites_the_original_value_and_unit():
    report_id = uuid.uuid4()
    alias = _alias(default_unit="g/dL")
    result = _result(report_id, "1000", "mg/dL", test_alias_id=alias.id)
    fake_db = _fake_db([result], [alias])

    apply_unit_conversion_for_report(fake_db, report_id)

    assert result.value == "1000"
    assert result.unit == "mg/dL"


def test_a_report_with_zero_results_does_nothing():
    fake_db = _fake_db([], [])

    apply_unit_conversion_for_report(fake_db, uuid.uuid4())

    fake_db.commit.assert_not_called()
