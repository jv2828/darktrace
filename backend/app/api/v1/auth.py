"""Authentication endpoints for login, session introspection, and password updates."""

from datetime import datetime, timedelta, timezone
import math
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.exceptions import APIException
from app.core.responses import success
from app.core.security import (
    create_access_token,
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", status_code=status.HTTP_200_OK)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    """Authenticate user with identifier (email or username) and password."""
    now = datetime.now(timezone.utc)
    identifier_clean = payload.identifier.strip().lower()

    # Query user by normalized email or username
    stmt = select(User).where(
        (func.lower(User.email) == identifier_clean) | (func.lower(User.username) == identifier_clean)
    )
    user = db.execute(stmt).scalar_one_or_none()

    # Generic credential rejection for unknown users (avoids username enumeration)
    if not user:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Invalid credentials",
        )

    # Check for temporary account lockout
    if user.locked_until is not None:
        if user.locked_until > now:
            remaining_seconds = (user.locked_until - now).total_seconds()
            minutes_remaining = max(1, math.ceil(remaining_seconds / 60))
            raise APIException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="ACCOUNT_LOCKED",
                message=f"Account is temporarily locked due to excessive failed attempts. Try again in {minutes_remaining} minutes.",
                details={"minutes_remaining": minutes_remaining},
            )
        else:
            # Lockout period expired
            user.locked_until = None
            user.failed_login_attempts = 0
            db.commit()

    # Reject inactive accounts with the same generic message to prevent enumeration
    if not user.is_active:
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Invalid credentials",
        )

    # Verify password hash
    is_valid, needs_rehash = verify_password(payload.password, user.password_hash)
    if not is_valid:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            db.commit()
            raise APIException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="ACCOUNT_LOCKED",
                message=f"Account is temporarily locked due to excessive failed attempts. Try again in {settings.LOCKOUT_MINUTES} minutes.",
                details={"minutes_remaining": settings.LOCKOUT_MINUTES},
            )

        db.commit()
        raise APIException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            message="Invalid credentials",
        )

    # Password is correct: reset lockout state and record login timestamp
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash:
        user.password_hash = hash_password(payload.password)
    db.commit()

    # Create signed access token
    access_token = create_access_token(user)
    role_value = user.role.value if hasattr(user.role, "value") else str(user.role)

    data = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "role": role_value,
        },
    }
    return success(data=data)


@router.get("/me", status_code=status.HTTP_200_OK)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Retrieve profile and role info for currently authenticated user."""
    role_value = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    data = {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "role": role_value,
        "is_active": current_user.is_active,
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
    }
    return success(data=data)


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change password for currently authenticated user."""
    # Verify current password
    is_valid, _ = verify_password(payload.current_password, current_user.password_hash)
    if not is_valid:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_CURRENT_PASSWORD",
            message="Current password is incorrect.",
        )

    # Validate replacement against password policy
    is_compliant, error_message = validate_password_policy(
        payload.new_password,
        username=current_user.username,
        email=current_user.email,
    )
    if not is_compliant:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WEAK_PASSWORD",
            message=error_message or "New password does not comply with security policy.",
        )

    # Update hash and save
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()

    return success(data={"message": "Password changed successfully"})
