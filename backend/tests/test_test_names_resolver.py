"""
Tests for the test-name catalog resolver (app/test_names/resolver.py).
No live database - db is a MagicMock, same pattern as
test_trust_service.py.
"""

import uuid
from unittest.mock import MagicMock

from app.models import Result, TestAlias
from app.test_names.resolver import normalize_test_name, resolve_aliases_for_report

# --- normalize_test_name ---


def test_normalize_collapses_case_and_whitespace():
    assert normalize_test_name("HGB") == normalize_test_name("  Hgb  ")


def test_normalize_strips_a_trailing_period():
    assert normalize_test_name("Total Chol.") == normalize_test_name("Total Chol")


def test_normalize_collapses_internal_whitespace():
    assert normalize_test_name("White  Blood   Cells") == normalize_test_name(
        "White Blood Cells"
    )


# --- resolve_aliases_for_report ---


def _alias(raw_name, canonical_name="Hemoglobin"):
    return TestAlias(id=uuid.uuid4(), raw_name=raw_name, canonical_name=canonical_name)


def _result(report_id, raw_test_name, canonical_test_name=None):
    return Result(
        id=uuid.uuid4(),
        report_id=report_id,
        raw_test_name=raw_test_name,
        canonical_test_name=canonical_test_name,
        value="13.5",
    )


def _fake_db(results, aliases):
    fake_db = MagicMock()

    def query_side_effect(model):
        mock = MagicMock()
        if model is Result:
            mock.filter.return_value.all.return_value = results
        elif model is TestAlias:
            mock.all.return_value = aliases
        return mock

    fake_db.query.side_effect = query_side_effect
    return fake_db


def test_resolves_by_raw_test_name_case_and_format_insensitively():
    report_id = uuid.uuid4()
    # Different case/whitespace/trailing-period than the catalog entry,
    # but the same underlying name once normalized.
    result = _result(report_id, "  HEMOGLOBIN.  ")
    alias = _alias("Hemoglobin")
    fake_db = _fake_db([result], [alias])

    resolve_aliases_for_report(fake_db, report_id)

    assert result.test_alias_id == alias.id
    fake_db.commit.assert_called_once()


def test_falls_back_to_the_ai_canonical_guess_when_raw_name_is_unrecognized():
    report_id = uuid.uuid4()
    # "H-G-B" isn't in the catalog, but the AI's own canonical guess is.
    result = _result(report_id, "H-G-B", canonical_test_name="Hemoglobin")
    alias = _alias("Hemoglobin")
    fake_db = _fake_db([result], [alias])

    resolve_aliases_for_report(fake_db, report_id)

    assert result.test_alias_id == alias.id


def test_leaves_test_alias_id_none_when_nothing_matches():
    report_id = uuid.uuid4()
    result = _result(report_id, "Some Totally Unknown Test", canonical_test_name=None)
    fake_db = _fake_db([result], [_alias("Hemoglobin")])

    resolve_aliases_for_report(fake_db, report_id)

    assert result.test_alias_id is None


def test_a_report_with_zero_results_does_nothing():
    fake_db = _fake_db([], [])

    resolve_aliases_for_report(fake_db, uuid.uuid4())

    fake_db.commit.assert_not_called()
