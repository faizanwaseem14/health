"""
Tests for backfill_alias_matches (app/test_names/backfill.py) - the
maintenance script that re-runs catalog matching against reports that
were processed before test_aliases was seeded (or before it had the
entries needed to match them). No live database - db is a MagicMock;
resolve_aliases_for_report itself is already covered against real
Postgres by tests/test_test_names_resolver.py.
"""

import uuid
from unittest.mock import MagicMock, patch

from app.test_names.backfill import backfill_alias_matches


def test_re_resolves_every_distinct_report_that_has_results():
    report_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    fake_db = MagicMock()
    fake_db.query.return_value.distinct.return_value.all.return_value = [
        (report_id,) for report_id in report_ids
    ]

    with patch("app.test_names.backfill.resolve_aliases_for_report") as mock_resolve:
        resolved_count = backfill_alias_matches(fake_db)

    assert resolved_count == 3
    assert mock_resolve.call_count == 3
    resolved_report_ids = {call.args[1] for call in mock_resolve.call_args_list}
    assert resolved_report_ids == set(report_ids)


def test_does_nothing_when_no_report_has_any_results():
    fake_db = MagicMock()
    fake_db.query.return_value.distinct.return_value.all.return_value = []

    with patch("app.test_names.backfill.resolve_aliases_for_report") as mock_resolve:
        resolved_count = backfill_alias_matches(fake_db)

    assert resolved_count == 0
    mock_resolve.assert_not_called()
