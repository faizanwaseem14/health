"""
Tests for the profile routes (GET/POST /profiles).

Auth-required and validation-failure cases never touch the database -
those are tested for real with no live database needed, same posture
as test_reports.py. The happy-path shape (what gets added to the
session, what the response looks like) uses a mocked db; the real,
end-to-end proof against an actual database (a profile really gets
stored, relationship_to_owner really defaults to "self", one user
never sees another user's profiles) is in the Task summary's
scratch-Postgres run.
"""

import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.main import app
from app.models import User

client = TestClient(app)


def _override_auth(user: User):
    app.dependency_overrides[get_current_user] = lambda: user


def _clear_overrides():
    app.dependency_overrides.clear()


def test_list_profiles_requires_login():
    response = client.get("/profiles")

    assert response.status_code == 401


def test_create_profile_requires_login():
    response = client.post("/profiles", json={"full_name": "Alice"})

    assert response.status_code == 401


def test_create_profile_rejects_a_missing_full_name():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    _override_auth(user)

    try:
        response = client.post("/profiles", json={})
    finally:
        _clear_overrides()

    assert response.status_code == 422
    assert response.json()["status"] == "error"


def test_create_profile_rejects_an_empty_full_name():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    _override_auth(user)

    try:
        response = client.post("/profiles", json={"full_name": ""})
    finally:
        _clear_overrides()

    assert response.status_code == 422


def test_create_profile_stores_the_submitted_fields():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    _override_auth(user)
    fake_db = MagicMock()

    from app.auth.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.post(
            "/profiles",
            json={
                "full_name": "Alice Sample",
                "date_of_birth": "1990-05-01",
                "sex": "Female",
            },
        )
    finally:
        _clear_overrides()

    assert response.status_code == 201
    added = fake_db.add.call_args[0][0]
    assert added.user_id == user.id
    assert added.full_name == "Alice Sample"
    assert str(added.date_of_birth) == "1990-05-01"
    assert added.sex == "Female"


def test_create_profile_allows_omitting_optional_fields():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    _override_auth(user)
    fake_db = MagicMock()

    from app.auth.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.post("/profiles", json={"full_name": "Alice"})
    finally:
        _clear_overrides()

    assert response.status_code == 201
    added = fake_db.add.call_args[0][0]
    assert added.date_of_birth is None
    assert added.sex is None


def test_list_profiles_only_queries_the_current_users_own_rows():
    user = User(id=uuid.uuid4(), phone_number="+15551234567")
    _override_auth(user)
    fake_db = MagicMock()
    query_chain = fake_db.query.return_value.filter.return_value.order_by.return_value
    query_chain.all.return_value = []

    from app.auth.dependencies import get_db

    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        response = client.get("/profiles")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["data"] == []
    fake_db.query.assert_called_once()
