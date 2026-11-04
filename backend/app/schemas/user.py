"""Pydantic schemas for user management."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserCreateRequest(BaseModel):
    """Payload for creating a new user account (admin only)."""
    email: EmailStr = Field(..., description="Unique email address")
    username: str = Field(..., min_length=2, max_length=100, description="Unique username handle")
    full_name: str = Field(..., min_length=1, max_length=255, description="Full name or alias")
    role: UserRole = Field(..., description="Assigned role (admin | investigator)")
    password: str = Field(..., description="Initial account password")


class UserUpdateRequest(BaseModel):
    """Payload for updating an existing user account (admin only)."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResetPasswordRequest(BaseModel):
    """Payload for administrative password reset."""
    password: str = Field(..., description="New password set by administrator")


class UserResponse(BaseModel):
    """Public representation of a user account (never exposes password hash)."""
    id: int
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
