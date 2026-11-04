"""User administration endpoints (restricted to administrators)."""

import math
from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.exceptions import APIException
from app.core.responses import success
from app.core.security import hash_password, validate_password_policy
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    UserCreateRequest,
    UserResetPasswordRequest,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["User Administration"])


def _serialize_user(user: User) -> Dict[str, Any]:
    """Serialize a User entity into a safe dictionary, strictly omitting password hash."""
    role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": role_value,
        "is_active": user.is_active,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Create a new user account (admin only)."""
    clean_email = str(payload.email).strip().lower()
    clean_username = payload.username.strip().lower()

    # Enforce unique email and username
    conflict_stmt = select(User).where(
        (func.lower(User.email) == clean_email) | (func.lower(User.username) == clean_username)
    )
    existing_user = db.execute(conflict_stmt).scalar_one_or_none()
    if existing_user:
        raise APIException(
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            message="A user with this email or username already exists.",
        )

    # Validate initial password against policy
    is_compliant, error_message = validate_password_policy(
        payload.password,
        username=payload.username,
        email=clean_email,
    )
    if not is_compliant:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WEAK_PASSWORD",
            message=error_message or "Password does not comply with security policy.",
        )

    # Create user
    new_user = User(
        email=clean_email,
        username=payload.username.strip(),
        full_name=payload.full_name.strip(),
        role=payload.role,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return success(data=_serialize_user(new_user))


@router.get("", status_code=status.HTTP_200_OK)
def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """List system users with pagination (admin only)."""
    total = db.scalar(select(func.count()).select_from(User)) or 0
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

    offset = (page - 1) * page_size
    stmt = select(User).order_by(User.id).offset(offset).limit(page_size)
    users = db.execute(stmt).scalars().all()

    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    return success(data=[_serialize_user(u) for u in users], meta=meta)


@router.get("/{user_id}", status_code=status.HTTP_200_OK)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Retrieve details for a specific user (admin only)."""
    target_user = db.get(User, user_id)
    if not target_user:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="User not found.",
        )
    return success(data=_serialize_user(target_user))


@router.patch("/{user_id}", status_code=status.HTTP_200_OK)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Update user attributes (admin only). Enforces self-protection and last-admin safety rules."""
    target_user = db.get(User, user_id)
    if not target_user:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="User not found.",
        )

    # Safety Rule 1: Administrator cannot deactivate or demote themselves
    if current_admin.id == target_user.id:
        if payload.is_active is False:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="SELF_DEACTIVATION_PROHIBITED",
                message="Administrators cannot deactivate their own account.",
            )
        if payload.role is not None and payload.role != UserRole.ADMIN:
            raise APIException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="SELF_DEMOTION_PROHIBITED",
                message="Administrators cannot demote their own account.",
            )

    # Safety Rule 2: The last active administrator can never be demoted or deactivated
    if target_user.role == UserRole.ADMIN and target_user.is_active:
        will_demote = payload.role is not None and payload.role != UserRole.ADMIN
        will_deactivate = payload.is_active is False
        if will_demote or will_deactivate:
            active_admin_count = (
                db.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
                )
                or 0
            )
            if active_admin_count <= 1:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="LAST_ADMIN_PROTECTED",
                    message="Cannot deactivate or demote the last active administrator.",
                )

    # Apply changes
    if payload.full_name is not None:
        target_user.full_name = payload.full_name.strip()
    if payload.role is not None:
        target_user.role = payload.role
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    db.commit()
    db.refresh(target_user)

    return success(data=_serialize_user(target_user))


@router.post("/{user_id}/reset-password", status_code=status.HTTP_200_OK)
def reset_user_password(
    user_id: int,
    payload: UserResetPasswordRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Administratively reset a user's password and clear any lockout status."""
    target_user = db.get(User, user_id)
    if not target_user:
        raise APIException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message="User not found.",
        )

    # Validate password policy
    is_compliant, error_message = validate_password_policy(
        payload.password,
        username=target_user.username,
        email=target_user.email,
    )
    if not is_compliant:
        raise APIException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WEAK_PASSWORD",
            message=error_message or "Password does not comply with security policy.",
        )

    # Update hash and clear any active lockout
    target_user.password_hash = hash_password(payload.password)
    target_user.failed_login_attempts = 0
    target_user.locked_until = None
    db.commit()

    return success(data={"message": "Password reset successfully"})

