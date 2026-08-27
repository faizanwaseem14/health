"""
Tests for app/routers/shares.py: the protected share-management routes
(create/list/revoke/access-history) and the PUBLIC doctor view.

No live database - db is a MagicMock and app.sharing.service's own
functions are mocked at their call sites in the router, since their
real behavior (including the actual atomic-access-grant SQL) is
already covered by tests/test_sharing_service.py and, for real SQL
semantics, a throwaway local Postgres database (see the Task summary).
What's verified here is routing/wiring: ownership is enforced, a
result_id that doesn't belong to the report is rejected before
app.sharing.service is ever called (the concrete cross-report leak
this guards against), and ShareUnavailableError becomes one uniform
404 no matter why it was raised.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_db
from app.main import app
from app.models import Report, Result, Share, User
from app.routers.reports import require_owned_report
from app.routers.shares import _share_status, require_owned_share
from app.sharing.service import ShareUnavailableError

client = TestClient(app)


def _clear_overrides():
    app.dependency_overrides.clear()


def _make_share(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        profile_id=uuid.uuid4(),
        report_id=uuid.uuid4(),
        shared_by_user_id=uuid.uuid4(),
        share_token="a-real-looking-token",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        revoked_at=None,
        access_count=0,
        max_views=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Share(**defaults)


# --- _share_status ---


def test_share_status_active_by_default():
    assert _share_status(_make_share()) == "active"


def test_share_status_revoked_wins_even_if_not_expired():
    share = _make_share(revoked_at=datetime.now(timezone.utc))
    assert _share_status(share) == "revoked"


def test_share_status_expired():
    share = _make_share(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    assert _share_status(share) == "expired"


def test_share_status_exhausted_when_access_count_reaches_max_views():
    share = _make_share(max_views=3, access_count=3)
    assert _share_status(share) == "exhausted"


def test_share_status_active_when_under_max_views():
    share = _make_share(max_views=3, access_count=2)
    assert _share_status(share) == "active"


# --- create share ---


def test_create_share_requires_login():
    response = client.post(f"/reports/{uuid.uuid4()}/shares", json={})
    assert response.status_code == 401


def test_create_share_rejects_a_result_id_that_belongs_to_a_different_report():
    # The exact cross-report/cross-user leak guard: a result_id in the
    # payload that isn't among this report's own results must never
    # reach app.sharing.service, however it got there.
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    user = User(id=uuid.uuid4())
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value = []  # none owned

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_report] = lambda: report
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        with patch("app.routers.shares.create_share") as mock_create:
            response = client.post(
                f"/reports/{report.id}/shares",
                json={"result_ids": [str(uuid.uuid4())]},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 422
    mock_create.assert_not_called()


def test_create_share_succeeds_and_records_an_audit_event():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    user = User(id=uuid.uuid4())
    fake_db = MagicMock()
    fake_share = _make_share(report_id=report.id)

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_report] = lambda: report
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        with (
            patch(
                "app.routers.shares.create_share", return_value=fake_share
            ) as mock_create,
            patch("app.routers.shares.record_audit_event") as mock_audit,
        ):
            response = client.post(
                f"/reports/{report.id}/shares",
                json={"expires_in_days": 5, "max_views": 10},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["share_token"] == fake_share.share_token
    assert body["status"] == "active"
    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["expires_in_days"] == 5
    assert mock_create.call_args.kwargs["max_views"] == 10
    assert mock_audit.call_args.kwargs["action"] == "create_share"


# --- list shares ---


def test_list_shares_requires_login():
    response = client.get(f"/reports/{uuid.uuid4()}/shares")
    assert response.status_code == 401


def test_list_shares_returns_every_share_for_the_report():
    report = Report(id=uuid.uuid4(), profile_id=uuid.uuid4())
    fake_db = MagicMock()
    shares = [_make_share(report_id=report.id), _make_share(report_id=report.id)]
    query = fake_db.query.return_value.filter.return_value
    query.order_by.return_value.all.return_value = shares

    app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
    app.dependency_overrides[require_owned_report] = lambda: report
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.get(f"/reports/{report.id}/shares")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert len(response.json()["data"]) == 2


# --- revoke ---


def test_revoke_share_requires_login():
    response = client.delete(f"/shares/{uuid.uuid4()}")
    assert response.status_code == 401


def test_revoke_share_sets_revoked_at():
    share = _make_share()
    fake_db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
    app.dependency_overrides[require_owned_share] = lambda: share
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        with patch("app.routers.shares.record_audit_event") as mock_audit:
            response = client.delete(f"/shares/{share.id}")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert share.revoked_at is not None
    assert response.json()["data"]["status"] == "revoked"
    assert mock_audit.call_args.kwargs["action"] == "revoke_share"


def test_revoke_share_denies_someone_elses_share():
    share = _make_share()
    fake_db = MagicMock()
    fake_db.get.return_value = share

    app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.delete(f"/shares/{share.id}")
    finally:
        _clear_overrides()

    assert response.status_code == 404
    assert share.revoked_at is None


# --- access history ---


def test_list_share_accesses_requires_login():
    response = client.get(f"/shares/{uuid.uuid4()}/accesses")
    assert response.status_code == 401


def test_list_share_accesses_returns_view_timestamps():
    share = _make_share()
    fake_db = MagicMock()
    fake_access = MagicMock(
        created_at=datetime.now(timezone.utc), ip_address="203.0.113.5"
    )
    query = fake_db.query.return_value.filter.return_value.filter.return_value
    query.order_by.return_value.all.return_value = [fake_access]

    app.dependency_overrides[get_current_user] = lambda: User(id=uuid.uuid4())
    app.dependency_overrides[require_owned_share] = lambda: share
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.get(f"/shares/{share.id}/accesses")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ip_address"] == "203.0.113.5"


# --- public doctor view ---


def test_public_share_view_denies_uniformly_when_the_share_is_unavailable():
    # Covers "expired denied", "revoked denied", "over-limit denied",
    # and "unknown token denied" all landing on the SAME response shape
    # - resolve_share_access is what actually decides which of those
    # apply (verified for real against Postgres); the router's job,
    # checked here, is to never leak which reason it was.
    with patch(
        "app.routers.shares.resolve_share_access", side_effect=ShareUnavailableError()
    ):
        response = client.get("/public/shares/some-token")

    assert response.status_code == 404
    assert "no longer available" in response.json()["detail"]


def test_public_share_view_returns_the_scoped_report_and_results_on_success():
    fake_db = MagicMock()
    share = _make_share()
    report = Report(
        id=share.report_id,
        profile_id=uuid.uuid4(),
        original_filename="labs.pdf",
        display_name=None,
        report_date=None,
        created_at=datetime.now(timezone.utc),
    )
    result = Result(
        id=uuid.uuid4(),
        report_id=share.report_id,
        raw_test_name="Hemoglobin",
        canonical_test_name="Hemoglobin",
        value="13.5",
        unit="g/dL",
        reference_range_text="12.0 - 15.5",
        flag="normal",
    )

    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        with (
            patch("app.routers.shares.resolve_share_access", return_value=share),
            patch("app.routers.shares.record_audit_event") as mock_audit,
            patch(
                "app.routers.shares.get_shared_report_data",
                return_value=MagicMock(report=report, results=[result]),
            ),
        ):
            response = client.get(f"/public/shares/{share.share_token}")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["report"]["original_filename"] == "labs.pdf"
    assert len(data["results"]) == 1
    assert data["results"][0]["raw_test_name"] == "Hemoglobin"
    assert data["results"][0]["flag"] == "normal"
    assert mock_audit.call_args.kwargs["action"] == "view_share"
    assert mock_audit.call_args.kwargs["resource_id"] == share.id
    assert mock_audit.call_args.kwargs.get("user_id") is None
