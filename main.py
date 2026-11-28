"""Entry point for the Cruise Trip Booking API.

Start the development server from the project root with:

    uvicorn main:app --reload

The API documentation is then at http://127.0.0.1:8000/docs.
"""
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.core.config import get_session_settings

# Load the MySQL settings from .env into the environment before anything
# connects to the database.
load_dotenv()

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_NO_STORE_PREFIXES = ("/login", "/register", "/logout", "/account", "/employee", "/auth", "/api/employee", "/dashboard", "/admin")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )

        path = request.url.path
        if not path.startswith(_DOCS_PATHS):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; script-src 'self'; "
                "form-action 'self'; frame-ancestors 'none'; base-uri 'self'",
            )

        if path.startswith(_NO_STORE_PREFIXES):
            response.headers["Cache-Control"] = "no-store"

        return response


session_settings = get_session_settings()

# Create the FastAPI application and register every endpoint
# (see app/api/router.py for the list).
app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=session_settings.secret_key,
    session_cookie=session_settings.cookie_name,
    max_age=session_settings.max_age,
    same_site=session_settings.same_site,
    https_only=session_settings.https_only,
)
app.add_middleware(SecurityHeadersMiddleware)
app.include_router(api_router)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "app" / "static"),
    name="static",
)