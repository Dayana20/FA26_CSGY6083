"""Authentication routes: registration, login, logout, and current-user inspection."""

import mysql.connector
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.security import (
    get_or_create_csrf_token,
    hash_password,
    normalize_email,
    rotate_csrf_token,
    validate_registration_input,
    verify_csrf_token,
    verify_password_constant_time,
)
from app.core.templates import templates
from app.dependencies.auth import (
    SESSION_CUSTOMER_ID_KEY,
    SESSION_EMAIL_KEY,
    SESSION_ROLE_KEY,
    SESSION_USER_ID_KEY,
    get_current_user,
    require_authenticated,
)
from app.repositories.user_repository import (
    AuthenticatedUser,
    DuplicateEmailError,
    get_user_by_email,
    register_customer,
)

router = APIRouter()


@router.get("/register", response_class=HTMLResponse, include_in_schema=False)
def register_page(
    request: Request,
    current_user: AuthenticatedUser | None = Depends(get_current_user),
):
    if current_user is not None:
        destination = "/employee" if current_user.is_employee else "/account"
        return RedirectResponse(url=destination, status_code=status.HTTP_303_SEE_OTHER)

    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "current_user": None,
            "csrf_token": csrf_token,
            "errors": [],
            "form_data": {
                "first_name": "",
                "last_name": "",
                "email": "",
                "phone": "",
                "address": "",
            },
        },
    )


@router.post("/register", response_class=HTMLResponse, include_in_schema=False)
def register_submit(
    request: Request,
    first_name: str = Form(default=""),
    last_name: str = Form(default=""),
    email: str = Form(default=""),
    phone: str = Form(default=""),
    address: str = Form(default=""),
    password: str = Form(default=""),
    confirm_password: str = Form(default=""),
    csrf_token: str = Form(default=""),
):
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token.",
        )

    preserved_form = {
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.strip(),
        "phone": phone.strip(),
        "address": address.strip(),
    }

    registration_data, errors = validate_registration_input(
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        address=address,
        password=password,
        confirm_password=confirm_password,
    )

    if errors or registration_data is None:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "current_user": None,
                "csrf_token": get_or_create_csrf_token(request),
                "errors": errors,
                "form_data": preserved_form,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        password_hash = hash_password(registration_data.password)
        register_customer(
            first_name=registration_data.first_name,
            last_name=registration_data.last_name,
            email=registration_data.email,
            phone=registration_data.phone,
            address=registration_data.address,
            password_hash=password_hash,
        )
    except DuplicateEmailError:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "current_user": None,
                "csrf_token": get_or_create_csrf_token(request),
                "errors": ["An account with that email address already exists."],
                "form_data": preserved_form,
            },
            status_code=status.HTTP_409_CONFLICT,
        )
    except (mysql.connector.Error, KeyError, ValueError):
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "current_user": None,
                "csrf_token": get_or_create_csrf_token(request),
                "errors": ["Registration is temporarily unavailable. Please try again later."],
                "form_data": preserved_form,
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    rotate_csrf_token(request)
    return RedirectResponse(
        url="/login?registered=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(
    request: Request,
    registered: int | None = None,
    logged_out: int | None = None,
    current_user: AuthenticatedUser | None = Depends(get_current_user),
):
    if current_user is not None:
        destination = "/employee" if current_user.is_employee else "/account"
        return RedirectResponse(url=destination, status_code=status.HTTP_303_SEE_OTHER)

    notice = None
    if registered == 1:
        notice = "Account created successfully. Please log in."
    elif logged_out == 1:
        notice = "You have been logged out."

    csrf_token = get_or_create_csrf_token(request)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "current_user": None,
            "csrf_token": csrf_token,
            "notice": notice,
            "error": None,
            "email": "",
        },
    )


@router.post("/login", response_class=HTMLResponse, include_in_schema=False)
def login_submit(
    request: Request,
    email: str = Form(default=""),
    password: str = Form(default=""),
    csrf_token: str = Form(default=""),
):
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token.",
        )

    clean_email = normalize_email(email)
    if not clean_email or not password:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "current_user": None,
                "csrf_token": get_or_create_csrf_token(request),
                "notice": None,
                "error": "Invalid email or password.",
                "email": email.strip(),
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        record = get_user_by_email(clean_email)
    except (mysql.connector.Error, KeyError, ValueError):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "current_user": None,
                "csrf_token": get_or_create_csrf_token(request),
                "notice": None,
                "error": "Sign in is temporarily unavailable. Please try again later.",
                "email": email.strip(),
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    is_valid = verify_password_constant_time(
        password,
        record.password_hash if record is not None else None,
    )
    if not is_valid or record is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "current_user": None,
                "csrf_token": get_or_create_csrf_token(request),
                "notice": None,
                "error": "Invalid email or password.",
                "email": email.strip(),
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = record.user
    request.session.clear()
    rotate_csrf_token(request)
    request.session[SESSION_USER_ID_KEY] = user.user_id
    request.session[SESSION_ROLE_KEY] = user.role
    request.session[SESSION_EMAIL_KEY] = user.email
    request.session[SESSION_CUSTOMER_ID_KEY] = user.customer_id

    destination = "/employee" if user.is_employee else "/account"
    return RedirectResponse(url=destination, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout", include_in_schema=False)
def logout_submit(
    request: Request,
    csrf_token: str = Form(default=""),
):
    if not verify_csrf_token(request, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token.",
        )

    request.session.clear()
    rotate_csrf_token(request)
    return RedirectResponse(
        url="/login?logged_out=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/auth/me", tags=["auth"])
def auth_me(
    current_user: AuthenticatedUser = Depends(require_authenticated),
) -> dict[str, object]:
    """Return the authenticated user's profile without sensitive fields."""
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
        "customer_id": current_user.customer_id,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
    }
