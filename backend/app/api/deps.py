"""Authentication and role-based authorization dependencies for DARKTRACE API."""

from collections.abc import Callable
from fastapi import Depends, Request, status
from sqlalchemy.orm import Session

from app.core.exceptions import APIException
from app.core.security import TokenExpiredError, TokenInvalidError, decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Validate Bearer access token and load the active user from database on every request.

    Raises:
        APIException: 401 with codes NOT_AUTHENTICATED, TOKEN_EXPIRED, TOKEN_INVALID, or ACCOUNT_DISABLED.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="NOT_AUTHENTICATED",
            message="Authentication credentials were not provided.",
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="NOT_AUTHENTICATED",
            message="Invalid authorization header format. Expected Bearer token.",
        )

    token = parts[1].strip()
    if not token:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="NOT_AUTHENTICATED",
            message="Bearer token cannot be empty.",
        )

    try:
        payload = decode_access_token(token)
    except TokenExpiredError:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_EXPIRED",
            message="Authentication token has expired.",
        )
    except TokenInvalidError:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_INVALID",
            message="Authentication token is invalid or tampered.",
        )

    user_id_raw = payload.get("sub")
    if not user_id_raw:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_INVALID",
            message="Authentication token is missing required subject claim.",
        )

    try:
        user_id = int(user_id_raw)
    except ValueError:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_INVALID",
            message="Authentication token contains an invalid user identifier.",
        )

    user = db.get(User, user_id)
    if not user:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_INVALID",
            message="User associated with this token no longer exists.",
        )

    if not user.is_active:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="ACCOUNT_DISABLED",
            message="Account has been deactivated.",
        )

    return user


def require_role(*roles: UserRole) -> Callable[..., User]:
    """Dependency factory checking that current user possesses at least one of the required roles."""

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise APIException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
                message="You do not have permission to access this resource.",
            )
        return current_user

    return role_checker


# Role-based dependency shortcuts
require_admin = require_role(UserRole.ADMIN)
require_investigator_or_admin = require_role(UserRole.INVESTIGATOR, UserRole.ADMIN)

