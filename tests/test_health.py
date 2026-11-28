"""Tests for GET /health."""

from fastapi.testclient import TestClient

from main import app


# Sends requests to the app directly, without starting a server.
client = TestClient(app)


def test_health_check():
    """/health returns 200 and {"status": "ok"}."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok"
    }
