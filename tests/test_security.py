"""Unit tests for password hashing, input validation, and session configuration."""

import pytest

from app.core.config import get_session_settings
from app.core.security import (
    hash_password,
    validate_registration_input,
    verify_password,
    verify_password_constant_time,
)


def test_bcrypt_hash_and_verify_roundtrip():
    plaintext = "CruisePass!2026"
    hashed_one = hash_password(plaintext)
    hashed_two = hash_password(plaintext)

    assert hashed_one != plaintext
    assert hashed_one.startswith("$2b$")
    # Distinct salts must produce distinct hashes for the same password.
    assert hashed_one != hashed_two
    assert verify_password(plaintext, hashed_one) is True
    assert verify_password(plaintext, hashed_two) is True
    assert verify_password("WrongPassword!2026", hashed_one) is False


def test_bcrypt_rejects_empty_and_overlong_passwords():
    with pytest.raises(ValueError, match="empty"):
        hash_password("")

    overlong = "a" * 73
    with pytest.raises(ValueError, match="72"):
        hash_password(overlong)

    valid_hash = hash_password("ValidPass123!")
    assert verify_password(overlong, valid_hash) is False
    assert verify_password("ValidPass123!", "not-a-valid-bcrypt-hash") is False


def test_constant_time_verify_returns_false_for_missing_user():
    assert verify_password_constant_time("AnyPassword123!", None) is False


def test_validate_registration_input_accepts_valid_payload():
    data, errors = validate_registration_input(
        first_name="  Ada ",
        last_name=" Lovelace ",
        email=" Ada.Lovelace@Example.COM ",
        phone=" +1 (212) 555-0199 ",
        address=" 370 Jay St, Brooklyn, NY 11201 ",
        password="StrongPassword!1",
        confirm_password="StrongPassword!1",
    )

    assert errors == []
    assert data is not None
    assert data.first_name == "Ada"
    assert data.last_name == "Lovelace"
    assert data.email == "ada.lovelace@example.com"
    assert data.phone == "+1 (212) 555-0199"
    assert data.address == "370 Jay St, Brooklyn, NY 11201"


def test_validate_registration_input_rejects_invalid_fields():
    data, errors = validate_registration_input(
        first_name="   ",
        last_name="",
        email="not-an-email",
        phone="123",
        address="NY",
        password="short",
        confirm_password="different",
    )

    assert data is None
    assert any("First name" in err for err in errors)
    assert any("Last name" in err for err in errors)
    assert any("email" in err.lower() for err in errors)
    assert any("phone" in err.lower() for err in errors)
    assert any("Address" in err for err in errors)
    assert any("at least 8" in err for err in errors)
    assert any("do not match" in err for err in errors)


def test_session_settings_requires_secret_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SESSION_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError, match="SESSION_SECRET_KEY"):
        get_session_settings()


def test_session_settings_reads_env_values(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_SECRET_KEY", "a-very-strong-production-secret-key")
    monkeypatch.setenv("SESSION_HTTPS_ONLY", "true")
    monkeypatch.setenv("SESSION_MAX_AGE", "7200")

    settings = get_session_settings()
    assert settings.secret_key == "a-very-strong-production-secret-key"
    assert settings.https_only is True
    assert settings.max_age == 7200
    assert settings.same_site == "lax"
