"""Application configuration loaded from environment variables."""

import os
import warnings
from dataclasses import dataclass

_DEV_FALLBACK_SESSION_SECRET = "dev-only-insecure-session-secret-change-in-env"


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SessionSettings:
    app_env: str
    secret_key: str
    cookie_name: str
    same_site: str
    https_only: bool
    max_age: int


def get_session_settings() -> SessionSettings:
    """Build session middleware settings from environment variables."""
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    secret_key = os.getenv("SESSION_SECRET_KEY", "").strip()

    if not secret_key:
        if app_env == "production":
            raise RuntimeError(
                "SESSION_SECRET_KEY must be set when APP_ENV is 'production'."
            )
        warnings.warn(
            "SESSION_SECRET_KEY is not set; using development fallback secret.",
            UserWarning,
            stacklevel=2,
        )
        secret_key = _DEV_FALLBACK_SESSION_SECRET

    https_only = _parse_bool(
        os.getenv("SESSION_HTTPS_ONLY"),
        default=(app_env == "production"),
    )

    raw_max_age = os.getenv("SESSION_MAX_AGE", "3600").strip()
    try:
        max_age = int(raw_max_age)
        if max_age <= 0:
            raise ValueError("SESSION_MAX_AGE must be positive.")
    except ValueError:
        max_age = 3600

    return SessionSettings(
        app_env=app_env,
        secret_key=secret_key,
        cookie_name="adh_session",
        same_site="lax",
        https_only=https_only,
        max_age=max_age,
    )
