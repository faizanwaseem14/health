"""
A consolidated check of the API skeleton itself (Task 14): every
PROTECTED route requires a valid identity, and every PUBLIC route
doesn't. This is a regression guard - if someone adds a new route later
and forgets Depends(get_current_user) where it's needed, this list is
the place that catches it.

Routes that touch the database are mocked here so this test is
deterministic and doesn't depend on whether a real database happens to
be reachable from wherever tests run.
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import User

client = TestClient(app)

# Every route that should be BLOCKED (401) without a valid login.
PROTECTED_ROUTES = [
    ("GET", "/auth/me"),
    ("POST", "/auth/recovery/generate"),
]

# Every route that should work with NO login at all.
PUBLIC_ROUTES = [
    ("GET", "/"),
    ("GET", "/health"),
    ("POST", "/auth/otp/request"),
    ("POST", "/auth/recovery/redeem"),
]


def test_every_protected_route_rejects_requests_with_no_token():
    for method, path in PROTECTED_ROUTES:
        response = client.request(method, path)
        assert response.status_code == 401, f"{method} {path} should require login"


def test_every_public_route_never_returns_401():
    # Note: /auth/recovery/redeem can ALSO return 401 for a WRONG
    # recovery code - that's a different kind of "unauthorized" than
    # "you forgot to log in", so here we mock it to succeed. What we're
    # actually proving is that none of these routes need an
    # Authorization header at all to be reached - not that they can
    # never produce a 401 for any reason.
    fake_user = User(id=uuid.uuid4(), phone_number="+15551234567")

    with (
        patch("app.routers.health.check_database_connection", return_value=None),
        patch("app.routers.auth.check_and_record_otp_request", return_value=None),
        patch("app.routers.auth.redeem_recovery_code", return_value=fake_user),
    ):
        for method, path in PUBLIC_ROUTES:
            kwargs = {}
            if method == "POST":
                kwargs["json"] = {"phone_number": "+15551234567", "recovery_code": "x"}
            response = client.request(method, path, **kwargs)
            assert (
                response.status_code != 401
            ), f"{method} {path} should NOT require login"


def test_json_responses_have_json_content_type():
    with patch("app.routers.health.check_database_connection", return_value=None):
        response = client.get("/health")

    assert response.headers["content-type"] == "application/json"
