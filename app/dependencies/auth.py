"""Reusable authentication and role-based authorization dependencies."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from app.repositories.user_repository import AuthenticatedUser, get_user_by_id

SESSION_USER_ID_KEY = "user_id"
SESSION_ROLE_KEY = "role"
SESSION_EMAIL_KEY = "email"
SESSION_CUSTOMER_ID_KEY = "customer_id"


def get_current_user(request: Request) -> AuthenticatedUser | None:
    """Resolve the currently signed-in user from the session cookie."""
    raw_user_id = request.session.get(SESSION_USER_ID_KEY)
    if raw_user_id is None:
        return None

    try:
        user_id = int(raw_user_id)
    except (TypeError, ValueError):
        request.session.clear()
        return None

    user = get_user_by_id(user_id)
    if user is None:
        request.session.clear()
        return None

    return user


def require_authenticated(
    current_user: AuthenticatedUser | None = Depends(get_current_user),
) -> AuthenticatedUser:
    """Require an active authenticated user session."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return current_user


def require_role(*allowed_roles: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """Build a reusable FastAPI dependency enforcing allowed user roles ('C' or 'E')."""
    normalized_roles = {role.upper() for role in allowed_roles}

    def _check_role(
        current_user: AuthenticatedUser = Depends(require_authenticated),
    ) -> AuthenticatedUser:
        if current_user.role not in normalized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return _check_role


require_customer = require_role("C")
require_employee = require_role("E")
