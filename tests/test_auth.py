"""End-to-end mocked tests for registration, login, logout, CSRF, XSS, SQLi, and headers."""

import re
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password, verify_password
from main import app
from tests.fake_mysql import FakeAuthDatabase


def _extract_csrf_token(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None, "CSRF token hidden input not found in HTML response."
    return match.group(1)


@pytest.fixture
def fake_db():
    db = FakeAuthDatabase()
    with patch("app.database.session.get_connection", side_effect=db.connect):
        yield db


@pytest.fixture
def client(fake_db):
    return TestClient(app)


def test_home_page_preserved_and_sets_security_headers(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Start your holiday with ADH Cruises" in response.text
    assert "/static/styles.css" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_successful_customer_registration(client, fake_db):
    page = client.get("/register")
    assert page.status_code == 200
    csrf_token = _extract_csrf_token(page.text)

    response = client.post(
        "/register",
        data={
            "first_name": "Jane",
            "last_name": "Sailor",
            "email": "Jane.Sailor@Example.com",
            "phone": "+1 212-555-0142",
            "address": "123 Pier Street, New York, NY",
            "password": "CruisePassword!2026",
            "confirm_password": "CruisePassword!2026",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?registered=1"
    assert len(fake_db.customers) == 1
    assert len(fake_db.users) == 1
    assert fake_db.commits == 1

    created_user = fake_db.users[1]
    assert created_user["EMAIL"] == "jane.sailor@example.com"
    assert created_user["ROLE"] == "C"
    assert created_user["CUSTOMER_ID"] == 1
    assert created_user["PASSWORD_HASH"] != "CruisePassword!2026"
    assert verify_password("CruisePassword!2026", created_user["PASSWORD_HASH"])


def test_registration_rejects_duplicate_email(client, fake_db):
    fake_db.seed_customer(
        first_name="Existing",
        last_name="User",
        email="existing@example.com",
        phone="212-555-0100",
        address="1 Pier Plaza",
        password_hash=hash_password("ExistingPass!1"),
    )

    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.text)

    response = client.post(
        "/register",
        data={
            "first_name": "Another",
            "last_name": "Person",
            "email": "EXISTING@example.com",
            "phone": "212-555-0199",
            "address": "2 Pier Plaza",
            "password": "StrongPassword!1",
            "confirm_password": "StrongPassword!1",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.text.lower()
    assert len(fake_db.customers) == 1
    assert len(fake_db.users) == 1
    assert fake_db.rollbacks == 1


def test_registration_rejects_invalid_input(client, fake_db):
    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.text)

    response = client.post(
        "/register",
        data={
            "first_name": "",
            "last_name": "Tester",
            "email": "bad-email",
            "phone": "12",
            "address": "NY",
            "password": "short",
            "confirm_password": "mismatch",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == 400
    assert "First name is required." in response.text
    assert "Please enter a valid email address." in response.text
    assert "Passwords do not match." in response.text
    assert len(fake_db.customers) == 0
    assert len(fake_db.users) == 0


def test_successful_login_and_logout_flow(client, fake_db):
    fake_db.seed_customer(
        first_name="Sam",
        last_name="Voyager",
        email="sam@example.com",
        phone="212-555-0123",
        address="500 Harbor Blvd",
        password_hash=hash_password("VoyagePass!2026"),
    )

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert login_page.headers["cache-control"] == "no-store"
    csrf_token = _extract_csrf_token(login_page.text)

    login_resp = client.post(
        "/login",
        data={
            "email": "SAM@example.com",
            "password": "VoyagePass!2026",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )

    assert login_resp.status_code == 303
    assert login_resp.headers["location"] == "/account"

    set_cookie_header = login_resp.headers.get("set-cookie", "").lower()
    assert "adh_session=" in set_cookie_header
    assert "httponly" in set_cookie_header
    assert "samesite=lax" in set_cookie_header

    me_resp = client.get("/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json() == {
        "user_id": 1,
        "email": "sam@example.com",
        "role": "C",
        "customer_id": 1,
        "first_name": "Sam",
        "last_name": "Voyager",
    }

    account_page = client.get("/account")
    assert account_page.status_code == 200
    logout_csrf = _extract_csrf_token(account_page.text)

    logout_resp = client.post(
        "/logout",
        data={"csrf_token": logout_csrf},
        follow_redirects=False,
    )
    assert logout_resp.status_code == 303
    assert logout_resp.headers["location"] == "/login?logged_out=1"

    assert client.get("/auth/me").status_code == 401


def test_login_rejects_invalid_credentials(client, fake_db):
    fake_db.seed_customer(
        first_name="Sam",
        last_name="Voyager",
        email="sam@example.com",
        phone="212-555-0123",
        address="500 Harbor Blvd",
        password_hash=hash_password("CorrectPass!2026"),
    )

    csrf_token = _extract_csrf_token(client.get("/login").text)

    wrong_pw = client.post(
        "/login",
        data={
            "email": "sam@example.com",
            "password": "WrongPassword!2026",
            "csrf_token": csrf_token,
        },
    )
    assert wrong_pw.status_code == 401
    assert "Invalid email or password." in wrong_pw.text
    assert client.get("/auth/me").status_code == 401

    unknown_email = client.post(
        "/login",
        data={
            "email": "nobody@example.com",
            "password": "AnyPassword!2026",
            "csrf_token": csrf_token,
        },
    )
    assert unknown_email.status_code == 401
    assert "Invalid email or password." in unknown_email.text


def test_sql_injection_attempt_cannot_bypass_login(client, fake_db):
    fake_db.seed_employee(
        email="admin@adhcruises.com",
        password_hash=hash_password("AdminSecret!2026"),
    )

    csrf_token = _extract_csrf_token(client.get("/login").text)
    sqli_payload = "' OR '1'='1' -- "

    resp = client.post(
        "/login",
        data={
            "email": sqli_payload,
            "password": "' OR '1'='1",
            "csrf_token": csrf_token,
        },
    )

    assert resp.status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert len(fake_db.executed_queries) >= 1
    for sql, params, prepared in fake_db.executed_queries:
        assert prepared is True
        assert sqli_payload not in sql
        assert params is not None


def test_xss_payload_is_html_escaped_in_rendered_pages(client, fake_db):
    xss_name = "<script>alert('xss')</script>"
    xss_address = '<img src=x onerror="alert(1)"> 123 Pier'

    page = client.get("/register")
    csrf_token = _extract_csrf_token(page.text)

    reg_resp = client.post(
        "/register",
        data={
            "first_name": xss_name,
            "last_name": "<b>Bold</b>",
            "email": "xss@example.com",
            "phone": "212-555-0188",
            "address": xss_address,
            "password": "SafePassword!2026",
            "confirm_password": "SafePassword!2026",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert reg_resp.status_code == 303

    login_csrf = _extract_csrf_token(client.get("/login").text)
    login_resp = client.post(
        "/login",
        data={
            "email": "xss@example.com",
            "password": "SafePassword!2026",
            "csrf_token": login_csrf,
        },
        follow_redirects=False,
    )
    assert login_resp.status_code == 303

    account_html = client.get("/account").text
    assert xss_name not in account_html
    assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in account_html
    assert xss_address not in account_html
    assert "&lt;img src=x onerror=&#34;alert(1)&#34;&gt;" in account_html

    home_html = client.get("/").text
    assert xss_name not in home_html
    assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;" in home_html


def test_csrf_protection_blocks_missing_or_forged_tokens(client, fake_db):
    fake_db.seed_customer(
        first_name="Csrf",
        last_name="Tester",
        email="csrf@example.com",
        phone="212-555-0155",
        address="10 Safe Harbor",
        password_hash=hash_password("SafePass!2026"),
    )

    # Missing CSRF token on register
    reg_no_csrf = client.post(
        "/register",
        data={
            "first_name": "A",
            "last_name": "B",
            "email": "new@example.com",
            "phone": "212-555-0100",
            "address": "123 Pier St",
            "password": "StrongPassword!1",
            "confirm_password": "StrongPassword!1",
        },
    )
    assert reg_no_csrf.status_code == 403

    # Forged CSRF token on login
    client.get("/login")
    login_bad_csrf = client.post(
        "/login",
        data={
            "email": "csrf@example.com",
            "password": "SafePass!2026",
            "csrf_token": "forged-token-value",
        },
    )
    assert login_bad_csrf.status_code == 403

    # Valid login, then forged CSRF token on logout
    valid_csrf = _extract_csrf_token(client.get("/login").text)
    login_ok = client.post(
        "/login",
        data={
            "email": "csrf@example.com",
            "password": "SafePass!2026",
            "csrf_token": valid_csrf,
        },
        follow_redirects=False,
    )
    assert login_ok.status_code == 303

    logout_bad_csrf = client.post("/logout", data={"csrf_token": "wrong-token"})
    assert logout_bad_csrf.status_code == 403
    # Session must still be active because logout was blocked.
    assert client.get("/auth/me").status_code == 200
