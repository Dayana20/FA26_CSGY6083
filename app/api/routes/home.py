from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.core.security import get_or_create_csrf_token
from app.core.templates import templates
from app.dependencies.auth import get_current_user
from app.repositories.user_repository import AuthenticatedUser

router = APIRouter()
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


# These are page routes rather than API endpoints, so keep them out of Swagger.
@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home_page(
    request: Request,
    current_user: AuthenticatedUser | None = Depends(get_current_user),
):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "current_user": current_user,
            "csrf_token": csrf_token,
        },
    )


@router.get("/dashboard", include_in_schema=False)
def user_dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")


@router.get("/admin/dashboard", include_in_schema=False)
def admin_dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin-dashboard.html")


@router.get("/admin/cruise-trips", include_in_schema=False)
def admin_cruise_trips() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin-cruise-trips.html")
