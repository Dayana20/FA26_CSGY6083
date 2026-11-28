from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()
STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


# These are page routes rather than API endpoints, so keep them out of Swagger.
@router.get("/", include_in_schema=False)
def home_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/book-cruise", include_in_schema=False)
def book_cruise_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "book-cruise.html")


@router.get("/dashboard", include_in_schema=False)
def user_dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")


@router.get("/admin/dashboard", include_in_schema=False)
def admin_dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin-dashboard.html")


@router.get("/admin/cruise-trips", include_in_schema=False)
def admin_cruise_trips() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin-cruise-trips.html")
