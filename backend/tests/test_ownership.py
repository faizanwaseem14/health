"""
Tests for the reusable ownership guard.

The real resolver functions (_owner_of_report, _owner_of_result, ...) run
real SQL joins, so they need a real database to prove for real - see the
Task 12 summary for the scratch-Postgres run that verified those across
multiple tables (report, result, correction, share) for two different
users. What we test here, with no database needed, is the GENERIC
guard logic itself: found+owned -> return the row, found+not-owned ->
404, not-found -> 404. We register a fake throwaway model to test that
logic in complete isolation from any real table.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth.ownership import require_owned_row


class _FakeModel:
    """A throwaway stand-in model, used only so we don't need a real table."""


def test_require_owned_row_returns_the_row_when_owned():
    fake_user = SimpleNamespace(id="user-1")
    fake_row = SimpleNamespace(id="row-1")
    db = MagicMock()
    db.get.return_value = fake_row

    with patch.dict(
        "app.auth.ownership._OWNER_RESOLVERS", {_FakeModel: lambda db, row: "user-1"}
    ):
        dependency = require_owned_row(_FakeModel)
        result = dependency(row_id="row-1", db=db, current_user=fake_user)

    assert result is fake_row


def test_require_owned_row_404s_for_someone_elses_row():
    fake_user = SimpleNamespace(id="user-1")
    fake_row = SimpleNamespace(id="row-1")
    db = MagicMock()
    db.get.return_value = fake_row

    with patch.dict(
        "app.auth.ownership._OWNER_RESOLVERS",
        {_FakeModel: lambda db, row: "someone-else"},
    ):
        dependency = require_owned_row(_FakeModel)
        with pytest.raises(HTTPException) as exc_info:
            dependency(row_id="row-1", db=db, current_user=fake_user)

    assert exc_info.value.status_code == 404


def test_require_owned_row_404s_when_the_row_does_not_exist():
    fake_user = SimpleNamespace(id="user-1")
    db = MagicMock()
    db.get.return_value = None

    with patch.dict(
        "app.auth.ownership._OWNER_RESOLVERS", {_FakeModel: lambda db, row: "user-1"}
    ):
        dependency = require_owned_row(_FakeModel)
        with pytest.raises(HTTPException) as exc_info:
            dependency(row_id="missing", db=db, current_user=fake_user)

    assert exc_info.value.status_code == 404


def test_every_owned_table_has_a_registered_resolver():
    # Regression guard: if someone adds a new per-user table to the
    # schema and forgets to register how to find its owner, this fails
    # loudly instead of silently leaving that table unprotected.
    from app.auth.ownership import _OWNER_RESOLVERS
    from app.models import Correction, Explanation, Job, Profile, Report, Result, Share

    expected_models = {Profile, Report, Result, Correction, Job, Explanation, Share}
    assert expected_models.issubset(_OWNER_RESOLVERS.keys())
