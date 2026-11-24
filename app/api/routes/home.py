from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.core.security import get_or_create_csrf_token
from app.core.templates import templates
from app.dependencies.auth import get_current_user
from app.repositories.user_repository import AuthenticatedUser

router = APIRouter()


# keeping this route at root so it wont be added to swagger docs
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
