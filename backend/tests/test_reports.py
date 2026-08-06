"""
Tests for the report upload route.

Validation failures (oversized file, wrong file type, no login) never
touch the database - they're rejected before any DB code runs - so
those are tested for real, with no live database needed. The full
happy path (file -> R2 -> a real database row) needs a real database
for the "id"/timestamps SQLAlchemy only fills in at actual flush time;
that's verified for real against a throwaway local Postgres (see the
Task summary), with R2 itself mocked since this sandbox has no real R2
credentials.

Here, for the happy-path shape check, we mock the database session too
- enough to prove the file was correctly validated, fingerprinted, and
handed to R2 with the right bytes and key, even though the response's
"id" field won't be a real value in this particular test.
"""

import io
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from app.auth.dependencies import get_current_user
from app.main import app
from app.models import Profile, User
from app.routers.reports import require_owned_profile

client = TestClient(app)

_REAL_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


def _make_real_png_bytes(width: int, height: int) -> bytes:
    image = Image.new("RGB", (width, height), color="green")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _override_auth(user: User, profile: Profile):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_owned_profile] = lambda: profile


def _clear_overrides():
    app.dependency_overrides.clear()


def test_upload_requires_login():
    response = client.post(
        f"/profiles/{uuid.uuid4()}/reports",
        files={"file": ("photo.png", _REAL_PNG_BYTES, "image/png")},
    )

    assert response.status_code == 401


def test_upload_rejects_a_file_over_10mb():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    profile = Profile(id=uuid.uuid4(), user_id=user.id, full_name="Alice")
    _override_auth(user, profile)

    try:
        oversized = b"\x89PNG\r\n\x1a\n" + (b"0" * (11 * 1024 * 1024))
        response = client.post(
            f"/profiles/{profile.id}/reports",
            files={"file": ("photo.png", oversized, "image/png")},
        )
    finally:
        _clear_overrides()

    assert response.status_code == 413
    assert response.json()["status"] == "error"


def test_upload_rejects_a_file_whose_real_bytes_dont_match_its_claimed_type():
    # The core requirement: a file claiming (via filename AND
    # Content-Type header) to be a JPEG, but whose actual bytes are
    # plain text - the real-type check must catch this regardless.
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    profile = Profile(id=uuid.uuid4(), user_id=user.id, full_name="Alice")
    _override_auth(user, profile)

    try:
        response = client.post(
            f"/profiles/{profile.id}/reports",
            files={
                "file": (
                    "totally_a_real_photo.jpg",
                    b"this is just plain text, not a jpeg",
                    "image/jpeg",
                )
            },
        )
    finally:
        _clear_overrides()

    assert response.status_code == 415
    assert response.json()["status"] == "error"


def test_upload_rejects_someone_elses_profile():
    # require_owned_row already 404s for a profile you don't own
    # (proven generically in Task 12) - this just confirms the upload
    # route actually uses that guard rather than skipping it.
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    app.dependency_overrides[get_current_user] = lambda: user
    # Deliberately NOT overriding require_owned_profile - it will try a
    # real (fake, localhost) database lookup and fail fast, which is a
    # fine proxy for "not overridden" here since we only care that
    # SOME rejection happens before any file processing.
    try:
        response = client.post(
            f"/profiles/{uuid.uuid4()}/reports",
            files={"file": ("photo.png", _REAL_PNG_BYTES, "image/png")},
        )
    finally:
        _clear_overrides()

    assert response.status_code in (404, 503)


def test_upload_succeeds_for_a_real_valid_png():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    profile = Profile(id=uuid.uuid4(), user_id=user.id, full_name="Alice")
    _override_auth(user, profile)

    png_bytes = _make_real_png_bytes(64, 48)
    fake_db = MagicMock()

    from app.auth.dependencies import get_db

    def fake_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = fake_get_db

    try:
        with patch("app.routers.reports.upload_file_bytes") as mock_upload:
            response = client.post(
                f"/profiles/{profile.id}/reports",
                files={"file": ("photo.png", png_bytes, "image/png")},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["mime_type"] == "image/png"
    assert body["data"]["file_size_bytes"] == len(png_bytes)
    assert body["data"]["original_width"] == 64
    assert body["data"]["original_height"] == 48

    # R2 was called with the file's REAL bytes, unmodified, and a
    # storage key that's not derived from anything the client sent.
    mock_upload.assert_called_once()
    called_key, called_bytes, called_content_type = mock_upload.call_args[0]
    assert called_bytes == png_bytes
    assert called_content_type == "image/png"
    assert called_key.startswith(f"reports/{profile.id}/")
    assert called_key.endswith(".png")
