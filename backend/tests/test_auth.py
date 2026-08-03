"""
Tests for the Firebase token wrapper and the get_current_user dependency.

There's no way to get a REAL, validly-signed Firebase ID token without a
real Firebase project (which needs your own account - see SETUP.md), so
these tests mock the one boundary that requires that: the actual call to
Firebase's SDK. What we're testing is OUR code around that boundary -
that Firebase's errors get translated into our own clear exception type,
and that a protected route correctly rejects requests with no token.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from firebase_admin.auth import InvalidIdTokenError

from app.auth.firebase import InvalidFirebaseTokenError, verify_id_token
from app.main import app as fastapi_app

client = TestClient(fastapi_app)


def test_verify_id_token_returns_decoded_claims_on_success():
    fake_decoded_token = {"uid": "abc123", "phone_number": "+15551234567"}

    with (
        patch("app.auth.firebase._get_firebase_app", return_value=MagicMock()),
        patch(
            "app.auth.firebase.firebase_auth.verify_id_token",
            return_value=fake_decoded_token,
        ),
    ):
        result = verify_id_token("some-token")

    assert result == fake_decoded_token


def test_verify_id_token_wraps_firebase_errors_in_our_own_exception_type():
    with (
        patch("app.auth.firebase._get_firebase_app", return_value=MagicMock()),
        patch(
            "app.auth.firebase.firebase_auth.verify_id_token",
            side_effect=InvalidIdTokenError("bad token"),
        ),
    ):
        with pytest.raises(InvalidFirebaseTokenError):
            verify_id_token("garbage")


def test_auth_me_rejects_requests_with_no_token():
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_auth_me_rejects_an_invalid_token():
    with (
        patch("app.auth.firebase._get_firebase_app", return_value=MagicMock()),
        patch(
            "app.auth.firebase.firebase_auth.verify_id_token",
            side_effect=InvalidIdTokenError("bad token"),
        ),
    ):
        response = client.get(
            "/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )

    assert response.status_code == 401
