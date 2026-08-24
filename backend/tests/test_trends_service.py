"""
Tests for compute_report_trends (app/trends/service.py) - the
orchestration that builds a per-test time series across a profile's
reports. No live database - db is a MagicMock dispatching by query
shape (db.query(Result) for the anchor report's own trend-eligible
results, db.query(TestAlias) per distinct alias, db.query(Result,
Report) for that alias's rows across the whole profile), same MagicMock
pattern as test_units_service.py. Call order matches the function's own
iteration order (deterministic - Python dict/list order), so each
per-alias query pops the next prepared answer off a small queue.

The relational correctness of the actual SQL filters (report_id
scoping, profile_id scoping, test_alias_id IS NOT NULL) is proven for
real against a scratch Postgres database, not here - a mock can't tell
a correct WHERE clause from a wrong one, only that the function used
whatever the mock was told to return.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.models import Report, Result, TestAlias
from app.trends.service import compute_report_trends

_BASE_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _report(profile_id, days_offset, report_id=None):
    return Report(
        id=report_id or uuid.uuid4(),
        profile_id=profile_id,
        status="processed",
        original_filename="labs.pdf",
        mime_type="application/pdf",
        created_at=_BASE_DATE + timedelta(days=days_offset),
    )


_UNSET = object()


def _result(report_id, alias_id, value, unit, flag, value_numeric=_UNSET):
    return Result(
        id=uuid.uuid4(),
        report_id=report_id,
        raw_test_name="WBC",
        value=value,
        value_numeric=float(value) if value_numeric is _UNSET else value_numeric,
        unit=unit,
        flag=flag,
        test_alias_id=alias_id,
        reference_range_text="4.5-11.0",
    )


def _alias(default_unit):
    return TestAlias(
        id=uuid.uuid4(),
        raw_name="WBC",
        canonical_name="White Blood Cell Count",
        default_unit=default_unit,
    )


def _fake_db(anchor_results, alias_queue, rows_queue):
    fake_db = MagicMock()
    alias_iter = iter(alias_queue)
    rows_iter = iter(rows_queue)

    def query_side_effect(*args):
        mock = MagicMock()
        if args == (Result,):
            mock.filter.return_value.order_by.return_value.all.return_value = (
                anchor_results
            )
        elif args == (TestAlias,):
            mock.filter.return_value.one_or_none.return_value = next(alias_iter)
        elif args == (Result, Report):
            joined = mock.join.return_value.filter.return_value.order_by.return_value
            joined.all.return_value = next(rows_iter)
        return mock

    fake_db.query.side_effect = query_side_effect
    return fake_db


def test_computes_a_rising_trend_with_all_points_comparable():
    profile_id = uuid.uuid4()
    alias = _alias(default_unit="x10^3/uL")
    report1, report2, report3 = (
        _report(profile_id, 0),
        _report(profile_id, 30),
        _report(profile_id, 60),
    )
    result1 = _result(report1.id, alias.id, "6.2", "x10^3/uL", "normal")
    result2 = _result(report2.id, alias.id, "8.1", "x10^3/uL", "normal")
    result3 = _result(report3.id, alias.id, "11.8", "x10^3/uL", "high")
    fake_db = _fake_db(
        anchor_results=[result3],
        alias_queue=[alias],
        rows_queue=[[(result1, report1), (result2, report2), (result3, report3)]],
    )

    tests = compute_report_trends(fake_db, report3)

    assert len(tests) == 1
    trend = tests[0]
    assert trend["canonical_name"] == "White Blood Cell Count"
    assert trend["chart_unit"] == "x10^3/uL"
    assert trend["has_trend"] is True
    assert [point["value"] for point in trend["points"]] == [6.2, 8.1, 11.8]
    assert trend["points"][-1]["flag"] == "high"
    assert trend["excluded_points"] == []
    assert trend["latest"]["value"] == "11.8"
    assert trend["latest"]["flag"] == "high"
    assert trend["latest"]["report_id"] == str(report3.id)


def test_excludes_a_point_with_an_incompatible_unit():
    profile_id = uuid.uuid4()
    alias = _alias(default_unit="x10^3/uL")
    report1, report2 = _report(profile_id, 0), _report(profile_id, 30)
    incompatible = _result(report1.id, alias.id, "3", "furlongs", "normal")
    comparable = _result(report2.id, alias.id, "8.1", "x10^3/uL", "normal")
    fake_db = _fake_db(
        anchor_results=[comparable],
        alias_queue=[alias],
        rows_queue=[[(incompatible, report1), (comparable, report2)]],
    )

    tests = compute_report_trends(fake_db, report2)

    trend = tests[0]
    assert len(trend["points"]) == 1
    assert trend["points"][0]["value"] == 8.1
    assert len(trend["excluded_points"]) == 1
    assert trend["excluded_points"][0]["reason"] == "unit not comparable"
    assert trend["excluded_points"][0]["raw_unit"] == "furlongs"
    # Only one genuinely comparable point - not enough for a real trend.
    assert trend["has_trend"] is False


def test_excludes_a_non_numeric_value():
    profile_id = uuid.uuid4()
    alias = _alias(default_unit="x10^3/uL")
    report1, report2 = _report(profile_id, 0), _report(profile_id, 30)
    non_numeric = _result(
        report1.id, alias.id, "Negative", None, None, value_numeric=None
    )
    comparable = _result(report2.id, alias.id, "8.1", "x10^3/uL", "normal")
    fake_db = _fake_db(
        anchor_results=[comparable],
        alias_queue=[alias],
        rows_queue=[[(non_numeric, report1), (comparable, report2)]],
    )

    tests = compute_report_trends(fake_db, report2)

    trend = tests[0]
    assert len(trend["points"]) == 1
    assert len(trend["excluded_points"]) == 1
    assert trend["excluded_points"][0]["reason"] == "not a numeric value"
    assert trend["excluded_points"][0]["raw_value"] == "Negative"


def test_has_trend_is_false_with_only_one_report():
    profile_id = uuid.uuid4()
    alias = _alias(default_unit="x10^3/uL")
    report1 = _report(profile_id, 0)
    result1 = _result(report1.id, alias.id, "6.2", "x10^3/uL", "normal")
    fake_db = _fake_db(
        anchor_results=[result1],
        alias_queue=[alias],
        rows_queue=[[(result1, report1)]],
    )

    tests = compute_report_trends(fake_db, report1)

    assert tests[0]["has_trend"] is False
    assert len(tests[0]["points"]) == 1


def test_falls_back_to_the_latest_reports_own_unit_with_no_catalog_default():
    profile_id = uuid.uuid4()
    alias = _alias(default_unit=None)
    report1, report2 = _report(profile_id, 0), _report(profile_id, 30)
    result1 = _result(report1.id, alias.id, "6200", "/uL", "normal")
    result2 = _result(report2.id, alias.id, "8.1", "x10^3/uL", "normal")
    fake_db = _fake_db(
        anchor_results=[result2],
        alias_queue=[alias],
        rows_queue=[[(result1, report1), (result2, report2)]],
    )

    tests = compute_report_trends(fake_db, report2)

    trend = tests[0]
    # No catalog default -> anchors on the most recent report's own unit.
    assert trend["chart_unit"] == "x10^3/uL"
    assert len(trend["points"]) == 2
    # 6200 /uL == 6.2 x10^3/uL, correctly converted onto the chart's unit.
    assert trend["points"][0]["value"] == 6.2
    assert trend["points"][1]["value"] == 8.1


def test_unitless_values_are_directly_comparable():
    profile_id = uuid.uuid4()
    alias = _alias(default_unit=None)
    report1, report2 = _report(profile_id, 0), _report(profile_id, 30)
    result1 = _result(report1.id, alias.id, "5.4", None, "normal")
    result2 = _result(report2.id, alias.id, "5.6", None, "normal")
    fake_db = _fake_db(
        anchor_results=[result2],
        alias_queue=[alias],
        rows_queue=[[(result1, report1), (result2, report2)]],
    )

    tests = compute_report_trends(fake_db, report2)

    trend = tests[0]
    assert trend["chart_unit"] is None
    assert trend["excluded_points"] == []
    assert [point["value"] for point in trend["points"]] == [5.4, 5.6]


def test_a_report_with_no_trend_eligible_results_returns_no_tests():
    report = _report(uuid.uuid4(), 0)
    fake_db = _fake_db(anchor_results=[], alias_queue=[], rows_queue=[])

    tests = compute_report_trends(fake_db, report)

    assert tests == []
