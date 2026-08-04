"""
Tests for the public /health route.

check_database_connection() needs a real database, so we mock it here
to test both outcomes deterministically (connected vs unreachable)
without depending on whether a real Postgres happens to be reachable
from wherever tests are running.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app

client = TestClient(app)


def test_health_reports_ok_when_database_is_reachable():
    with patch("app.routers.health.check_database_connection", return_value=None):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_health_reports_503_when_database_is_unreachable():
    with patch(
        "app.routers.health.check_database_connection",
        side_effect=OperationalError("connect failed", None, Exception("refused")),
    ):
        response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    # Never leak connection details (host, credentials, query text) in the response.
    assert "refused" not in str(body)
    assert "postgresql://" not in str(body)
