"""Role-based authorization tests for anonymous, customer (C), and employee (E) access."""

import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from main import app
from tests.fake_mysql import FakeAuthDatabase


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


@pytest.fixture
def fake_db():
    db = FakeAuthDatabase()
    db.seed_customer(
        first_name="Maya",
        last_name="Cruiser",
        email="customer@example.com",
        phone="212-555-0111",
        address="100 Pier Way, NY",
        password_hash=hash_password("CustomerPass!1"),
    )
    db.seed_employee(
        email="staff@adhcruises.com",
        password_hash=hash_password("EmployeePass!1"),
    )
    with patch("app.database.session.get_connection", side_effect=db.connect):
        yield db


def _login(client: TestClient, email: str, password: str):
    csrf_token = _extract_csrf_token(client.get("/login").text)
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf_token},
        follow_redirects=False,
    )


def test_unauthenticated_users_are_rejected_from_protected_routes(fake_db):
    client = TestClient(app)

    assert client.get("/account").status_code == 401
    assert client.get("/employee").status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert client.get("/api/employee/status").status_code == 401


def test_customer_can_access_customer_routes_but_not_employee_routes(fake_db):
    client = TestClient(app)
    login_resp = _login(client, "customer@example.com", "CustomerPass!1")
    assert login_resp.status_code == 303
    assert login_resp.headers["location"] == "/account"

    account_resp = client.get("/account")
    assert account_resp.status_code == 200
    assert "Maya Cruiser" in account_resp.text

    me_resp = client.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "C"

    assert client.get("/employee").status_code == 403
    assert client.get("/api/employee/status").status_code == 403


def test_employee_can_access_employee_routes_but_not_customer_only_account(fake_db):
    client = TestClient(app)
    login_resp = _login(client, "staff@adhcruises.com", "EmployeePass!1")
    assert login_resp.status_code == 303
    assert login_resp.headers["location"] == "/employee"

    employee_page = client.get("/employee")
    assert employee_page.status_code == 200
    assert "staff@adhcruises.com" in employee_page.text

    employee_api = client.get("/api/employee/status")
    assert employee_api.status_code == 200
    assert employee_api.json() == {
        "status": "authorized",
        "user_id": 2,
        "email": "staff@adhcruises.com",
        "role": "E",
    }

    me_resp = client.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "E"
    assert me_resp.json()["customer_id"] is None

    assert client.get("/account").status_code == 403


def test_deleted_user_session_is_invalidated(fake_db):
    client = TestClient(app)
    assert _login(client, "customer@example.com", "CustomerPass!1").status_code == 303
    assert client.get("/auth/me").status_code == 200

    # Simulate user deletion in DB while cookie still exists.
    fake_db.users.clear()

    assert client.get("/auth/me").status_code == 401
    assert client.get("/account").status_code == 401
