"""Live integration and security verification against the local MySQL database."""

import re
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password, verify_password  # noqa: E402
from app.database.session import db_cursor, db_transaction, decode_db_value  # noqa: E402
from app.repositories.user_repository import (  # noqa: E402
    create_employee,
    get_user_by_email,
)
from main import app  # noqa: E402


def _extract_csrf(html: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert match is not None, "Missing CSRF token in HTML form."
    return match.group(1)


def _cleanup_test_emails(emails: list[str]) -> None:
    """Remove only the explicitly created live-test records (never touches other rows)."""
    with db_transaction() as cursor:
        for email in emails:
            cursor.execute(
                "SELECT USER_ID, CUSTOMER_ID FROM ADH_USER WHERE EMAIL = %s",
                (email,),
            )
            row = cursor.fetchone()
            if row:
                user_id = int(row[0])
                customer_id = int(row[1]) if row[1] is not None else None
                cursor.execute("DELETE FROM ADH_USER WHERE USER_ID = %s", (user_id,))
                if customer_id is not None:
                    cursor.execute(
                        "DELETE FROM ADH_CUSTOMER WHERE CUSTOMER_ID = %s",
                        (customer_id,),
                    )


def main() -> int:
    run_id = uuid.uuid4().hex[:10]
    customer_email = f"__live_test_cust_{run_id}@adh-local-test.invalid"
    employee_email = f"__live_test_emp_{run_id}@adh-local-test.invalid"
    xss_email = f"__live_test_xss_{run_id}@adh-local-test.invalid"
    test_emails = [customer_email, employee_email, xss_email]

    client = TestClient(app)

    try:
        # 1. Health endpoints
        assert client.get("/health").status_code == 200
        mysql_health = client.get("/health/mysql")
        assert mysql_health.status_code == 200, f"/health/mysql failed: {mysql_health.text}"
        assert mysql_health.json()["database"] == "da2410hc4288as23663"
        assert client.get("/docs").status_code == 200
        print("   [PASS] /health, /health/mysql, /docs verified against live MySQL")

        # 2. Live customer registration via HTTP
        reg_csrf = _extract_csrf(client.get("/register").text)
        reg_resp = client.post(
            "/register",
            data={
                "first_name": "Live",
                "last_name": "Customer",
                "email": customer_email,
                "phone": "+1 212-555-0190",
                "address": "370 Jay St, Brooklyn, NY",
                "password": "LiveTestPass!2026",
                "confirm_password": "LiveTestPass!2026",
                "csrf_token": reg_csrf,
            },
            follow_redirects=False,
        )
        assert reg_resp.status_code == 303
        assert reg_resp.headers["location"] == "/login?registered=1"

        # Verify DB records & bcrypt hash
        record = get_user_by_email(customer_email)
        assert record is not None
        assert record.user.role == "C"
        assert record.user.customer_id is not None
        assert record.password_hash.startswith("$2b$")
        assert record.password_hash != "LiveTestPass!2026"
        assert verify_password("LiveTestPass!2026", record.password_hash)

        # Duplicate email rejected (409) & no orphan customer row created
        with db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM ADH_CUSTOMER")
            count_before = int(cursor.fetchone()[0])

        dup_resp = client.post(
            "/register",
            data={
                "first_name": "Dup",
                "last_name": "Customer",
                "email": customer_email,
                "phone": "+1 212-555-0191",
                "address": "371 Jay St, Brooklyn, NY",
                "password": "LiveTestPass!2026",
                "confirm_password": "LiveTestPass!2026",
                "csrf_token": _extract_csrf(client.get("/register").text),
            },
        )
        assert dup_resp.status_code == 409

        with db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM ADH_CUSTOMER")
            count_after = int(cursor.fetchone()[0])
        assert count_after == count_before, "Orphan ADH_CUSTOMER row created on duplicate email!"
        print("   [PASS] Live registration, bcrypt storage, FK link, and duplicate-email rollback verified")

        # 3. Live login, cookie flags, customer authorization, and logout
        bad_login = client.post(
            "/login",
            data={
                "email": customer_email,
                "password": "WrongPassword!2026",
                "csrf_token": _extract_csrf(client.get("/login").text),
            },
        )
        assert bad_login.status_code == 401

        sqli_login = client.post(
            "/login",
            data={
                "email": "' OR '1'='1' -- ",
                "password": "' OR '1'='1",
                "csrf_token": _extract_csrf(client.get("/login").text),
            },
        )
        assert sqli_login.status_code == 401

        ok_login = client.post(
            "/login",
            data={
                "email": customer_email,
                "password": "LiveTestPass!2026",
                "csrf_token": _extract_csrf(client.get("/login").text),
            },
            follow_redirects=False,
        )
        assert ok_login.status_code == 303
        assert ok_login.headers["location"] == "/account"
        cookie_hdr = ok_login.headers.get("set-cookie", "").lower()
        assert "adh_session=" in cookie_hdr
        assert "httponly" in cookie_hdr
        assert "samesite=lax" in cookie_hdr

        assert client.get("/account").status_code == 200
        assert client.get("/auth/me").json()["role"] == "C"
        assert client.get("/employee").status_code == 403
        assert client.get("/api/employee/status").status_code == 403

        # CSRF check on logout
        assert client.post("/logout", data={"csrf_token": "bad"}).status_code == 403
        logout_csrf = _extract_csrf(client.get("/account").text)
        logout_resp = client.post(
            "/logout",
            data={"csrf_token": logout_csrf},
            follow_redirects=False,
        )
        assert logout_resp.status_code == 303
        assert client.get("/auth/me").status_code == 401
        assert client.get("/account").status_code == 401
        print("   [PASS] Live login/logout, session cookies, CSRF, SQLi, and Customer RBAC verified")

        # 4. Employee authorization (ROLE = 'E', CUSTOMER_ID = NULL)
        emp = create_employee(
            email=employee_email,
            password_hash=hash_password("EmpLivePass!2026"),
        )
        assert emp.role == "E" and emp.customer_id is None

        emp_client = TestClient(app)
        emp_login = emp_client.post(
            "/login",
            data={
                "email": employee_email,
                "password": "EmpLivePass!2026",
                "csrf_token": _extract_csrf(emp_client.get("/login").text),
            },
            follow_redirects=False,
        )
        assert emp_login.status_code == 303
        assert emp_login.headers["location"] == "/employee"
        assert emp_client.get("/employee").status_code == 200
        assert emp_client.get("/api/employee/status").status_code == 200
        assert emp_client.get("/account").status_code == 403
        print("   [PASS] Live Employee RBAC verified (allowed /employee, blocked /account)")

        # 5. Live XSS escaping verification
        xss_client = TestClient(app)
        xss_payload = "<script>alert('live-xss')</script>"
        xss_reg = xss_client.post(
            "/register",
            data={
                "first_name": xss_payload,
                "last_name": "Tester",
                "email": xss_email,
                "phone": "212-555-0192",
                "address": "100 Harbor Way",
                "password": "XssLivePass!2026",
                "confirm_password": "XssLivePass!2026",
                "csrf_token": _extract_csrf(xss_client.get("/register").text),
            },
            follow_redirects=False,
        )
        assert xss_reg.status_code == 303
        xss_client.post(
            "/login",
            data={
                "email": xss_email,
                "password": "XssLivePass!2026",
                "csrf_token": _extract_csrf(xss_client.get("/login").text),
            },
            follow_redirects=False,
        )
        acct_html = xss_client.get("/account").text
        assert xss_payload not in acct_html
        assert "&lt;script&gt;alert(&#39;live-xss&#39;)&lt;/script&gt;" in acct_html
        print("   [PASS] Live XSS HTML escaping verified")

        # 6. Transaction rollback test directly against live MySQL
        with db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM ADH_CUSTOMER")
            before_rb = int(cursor.fetchone()[0])
        try:
            with db_transaction() as cursor:
                cursor.execute(
                    "INSERT INTO ADH_CUSTOMER (FIRST_NAME, LAST_NAME, PHONE, ADDRESS) VALUES (%s, %s, %s, %s)",
                    ("Rollback", "Probe", "212-555-0199", "Rollback St"),
                )
                raise RuntimeError("Forced rollback test")
        except RuntimeError:
            pass
        with db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM ADH_CUSTOMER")
            after_rb = int(cursor.fetchone()[0])
        assert after_rb == before_rb, "Live transaction rollback failed!"
        print("   [PASS] Live MySQL transaction rollback verified")

        # Verify raw DB value decoding
        with db_cursor() as cursor:
            cursor.execute("SELECT EMAIL FROM ADH_USER WHERE EMAIL = %s", (customer_email,))
            assert str(decode_db_value(cursor.fetchone()[0])) == customer_email
    finally:
        _cleanup_test_emails(test_emails)
        print("   [CLEANUP] Removed temporary live-test records safely.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
