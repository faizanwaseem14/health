"""
Tests for app/sharing/service.py - share-link creation, atomic
access resolution, and the data a share exposes.

No live database - db is a MagicMock, so what's verified here is the
LOGIC around the database (the redoable-closure shape create_share
uses with commit_with_retry, how resolve_share_access interprets its
query's result, and how get_shared_report_data scopes results) - not
the actual SQL semantics (a real UPDATE...WHERE really does deny an
expired/revoked/over-limit token, two racing requests really can't
both get the last view, ...). Those are verified for real against a
throwaway local Postgres database - see the Task summary for that run.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import OperationalError

import app.sharing.service as sharing_service
from app.models import Report, Result
from app.sharing.service import (
    ShareUnavailableError,
    create_share,
    generate_share_token,
    get_shared_report_data,
    resolve_share_access,
)


def _operational_error():
    return OperationalError("UPDATE ...", {}, Exception("server closed the connection"))


# --- generate_share_token ---


def test_generate_share_token_is_long_and_unpredictable():
    tokens = {generate_share_token() for _ in range(20)}

    assert len(tokens) == 20  # no collisions across 20 draws
    assert all(len(token) >= 32 for token in tokens)


# --- create_share ---


def test_create_share_adds_the_share_and_its_result_scoping():
    db = MagicMock()
    profile_id = uuid.uuid4()
    report_id = uuid.uuid4()
    user_id = uuid.uuid4()
    result_ids = [uuid.uuid4(), uuid.uuid4()]

    with patch("app.sharing.service.commit_with_retry") as mock_retry:
        create_share(
            db,
            profile_id=profile_id,
            report_id=report_id,
            shared_by_user_id=user_id,
            expires_in_days=7,
            max_views=5,
            result_ids=result_ids,
        )
        # Actually run the mutate() commit_with_retry was handed, since
        # we've mocked commit_with_retry itself away above.
        mutate = mock_retry.call_args.args[1]
        mutate()

    added = [call.args[0] for call in db.add.call_args_list]
    assert len(added) == 3  # the Share + 2 ShareResult rows
    share = added[0]
    assert share.profile_id == profile_id
    assert share.report_id == report_id
    assert share.shared_by_user_id == user_id
    assert share.max_views == 5
    assert {row.result_id for row in added[1:]} == set(result_ids)
    assert all(row.share_id == share.id for row in added[1:])


def test_create_share_with_no_result_ids_creates_only_the_share():
    db = MagicMock()

    with patch("app.sharing.service.commit_with_retry") as mock_retry:
        create_share(
            db,
            profile_id=uuid.uuid4(),
            report_id=uuid.uuid4(),
            shared_by_user_id=uuid.uuid4(),
            expires_in_days=7,
            max_views=None,
            result_ids=None,
        )
        mutate = mock_retry.call_args.args[1]
        mutate()

    assert db.add.call_count == 1


def test_create_share_rebuilds_the_same_share_id_and_token_on_every_retry_attempt():
    # The critical correctness property: a rollback() before a retry
    # (commit_with_retry's own behavior on a transient error) discards
    # whatever mutate() staged - so mutate() must be safe to call twice
    # and produce the SAME share id/token both times, not a fresh one,
    # or the two attempts would silently create two different shares
    # with two different tokens for what should be one logical create.
    db = MagicMock()
    db.commit.side_effect = [_operational_error(), None]

    with patch("app.database.time.sleep"):
        create_share(
            db,
            profile_id=uuid.uuid4(),
            report_id=uuid.uuid4(),
            shared_by_user_id=uuid.uuid4(),
            expires_in_days=7,
            max_views=None,
            result_ids=None,
        )

    added_shares = [
        call.args[0]
        for call in db.add.call_args_list
        if hasattr(call.args[0], "share_token")
    ]
    assert len(added_shares) == 2  # mutate() ran twice (retry)
    assert added_shares[0].id == added_shares[1].id
    assert added_shares[0].share_token == added_shares[1].share_token


def test_create_share_expires_at_is_in_the_future_by_the_requested_days():
    db = MagicMock()
    before = datetime.now(timezone.utc)

    with patch("app.sharing.service.commit_with_retry") as mock_retry:
        create_share(
            db,
            profile_id=uuid.uuid4(),
            report_id=uuid.uuid4(),
            shared_by_user_id=uuid.uuid4(),
            expires_in_days=3,
            max_views=None,
            result_ids=None,
        )
        mutate = mock_retry.call_args.args[1]
        mutate()

    share = db.add.call_args_list[0].args[0]
    lower_bound = before + timedelta(days=3)
    upper_bound = before + timedelta(days=3, seconds=5)
    assert lower_bound <= share.expires_at <= upper_bound


# --- resolve_share_access ---


def test_resolve_share_access_returns_the_share_when_the_update_matches_a_row():
    db = MagicMock()
    share_id = uuid.uuid4()
    db.execute.return_value.scalar_one_or_none.return_value = share_id
    fake_share = MagicMock()
    db.get.return_value = fake_share

    with patch(
        "app.sharing.service.commit_with_retry",
        side_effect=lambda d, mutate: mutate(),
    ):
        result = resolve_share_access(db, "some-token")

    assert result is fake_share
    db.get.assert_called_once_with(sharing_service.Share, share_id)


def test_resolve_share_access_raises_when_nothing_matches():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    with patch(
        "app.sharing.service.commit_with_retry",
        side_effect=lambda d, mutate: mutate(),
    ):
        try:
            resolve_share_access(db, "some-token")
            assert False, "expected ShareUnavailableError"
        except ShareUnavailableError:
            pass


# --- get_shared_report_data ---


def test_get_shared_report_data_scopes_to_the_chosen_results_when_present():
    db = MagicMock()
    share = MagicMock(id=uuid.uuid4(), report_id=uuid.uuid4())
    scoped_id = uuid.uuid4()

    db.query.return_value.filter.return_value = [MagicMock(result_id=scoped_id)]
    db.get.return_value = MagicMock(spec=Report)

    filtered_query = MagicMock()
    filtered_query.filter.return_value = filtered_query  # .filter() chains onto itself
    ordered_results = [MagicMock(spec=Result)]
    filtered_query.order_by.return_value.all.return_value = ordered_results

    def query_side_effect(model):
        if model is Result:
            q = MagicMock()
            q.filter.return_value = filtered_query
            return q
        # ShareResult.result_id query
        q = MagicMock()
        q.filter.return_value = [MagicMock(result_id=scoped_id)]
        return q

    db.query.side_effect = query_side_effect

    data = get_shared_report_data(db, share)

    filtered_query.filter.assert_called_once()
    assert data.results == ordered_results


def test_get_shared_report_data_returns_every_result_when_no_scoping_rows_exist():
    db = MagicMock()
    share = MagicMock(id=uuid.uuid4(), report_id=uuid.uuid4())
    db.get.return_value = MagicMock(spec=Report)

    unfiltered_query = MagicMock()
    all_results = [MagicMock(spec=Result), MagicMock(spec=Result)]
    unfiltered_query.order_by.return_value.all.return_value = all_results

    def query_side_effect(model):
        if model is Result:
            q = MagicMock()
            q.filter.return_value = unfiltered_query
            return q
        q = MagicMock()
        q.filter.return_value = []  # no ShareResult rows -> whole report
        return q

    db.query.side_effect = query_side_effect

    data = get_shared_report_data(db, share)

    unfiltered_query.filter.assert_not_called()
    assert data.results == all_results
