"""Protected customer account routes."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.core.security import get_or_create_csrf_token
from app.core.templates import templates
from app.dependencies.auth import require_customer
from app.repositories.user_repository import AuthenticatedUser

router = APIRouter()


@router.get("/account", response_class=HTMLResponse, include_in_schema=False)
def customer_account_page(
    request: Request,
    current_user: AuthenticatedUser = Depends(require_customer),
):
    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request=request,
        name="account.html",
        context={
            "current_user": current_user,
            "csrf_token": csrf_token,
        },
    )
