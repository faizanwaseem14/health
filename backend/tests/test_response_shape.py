"""
Tests for the standard response envelope (Task 16).

The error side already got its standard shape in Task 15 and is proven
elsewhere (test_error_handling.py, test_rate_limit.py, test_recovery.py).
This covers the SUCCESS side: the helper function itself, and - the
part that actually matters - that every existing route's SUCCESS
response really uses it, not just that the helper works in isolation.
"""

import json
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.core.responses import success_response
from app.main import app
from app.models import User

client = TestClient(app)


def test_success_response_wraps_data():
    response = success_response({"foo": "bar"})

    assert response.status_code == 200
    assert json.loads(response.body) == {"status": "success", "data": {"foo": "bar"}}


def test_success_response_defaults_data_to_none():
    response = success_response()

    assert json.loads(response.body) == {"status": "success", "data": None}


def test_success_response_supports_a_custom_status_code():
    response = success_response({"created": True}, status_code=201)

    assert response.status_code == 201


def test_root_route_uses_the_standard_envelope():
    response = client.get("/")

    assert response.json() == {
        "status": "success",
        "data": {"service": "MedVault API", "status": "running"},
    }


def test_health_route_uses_the_standard_envelope():
    with patch("app.routers.health.check_database_connection", return_value=None):
        response = client.get("/health")

    assert response.json() == {"status": "success", "data": {"database": "connected"}}


def test_otp_request_route_uses_the_standard_envelope():
    with patch("app.routers.auth.check_and_record_otp_request", return_value=None):
        response = client.post(
            "/auth/otp/request", json={"phone_number": "+15551234567"}
        )

    assert response.json() == {"status": "success", "data": None}


def test_recovery_redeem_route_uses_the_standard_envelope():
    fake_user = User(id=uuid.uuid4(), phone_number="+15551234567")

    with patch("app.routers.auth.redeem_recovery_code", return_value=fake_user):
        response = client.post(
            "/auth/recovery/redeem",
            json={"phone_number": "+15551234567", "recovery_code": "x"},
        )

    assert response.json() == {
        "status": "success",
        "data": {"id": str(fake_user.id), "phone_number": "+15551234567"},
    }


def test_me_route_uses_the_standard_envelope():
    fake_user = User(id=uuid.uuid4(), phone_number="+15551234567")
    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        with patch("app.routers.auth.record_audit_event", return_value=None):
            response = client.get("/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.json() == {
        "status": "success",
        "data": {"id": str(fake_user.id), "phone_number": "+15551234567"},
    }


def test_recovery_generate_route_uses_the_standard_envelope():
    fake_user = User(id=uuid.uuid4(), phone_number="+15551234567")
    app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        with patch(
            "app.routers.auth.generate_recovery_code",
            return_value="AAAA-BBBB-CCCC-DDDD",
        ):
            response = client.post("/auth/recovery/generate")
    finally:
        app.dependency_overrides.clear()

    assert response.json() == {
        "status": "success",
        "data": {"recovery_code": "AAAA-BBBB-CCCC-DDDD"},
    }


def test_error_responses_still_use_the_error_shape_not_the_success_shape():
    # A quick sanity check that the two envelopes stay distinguishable:
    # a "status": "error" response never has a "data" key, and always
    # has "detail" instead.
    response = client.get("/auth/me")

    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"
    assert "detail" in body
    assert "data" not in body
