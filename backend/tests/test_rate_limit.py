"""
Tests for OTP request rate limiting.

check_and_record_otp_request() needs a real database - it counts and
inserts real rows in otp_attempts - so we don't call it directly here.
(See the Task 10 summary for the scratch-Postgres run that verified it
for real.) What we test here, with no database needed, is: the rate
limit RULE itself matches the spec (5 per hour), and the
/auth/otp/request route returns the right status code for both the
allowed and blocked cases.
"""

from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.rate_limit import (
    MAX_OTP_REQUESTS_PER_WINDOW,
    OTP_RATE_LIMIT_WINDOW,
    OtpRateLimitExceededError,
)
from app.main import app as fastapi_app

client = TestClient(fastapi_app)


def test_rate_limit_matches_the_spec_of_5_per_hour():
    assert MAX_OTP_REQUESTS_PER_WINDOW == 5
    assert OTP_RATE_LIMIT_WINDOW == timedelta(hours=1)


def test_otp_request_allowed_returns_200():
    with patch("app.main.check_and_record_otp_request", return_value=None):
        response = client.post(
            "/auth/otp/request", json={"phone_number": "+15551234567"}
        )

    assert response.status_code == 200


def test_otp_request_blocked_returns_429():
    with patch(
        "app.main.check_and_record_otp_request",
        side_effect=OtpRateLimitExceededError("too many"),
    ):
        response = client.post(
            "/auth/otp/request", json={"phone_number": "+15551234567"}
        )

    assert response.status_code == 429


def test_otp_request_rejects_empty_phone_number():
    response = client.post("/auth/otp/request", json={"phone_number": ""})

    assert response.status_code == 422
