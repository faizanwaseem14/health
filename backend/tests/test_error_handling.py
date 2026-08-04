"""
Tests for global error handling (Task 15).

The individual error cases (rate limit -> 429, bad recovery code -> 401,
database down -> 503) are already covered where they're first
introduced (test_rate_limit.py, test_recovery.py, test_health.py) - and
still pass unchanged here, proving the global handler produces the same
result as the old per-route try/except did. This file covers the NEW
behavior that only the global handler provides: unknown routes, request
validation, and the catch-all safety net for a totally unexpected error.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_unknown_route_returns_structured_json_not_html():
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["status"] == "error"
    assert "detail" in body


def test_missing_required_field_returns_structured_422():
    response = client.post("/auth/otp/request", json={})

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"
    # The error should point at the actual missing field, not just say
    # "invalid" - useful for whoever is calling the API.
    assert any("phone_number" in problem for problem in body["detail"])


def test_wrong_field_type_returns_structured_422():
    response = client.post(
        "/auth/recovery/redeem", json={"phone_number": 12345, "recovery_code": True}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["status"] == "error"


def test_completely_unexpected_error_returns_generic_500_with_no_leaked_details():
    # Something that is NOT one of our known exception types (not a
    # SQLAlchemyError, not OtpRateLimitExceededError, ...) - simulates a
    # genuine bug somewhere, to prove the catch-all safety net works.
    #
    # raise_server_exceptions=False is needed here on purpose: by
    # default TestClient re-raises exceptions caught by a bare
    # `Exception` handler so a real bug surfaces loudly while writing
    # tests, instead of quietly turning into "just a 500". We want to
    # inspect the actual response our handler produces, so we turn that
    # off just for this one test - real clients hitting a real running
    # server always get the clean JSON response (verified in Task 14).
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    with patch(
        "app.routers.health.check_database_connection",
        side_effect=RuntimeError("super secret internal file path or query"),
    ):
        response = no_raise_client.get("/health")

    assert response.status_code == 500
    body = response.json()
    assert body["status"] == "error"
    assert body["detail"] == "An unexpected error occurred. Please try again."
    # The real exception message must never reach the client.
    assert "super secret" not in str(body)
