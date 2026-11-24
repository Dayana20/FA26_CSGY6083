"""Password hashing, input validation, and CSRF protection utilities."""

import hmac
import re
import secrets
from dataclasses import dataclass

import bcrypt
from fastapi import Request

BCRYPT_ROUNDS = 12
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8
CSRF_SESSION_KEY = "csrf_token"

EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)
PHONE_ALLOWED_REGEX = re.compile(r"^[0-9+\-().\s]{7,30}$")

# Precomputed bcrypt hash used when an email is not found to reduce timing leakage.
DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"dummy-timing-mitigation-password",
    bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
).decode("utf-8")


@dataclass(frozen=True)
class RegistrationData:
    first_name: str
    last_name: str
    email: str
    phone: str
    address: str
    password: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with a fresh per-password salt."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) == 0:
        raise ValueError("Password cannot be empty.")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must not exceed {MAX_PASSWORD_BYTES} UTF-8 bytes."
        )
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode(
        "utf-8"
    )


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    if not password or not password_hash:
        return False
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except ValueError:
        return False


def verify_password_constant_time(password: str, password_hash: str | None) -> bool:
    """Verify password while performing a dummy hash check if no user record exists."""
    if password_hash is None:
        verify_password(password, DUMMY_PASSWORD_HASH)
        return False
    return verify_password(password, password_hash)


def validate_registration_input(
    *,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    address: str,
    password: str,
    confirm_password: str,
) -> tuple[RegistrationData | None, list[str]]:
    """Validate and sanitize customer registration form fields."""
    errors: list[str] = []

    clean_first_name = first_name.strip()
    clean_last_name = last_name.strip()
    clean_email = normalize_email(email)
    clean_phone = phone.strip()
    clean_address = address.strip()

    if not clean_first_name:
        errors.append("First name is required.")
    elif len(clean_first_name) > 100:
        errors.append("First name must be 100 characters or fewer.")

    if not clean_last_name:
        errors.append("Last name is required.")
    elif len(clean_last_name) > 100:
        errors.append("Last name must be 100 characters or fewer.")

    if not clean_email:
        errors.append("Email address is required.")
    elif len(clean_email) > 255 or not EMAIL_REGEX.match(clean_email):
        errors.append("Please enter a valid email address.")

    digits_in_phone = sum(ch.isdigit() for ch in clean_phone)
    if not clean_phone:
        errors.append("Phone number is required.")
    elif (
        len(clean_phone) > 30
        or not PHONE_ALLOWED_REGEX.match(clean_phone)
        or digits_in_phone < 7
    ):
        errors.append("Please enter a valid phone number (7 to 30 characters).")

    if not clean_address:
        errors.append("Address is required.")
    elif len(clean_address) < 5 or len(clean_address) > 255:
        errors.append("Address must be between 5 and 255 characters.")

    if not password:
        errors.append("Password is required.")
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors.append(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    elif len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        errors.append(
            f"Password must not exceed {MAX_PASSWORD_BYTES} bytes in length."
        )

    if not confirm_password:
        errors.append("Please confirm your password.")
    elif password != confirm_password:
        errors.append("Passwords do not match.")

    if errors:
        return None, errors

    return (
        RegistrationData(
            first_name=clean_first_name,
            last_name=clean_last_name,
            email=clean_email,
            phone=clean_phone,
            address=clean_address,
            password=password,
        ),
        [],
    )


def get_or_create_csrf_token(request: Request) -> str:
    """Return the session CSRF token, creating one if absent."""
    token = request.session.get(CSRF_SESSION_KEY)
    if not isinstance(token, str) or len(token) < 32:
        token = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


def rotate_csrf_token(request: Request) -> str:
    """Generate and store a fresh CSRF token in the current session."""
    token = secrets.token_urlsafe(32)
    request.session[CSRF_SESSION_KEY] = token
    return token


def verify_csrf_token(request: Request, submitted_token: str | None) -> bool:
    """Validate a submitted CSRF token against the session token in constant time."""
    expected_token = request.session.get(CSRF_SESSION_KEY)
    if (
        not isinstance(expected_token, str)
        or not isinstance(submitted_token, str)
        or not expected_token
        or not submitted_token
    ):
        return False
    return hmac.compare_digest(expected_token, submitted_token)
