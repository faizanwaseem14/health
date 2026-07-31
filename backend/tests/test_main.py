"""
A first, simple test that proves pytest + FastAPI's TestClient are wired
up correctly end to end.

It doesn't test any real health-records feature yet - there isn't one to
test today. It just proves: the app can be imported, the server can
handle a request, and pytest can run and report the result. Later tasks
will add real tests alongside real features.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_returns_running_status():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"service": "MedVault API", "status": "running"}
