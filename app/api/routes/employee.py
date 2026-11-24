"""Protected employee-only routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.core.security import get_or_create_csrf_token
from app.core.templates import templates
from app.dependencies.auth import require_employee
from app.repositories.user_repository import AuthenticatedUser

router = APIRouter()


@router.get("/employee", response_class=HTMLResponse, include_in_schema=False)
def employee_portal_page(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_employee),
):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request=request,
        name="employee.html",
        context={
            "current_user": current_user,
            "csrf_token": csrf_token,
        },
    )


@router.get("/api/employee/status", tags=["employee"])
def employee_status(
    current_user: AuthenticatedUser = Depends(require_employee),
) -> dict[str, object]:
    """Employee-only API endpoint verifying role-based access control."""
    return {
        "status": "authorized",
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
    }
