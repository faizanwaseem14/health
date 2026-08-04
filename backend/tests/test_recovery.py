"""
Tests for backup recovery codes.

generate_recovery_code() and redeem_recovery_code() need a real database
(they read/write real User and OtpAttempt rows), so we don't call them
directly here. (See the Task 11 summary for the scratch-Postgres run
that verified the full generate -> redeem -> one-time-use flow for
real.) What we test here, with no database needed, is: the code format
itself, that hashing is deterministic and one-way, and that the routes
require the right things (auth on generate, valid input on redeem).
"""

import re
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.recovery import RecoveryCodeInvalidError, _generate_code, _hash_code
from app.main import app as fastapi_app
from app.models import User

client = TestClient(fastapi_app)

_CODE_PATTERN = re.compile(
    r"^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}(-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}){3}$"
)


def test_generated_code_matches_the_expected_format():
    code = _generate_code()

    assert _CODE_PATTERN.match(code), f"unexpected code shape: {code}"
    # No ambiguous characters anywhere in the code.
    for confusing_char in "01OIL":
        assert confusing_char not in code


def test_generated_codes_are_not_repeated():
    codes = {_generate_code() for _ in range(50)}
    assert len(codes) == 50  # extremely unlikely to collide by chance


def test_hash_code_is_deterministic_and_one_way():
    code = "AAAA-BBBB-CCCC-DDDD"

    hash1 = _hash_code(code)
    hash2 = _hash_code(code)

    assert hash1 == hash2  # same input -> same hash, so we can compare later
    assert hash1 != code  # never store the code itself
    assert (
        _hash_code("WXYZ-WXYZ-WXYZ-WXYZ") != hash1
    )  # different code -> different hash


def test_generate_recovery_code_route_requires_login():
    response = client.post("/auth/recovery/generate")

    assert response.status_code == 401


def test_redeem_recovery_code_route_rejects_invalid_code():
    with patch(
        "app.routers.auth.redeem_recovery_code",
        side_effect=RecoveryCodeInvalidError("Invalid phone number or recovery code."),
    ):
        response = client.post(
            "/auth/recovery/redeem",
            json={"phone_number": "+15551234567", "recovery_code": "WRONG-CODE"},
        )

    assert response.status_code == 401


def test_redeem_recovery_code_route_accepts_a_valid_code():
    fake_user = User(id=uuid.uuid4(), phone_number="+15551234567")

    with patch("app.routers.auth.redeem_recovery_code", return_value=fake_user):
        response = client.post(
            "/auth/recovery/redeem",
            json={
                "phone_number": "+15551234567",
                "recovery_code": "AAAA-BBBB-CCCC-DDDD",
            },
        )

    assert response.status_code == 200
    assert response.json()["phone_number"] == "+15551234567"


def test_redeem_recovery_code_route_rejects_missing_fields():
    response = client.post("/auth/recovery/redeem", json={"phone_number": ""})

    assert response.status_code == 422
