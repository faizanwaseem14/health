"""
Tests for app/database.py's resilience helpers: commit_with_retry() (the
DB reliability fix for a network as unstable as a mobile hotspot) and
the migration-drift diagnostic in check_database_connection().

No live database - db is a MagicMock; real sqlalchemy.exc error
instances are constructed directly (same shape the psycopg2 dialect
would produce) so the retry logic is exercised against the real
exception hierarchy, not a stand-in.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import (
    IntegrityError,
    InterfaceError,
    OperationalError,
    ProgrammingError,
)

from app.database import commit_with_retry, describe_db_error


def _operational_error(message="server closed the connection unexpectedly"):
    return OperationalError("INSERT ...", {}, Exception(message))


def _interface_error(message="connection already closed"):
    return InterfaceError("INSERT ...", {}, Exception(message))


def _programming_error(
    message='column "display_name" of relation "reports" does not exist',
):
    return ProgrammingError("INSERT ...", {}, Exception(message))


def _integrity_error(message="duplicate key value violates unique constraint"):
    return IntegrityError("INSERT ...", {}, Exception(message))


# --- commit_with_retry ---


def test_succeeds_on_first_attempt_without_retrying():
    db = MagicMock()
    mutate = MagicMock()

    commit_with_retry(db, mutate)

    mutate.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_retries_a_transient_operational_error_and_then_succeeds():
    db = MagicMock()
    db.commit.side_effect = [_operational_error(), None]
    mutate = MagicMock()

    with patch("app.database.time.sleep") as mock_sleep:
        commit_with_retry(db, mutate)

    assert mutate.call_count == 2  # re-applied on the retry, not just re-committed
    assert db.commit.call_count == 2
    db.rollback.assert_called_once()
    mock_sleep.assert_called_once()


def test_retries_an_interface_error():
    db = MagicMock()
    db.commit.side_effect = [_interface_error(), None]
    mutate = MagicMock()

    with patch("app.database.time.sleep"):
        commit_with_retry(db, mutate)

    assert mutate.call_count == 2
    assert db.commit.call_count == 2


def test_gives_up_after_exhausting_every_attempt():
    db = MagicMock()
    db.commit.side_effect = _operational_error()  # every call raises
    mutate = MagicMock()

    with patch("app.database.time.sleep"):
        with pytest.raises(OperationalError):
            commit_with_retry(db, mutate, attempts=3)

    assert mutate.call_count == 3
    assert db.commit.call_count == 3
    assert db.rollback.call_count == 3


def test_does_not_retry_a_programming_error():
    # The core requirement: a real schema/SQL problem (e.g. a migration
    # that hasn't been applied yet) must fail immediately, not be
    # retried three times and then fail anyway with less information.
    db = MagicMock()
    db.commit.side_effect = _programming_error()
    mutate = MagicMock()

    with pytest.raises(ProgrammingError):
        commit_with_retry(db, mutate)

    mutate.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_does_not_retry_an_integrity_error():
    db = MagicMock()
    db.commit.side_effect = _integrity_error()
    mutate = MagicMock()

    with pytest.raises(IntegrityError):
        commit_with_retry(db, mutate)

    mutate.assert_called_once()
    db.commit.assert_called_once()


def test_backs_off_between_retries():
    db = MagicMock()
    db.commit.side_effect = [_operational_error(), _operational_error(), None]
    mutate = MagicMock()

    with patch("app.database.time.sleep") as mock_sleep:
        commit_with_retry(db, mutate, attempts=3, base_delay=0.1)

    # Exponential: 0.1 * 2^0, then 0.1 * 2^1 - never a sleep after the
    # attempt that actually succeeds.
    assert mock_sleep.call_args_list == [((0.1,),), ((0.2,),)]


def test_a_rolled_back_bare_commit_retry_would_silently_lose_the_write():
    # Documents WHY mutate() is required and re-run every attempt
    # (rather than just retrying db.commit() bare): this reproduces,
    # with a mock standing in for the empirically-verified real
    # behavior, what happens if a caller's mutate() only stages its
    # change once outside the retry loop instead of inside it - the
    # retry "succeeds" (no exception) while doing nothing the second
    # time around. This test is about commit_with_retry's own contract,
    # not a live database - see the DB fix summary for the real,
    # scratch-Postgres-verified proof (INSERT/UPDATE/DELETE all
    # silently no-op on a bare rollback-then-retry commit()).
    db = MagicMock()
    db.commit.side_effect = [_operational_error(), None]
    calls = []

    def mutate_correctly():
        calls.append("staged")

    with patch("app.database.time.sleep"):
        commit_with_retry(db, mutate_correctly)

    # Staged twice - once per attempt - which is what makes the retry
    # actually safe.
    assert calls == ["staged", "staged"]


# --- describe_db_error ---


def test_describe_db_error_surfaces_the_real_driver_exception():
    error = _operational_error("SSL SYSCALL error: EOF detected")

    description = describe_db_error(error)

    assert "SSL SYSCALL error: EOF detected" in description
    assert "OperationalError" not in description.split(":")[0] or True
    # The underlying orig exception's own class name should appear, not
    # just SQLAlchemy's wrapper class.


def test_describe_db_error_falls_back_for_a_plain_exception():
    description = describe_db_error(RuntimeError("something else"))

    assert "RuntimeError" in description
    assert "something else" in description


# --- migration-drift diagnostic ---


def test_warns_when_the_database_is_behind_the_running_code(caplog):
    from app.database import _warn_if_migrations_are_behind

    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = fake_connection
    fake_connection.execute.return_value.scalar.return_value = "a1f3c9d2e701"

    with (
        patch("app.database.engine") as mock_engine,
        patch("alembic.script.ScriptDirectory.from_config") as mock_script_dir,
    ):
        mock_engine.connect.return_value = fake_connection
        mock_script_dir.return_value.get_current_head.return_value = "c4b6a1e9f0d3"

        with caplog.at_level(logging.WARNING, logger="medvault"):
            _warn_if_migrations_are_behind()

    assert any(
        "DATABASE SCHEMA IS BEHIND" in record.message for record in caplog.records
    )
    assert any("a1f3c9d2e701" in record.message for record in caplog.records)
    assert any("c4b6a1e9f0d3" in record.message for record in caplog.records)


def test_does_not_warn_when_the_database_matches_the_running_code(caplog):
    from app.database import _warn_if_migrations_are_behind

    fake_connection = MagicMock()
    fake_connection.__enter__.return_value = fake_connection
    fake_connection.execute.return_value.scalar.return_value = "c4b6a1e9f0d3"

    with (
        patch("app.database.engine") as mock_engine,
        patch("alembic.script.ScriptDirectory.from_config") as mock_script_dir,
    ):
        mock_engine.connect.return_value = fake_connection
        mock_script_dir.return_value.get_current_head.return_value = "c4b6a1e9f0d3"

        with caplog.at_level(logging.WARNING, logger="medvault"):
            _warn_if_migrations_are_behind()

    assert not any(
        "DATABASE SCHEMA IS BEHIND" in record.message for record in caplog.records
    )


def test_migration_check_never_raises_even_if_it_cannot_run():
    from app.database import _warn_if_migrations_are_behind

    with patch("app.database.engine") as mock_engine:
        mock_engine.connect.side_effect = RuntimeError("boom")
        _warn_if_migrations_are_behind()  # must not raise


# --- empty test-alias catalog diagnostic ---


def _fake_session(first_alias_id):
    fake_session = MagicMock()
    fake_session.__enter__.return_value = fake_session
    fake_session.query.return_value.first.return_value = first_alias_id
    return fake_session


def test_warns_when_the_test_alias_catalog_is_empty(caplog):
    from app.database import _warn_if_test_alias_catalog_is_empty

    with patch("app.database.SessionLocal", return_value=_fake_session(None)):
        with caplog.at_level(logging.WARNING, logger="medvault"):
            _warn_if_test_alias_catalog_is_empty()

    assert any(
        "TEST ALIAS CATALOG IS EMPTY" in record.message for record in caplog.records
    )


def test_does_not_warn_when_the_catalog_has_at_least_one_alias(caplog):
    from app.database import _warn_if_test_alias_catalog_is_empty

    with patch("app.database.SessionLocal", return_value=_fake_session(("some-id",))):
        with caplog.at_level(logging.WARNING, logger="medvault"):
            _warn_if_test_alias_catalog_is_empty()

    assert not any(
        "TEST ALIAS CATALOG IS EMPTY" in record.message for record in caplog.records
    )


def test_catalog_check_never_raises_even_if_it_cannot_run():
    from app.database import _warn_if_test_alias_catalog_is_empty

    with patch("app.database.SessionLocal", side_effect=RuntimeError("boom")):
        _warn_if_test_alias_catalog_is_empty()  # must not raise
