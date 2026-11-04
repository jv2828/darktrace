"""Pydantic schemas for authentication and tokens."""

from typing import Any, Dict
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Payload for user authentication."""
    identifier: str = Field(..., description="Email address or username")
    password: str = Field(..., description="Plaintext password")


class ChangePasswordRequest(BaseModel):
    """Payload for password change by authenticated user."""
    current_password: str = Field(..., description="Existing plaintext password")
    new_password: str = Field(..., description="New replacement password conforming to policy")


class TokenResponse(BaseModel):
    """Standard authentication token payload."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]

