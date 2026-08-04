"""
Tests for append-only audit logging.

record_audit_event() needs a real database to actually insert a row, but
its validation logic (what it accepts vs rejects) runs BEFORE it ever
touches the database - so we can test that, and specifically prove that
health data cannot get through, without any database at all. The
database-level enforcement (Postgres itself refusing UPDATE/DELETE on
audit_log) is verified for real in the Task 13 summary, against a
throwaway local Postgres.
"""

import inspect
from unittest.mock import MagicMock

import pytest

from app.core.audit import ALLOWED_ACTIONS, ALLOWED_RESOURCE_TYPES, record_audit_event


def test_valid_event_is_recorded():
    db = MagicMock()

    entry = record_audit_event(
        db,
        action="view_report",
        ip_address="127.0.0.1",
        resource_type="report",
    )

    assert entry.action == "view_report"
    assert entry.resource_type == "report"
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_rejects_an_action_not_on_the_allowed_list():
    db = MagicMock()

    with pytest.raises(ValueError):
        record_audit_event(db, action="something_made_up", ip_address="127.0.0.1")

    # Nothing should even reach the database for a rejected call.
    db.add.assert_not_called()


def test_rejects_a_resource_type_not_on_the_allowed_list():
    db = MagicMock()

    with pytest.raises(ValueError):
        record_audit_event(
            db,
            action="view_report",
            ip_address="127.0.0.1",
            resource_type="something_made_up",
        )

    db.add.assert_not_called()


def test_cannot_smuggle_a_health_value_in_as_the_action():
    # A lab result dressed up as an "action" string - this must be
    # rejected, not silently logged.
    db = MagicMock()

    with pytest.raises(ValueError):
        record_audit_event(
            db, action="Hemoglobin: 13.5 g/dL (HIGH)", ip_address="127.0.0.1"
        )

    db.add.assert_not_called()


def test_cannot_smuggle_a_health_value_in_as_the_resource_type():
    db = MagicMock()

    with pytest.raises(ValueError):
        record_audit_event(
            db,
            action="view_report",
            ip_address="127.0.0.1",
            resource_type="Patient has elevated glucose",
        )

    db.add.assert_not_called()


def test_no_field_exists_for_arbitrary_free_text():
    # The strongest guarantee: there is no parameter AT ALL that a
    # caller could stuff a health value, report content, or any other
    # free-form text into. If this test ever fails, someone added one.
    params = set(inspect.signature(record_audit_event).parameters.keys())
    forbidden_field_names = {
        "details",
        "data",
        "value",
        "content",
        "message",
        "notes",
        "metadata",
        "description",
        "payload",
    }
    assert params.isdisjoint(forbidden_field_names)


def test_allowed_lists_are_short_fixed_vocabularies_not_open_text():
    # Sanity check on the lists themselves: every entry is a short,
    # code-like label - not a sentence, which is what a leaked health
    # value smuggled in as a new "action" would look like.
    for action in ALLOWED_ACTIONS:
        assert " " not in action
        assert len(action) < 40
    for resource_type in ALLOWED_RESOURCE_TYPES:
        assert " " not in resource_type
        assert len(resource_type) < 40
