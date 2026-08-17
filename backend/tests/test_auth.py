"""
Tests for the Firebase token wrapper and the get_current_user dependency.

There's no way to get a REAL, validly-signed Firebase ID token without a
real Firebase project (which needs your own account - see SETUP.md), so
these tests mock the one boundary that requires that: the actual call to
Firebase's SDK. What we're testing is OUR code around that boundary -
that Firebase's errors get translated into our own clear exception type,
and that a protected route correctly rejects requests with no token.
"""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from firebase_admin.auth import InvalidIdTokenError

from app.auth import firebase as firebase_module
from app.auth.dependencies import resolve_or_create_user
from app.auth.firebase import InvalidFirebaseTokenError, verify_id_token
from app.config import settings
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


def test_resolve_or_create_user_accepts_an_email_only_token():
    # A Google sign-in token has no phone_number at all - only email.
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = None

    user = resolve_or_create_user(
        {"uid": "google-uid-1", "email": "alice@example.com"}, fake_db
    )

    added = fake_db.add.call_args[0][0]
    assert added is user
    assert user.firebase_uid == "google-uid-1"
    assert user.email == "alice@example.com"
    assert user.phone_number is None


def test_resolve_or_create_user_rejects_a_token_with_neither_phone_nor_email():
    fake_db = MagicMock()

    with pytest.raises(InvalidFirebaseTokenError):
        resolve_or_create_user({"uid": "some-uid"}, fake_db)


def test_resolve_or_create_user_backfills_email_onto_an_existing_phone_user():
    existing_user = MagicMock(phone_number="+15551234567", email=None)
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.first.return_value = existing_user

    user = resolve_or_create_user(
        {"uid": "abc123", "email": "alice@example.com"}, fake_db
    )

    assert user is existing_user
    assert user.email == "alice@example.com"
    fake_db.add.assert_not_called()


def test_get_firebase_app_prefers_the_service_account_file_when_set():
    # FIREBASE_SERVICE_ACCOUNT_FILE lets the Admin SDK read+parse the
    # downloaded credential file itself - no manual JSON-on-one-line
    # formatting to get wrong (see .env.example).
    firebase_module._firebase_app = None
    fake_settings = replace(
        settings,
        firebase_service_account_file="/fake/service-account.json",
        firebase_service_account_json=None,
    )
    try:
        with (
            patch("app.auth.firebase.settings", fake_settings),
            patch("app.auth.firebase.credentials.Certificate") as mock_certificate,
            patch(
                "app.auth.firebase.firebase_admin.initialize_app",
                return_value=MagicMock(),
            ),
        ):
            firebase_module._get_firebase_app()
        mock_certificate.assert_called_once_with("/fake/service-account.json")
    finally:
        firebase_module._firebase_app = None


def test_get_firebase_app_gives_a_clear_error_for_invalid_inline_json():
    firebase_module._firebase_app = None
    fake_settings = replace(
        settings,
        firebase_service_account_file=None,
        firebase_service_account_json="not valid json",
    )
    try:
        with patch("app.auth.firebase.settings", fake_settings):
            with pytest.raises(RuntimeError, match="isn't valid JSON"):
                firebase_module._get_firebase_app()
    finally:
        firebase_module._firebase_app = None


def test_get_firebase_app_gives_a_clear_error_for_a_missing_file():
    firebase_module._firebase_app = None
    fake_settings = replace(
        settings,
        firebase_service_account_file="/no/such/file.json",
        firebase_service_account_json=None,
    )
    try:
        with patch("app.auth.firebase.settings", fake_settings):
            with pytest.raises(RuntimeError, match="Couldn't read the Firebase"):
                firebase_module._get_firebase_app()
    finally:
        firebase_module._firebase_app = None
