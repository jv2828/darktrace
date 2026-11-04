"""Cryptographic security utilities for DARKTRACE.

Handles Argon2id password hashing, JWT creation/validation, and password policies.
"""

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
import jwt

from app.core.config import settings

# Global Argon2 PasswordHasher instance
_hasher = PasswordHasher()


class TokenError(Exception):
    """Base exception for authentication token issues."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class TokenExpiredError(TokenError):
    """Raised when an access token has expired."""

    def __init__(self, message: str = "Authentication token has expired."):
        super().__init__("TOKEN_EXPIRED", message)


class TokenInvalidError(TokenError):
    """Raised when an access token is corrupted, tampered, or invalid."""

    def __init__(self, message: str = "Authentication token is invalid or corrupted."):
        super().__init__("TOKEN_INVALID", message)


def hash_password(password: str) -> str:
    """Hash plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> Tuple[bool, bool]:
    """Verify plaintext password against an Argon2 hash.

    Returns:
        Tuple of (is_valid, needs_rehash).
    """
    try:
        _hasher.verify(hashed_password, plain_password)
        needs_rehash = _hasher.check_needs_rehash(hashed_password)
        return True, needs_rehash
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, False


def create_access_token(user: Any, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token for an authenticated user."""
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    payload = {
        "sub": str(user.id),
        "role": role_str,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a signed JWT token.

    Raises:
        TokenExpiredError: If token expired.
        TokenInvalidError: If token signature or claims are invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "role", "iat", "exp"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError()
    except (jwt.InvalidTokenError, Exception) as exc:
        raise TokenInvalidError(f"Authentication token is invalid: {str(exc)}")


def validate_password_policy(
    password: str,
    username: str = "",
    email: str = "",
) -> Tuple[bool, Optional[str]]:
    """Validate password against security policy.

    Rules:
    - Minimum 10 characters long
    - Must not equal username (case-insensitive)
    - Must not equal email (case-insensitive)
    - Must contain at least one letter
    - Must contain at least one digit

    Returns:
        (is_valid, error_message)
    """
    if len(password) < 10:
        return False, "Password must be at least 10 characters long."

    if username and password.strip().lower() == username.strip().lower():
        return False, "Password must not match your username."

    if email and password.strip().lower() == email.strip().lower():
        return False, "Password must not match your email address."

    if not re.search(r"[A-Za-z]", password):
        return False, "Password must contain at least one letter."

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."

    return True, None

