"""
The final cross-user security gate: for every route that takes a
resource id in its path and is meant to be reachable only by its
owner, proves that a DIFFERENT logged-in user gets exactly a 404 -
never a 403 (which would confirm the row exists), never a 200, and
never "whatever happens to fall out of an unmocked network call" (see
below for why that distinction matters).

Every one of these routes is already guarded by the SAME generic
dependency (require_owned_row - see app/auth/ownership.py), whose core
allow/deny logic is already exhaustively unit-tested in isolation in
test_ownership.py. What THIS file proves, route by route, is that each
one is actually wired to that guard and that the wiring produces a
real 404 - not that "some error happens to occur".

That distinction is the reason this file exists rather than just
trusting the pattern used by several older tests in this codebase
(test_reports.py's test_upload_rejects_someone_elses_profile,
test_retry_rejects_someone_elses_report; test_ocr_router.py's
test_list_ocr_words_rejects_someone_elses_report; and this file's own
test_shares_router.py sibling test_revoke_share_denies_someone_elses_share)
of deliberately NOT overriding require_owned_report/require_owned_share
and letting the request hit a real (fake, unreachable) database
connection, asserting "404 or 503". That pattern only proves a request
gets rejected SOMEHOW - a 503 there proves nothing about ownership at
all, since it would happen identically even if the ownership check
were deleted outright (the very next line of code would still try to
touch the database and fail the same way). It is a smoke test for "the
route doesn't crash uncontrolled", not a security proof.

Here, `db` is a MagicMock configured to return a REAL row owned by a
DIFFERENT user (never `None`, so a "not found" 404 can't be mistaken
for an "not yours" 404), and require_owned_report/require_owned_profile/
require_owned_share/require_owned_result are NOT overridden - the real
dependency runs, actually calls the (mocked) resolver query, and its
own decision is what produces the 404. That is what "ownership -> 404"
actually means, proven for real for every route below.
"""

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_db
from app.main import app
from app.models import Profile, Report, Result, Share, User
from app.routers.reports import require_owned_profile, require_owned_report
from app.routers.results import require_owned_result
from app.routers.shares import require_owned_share

client = TestClient(app)


def _clear_overrides():
    app.dependency_overrides.clear()


def _fake_db_owned_by_someone_else(row, owner_id):
    """
    A MagicMock db that: (a) returns `row` from db.get(...) - so the
    row genuinely exists, and (b) resolves EVERY shape the various
    _owner_of_* resolvers query in (a direct column read needs no
    query; report/profile ownership is one query+filter+scalar;
    result ownership adds a join) to `owner_id`, a user that is NOT
    the one making the request.
    """
    fake_db = MagicMock()
    fake_db.get.return_value = row
    fake_db.query.return_value.filter.return_value.scalar.return_value = owner_id
    join_chain = fake_db.query.return_value.join.return_value
    join_chain.filter.return_value.scalar.return_value = owner_id
    return fake_db


def _override_as_a_different_user(row, owner_id):
    requester = User(id=uuid.uuid4())
    fake_db = _fake_db_owned_by_someone_else(row, owner_id)
    app.dependency_overrides[get_current_user] = lambda: requester
    app.dependency_overrides[get_db] = lambda: fake_db


# --- reports.py ---


def test_get_report_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.get(f"/reports/{report.id}")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_rename_report_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.patch(
            f"/reports/{report.id}", json={"display_name": "Mine now"}
        )
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_delete_report_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.delete(f"/reports/{report.id}")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_retry_report_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.post(f"/reports/{report.id}/retry")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_report_trends_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.get(f"/reports/{report.id}/trends")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_list_reports_for_profile_denies_a_profile_you_dont_own():
    profile = Profile(id=uuid.uuid4(), user_id=uuid.uuid4(), full_name="Not You")
    _override_as_a_different_user(profile, profile.user_id)
    try:
        response = client.get(f"/profiles/{profile.id}/reports")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_upload_denies_a_profile_you_dont_own():
    profile = Profile(id=uuid.uuid4(), user_id=uuid.uuid4(), full_name="Not You")
    _override_as_a_different_user(profile, profile.user_id)
    try:
        response = client.post(
            f"/profiles/{profile.id}/reports",
            files={
                "file": ("photo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")
            },
        )
    finally:
        _clear_overrides()
    assert response.status_code == 404


# --- results.py ---


def test_list_results_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.get(f"/reports/{report.id}/results")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_generate_explanations_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.post(f"/reports/{report.id}/explanations")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_create_correction_denies_a_result_you_dont_own():
    result = Result(
        id=uuid.uuid4(), report_id=uuid.uuid4(), raw_test_name="Hgb", value="1"
    )
    _override_as_a_different_user(result, uuid.uuid4())
    try:
        response = client.post(
            f"/results/{result.id}/corrections",
            json={"field_name": "value", "new_value": "2"},
        )
    finally:
        _clear_overrides()
    assert response.status_code == 404


# --- ocr.py ---


def test_list_ocr_words_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.get(f"/reports/{report.id}/ocr-words")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_get_report_page_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.get(f"/reports/{report.id}/pages/1")
    finally:
        _clear_overrides()
    assert response.status_code == 404


# --- shares.py (management routes - the public doctor view has no
# concept of "ownership" at all; its own denial semantics - expired,
# revoked, over-limit, unknown token, all indistinguishable - are
# covered in test_shares_router.py and verified for real against
# Postgres, see the Task summary) ---


def _make_share(**overrides):
    from datetime import datetime, timedelta, timezone

    defaults = dict(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        shared_by_user_id=uuid.uuid4(),
        share_token="tok",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    defaults.update(overrides)
    return Share(**defaults)


def test_create_share_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        with patch("app.routers.shares.create_share") as mock_create:
            response = client.post(f"/reports/{report.id}/shares", json={})
    finally:
        _clear_overrides()
    assert response.status_code == 404
    mock_create.assert_not_called()


def test_list_shares_denies_a_report_you_dont_own():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    _override_as_a_different_user(report, uuid.uuid4())
    try:
        response = client.get(f"/reports/{report.id}/shares")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_revoke_share_denies_a_share_you_dont_own():
    share = _make_share()
    _override_as_a_different_user(share, share.shared_by_user_id)
    try:
        response = client.delete(f"/shares/{share.id}")
    finally:
        _clear_overrides()
    assert response.status_code == 404


def test_share_accesses_denies_a_share_you_dont_own():
    share = _make_share()
    _override_as_a_different_user(share, share.shared_by_user_id)
    try:
        response = client.get(f"/shares/{share.id}/accesses")
    finally:
        _clear_overrides()
    assert response.status_code == 404


# --- confirms the dependency objects imported above are exactly the
# ones actually wired into the routes tested (a stale import here would
# silently make every override no-op and every test above a false
# positive) ---


def test_the_dependencies_used_here_are_the_ones_the_routes_actually_use():
    from app.routers import ocr, reports, results, shares

    assert reports.require_owned_report is require_owned_report
    assert reports.require_owned_profile is require_owned_profile
    assert results.require_owned_result is require_owned_result
    assert shares.require_owned_share is require_owned_share
    # ocr.py reuses reports.require_owned_report directly (no alias of
    # its own) - confirm that import didn't drift either.
    assert ocr.require_owned_report is require_owned_report
