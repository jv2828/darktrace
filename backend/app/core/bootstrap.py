"""Bootstrap administrative user on system startup."""

import logging
import os
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, validate_password_policy
from app.db.session import SessionLocal
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


def bootstrap_admin_user(
    db: Optional[Session] = None,
    email: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    full_name: Optional[str] = None,
    raise_on_policy_violation: bool = False,
) -> Optional[User]:
    """Bootstrap an initial administrator account if configured via environment variables.

    Execution conditions:
    1. BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_USERNAME, and BOOTSTRAP_ADMIN_PASSWORD
       must all be non-empty strings.
    2. No user with role == UserRole.ADMIN exists yet in the database.
    3. The password must satisfy the existing system password policy.

    Security & Safety:
    - Never logs or exposes the plaintext password under any circumstance.
    - If any requirement is not met, does nothing and returns None (unless
      raise_on_policy_violation=True is explicitly requested).
    """
    target_email = (
        email
        if email is not None
        else (getattr(settings, "BOOTSTRAP_ADMIN_EMAIL", None) or os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "")
    ).strip()
    target_username = (
        username
        if username is not None
        else (getattr(settings, "BOOTSTRAP_ADMIN_USERNAME", None) or os.getenv("BOOTSTRAP_ADMIN_USERNAME") or "")
    ).strip()
    target_password = (
        password
        if password is not None
        else (getattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", None) or os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or "")
    ).strip()

    # If any required credential is missing or empty, do nothing
    if not target_email or not target_username or not target_password:
        return None

    target_full_name = (
        full_name
        if full_name is not None
        else (
            getattr(settings, "BOOTSTRAP_ADMIN_FULL_NAME", None)
            or os.getenv("BOOTSTRAP_ADMIN_FULL_NAME")
            or "Administrator"
        )
    ).strip()
    if not target_full_name:
        target_full_name = "Administrator"

    if db is not None:
        return _execute_bootstrap(
            db=db,
            email=target_email,
            username=target_username,
            password=target_password,
            full_name=target_full_name,
            raise_on_policy_violation=raise_on_policy_violation,
        )

    try:
        with SessionLocal() as session:
            return _execute_bootstrap(
                db=session,
                email=target_email,
                username=target_username,
                password=target_password,
                full_name=target_full_name,
                raise_on_policy_violation=raise_on_policy_violation,
            )
    except Exception as exc:
        logger.error("Failed to execute administrator bootstrap startup step: %s", exc)
        return None


def _execute_bootstrap(
    db: Session,
    email: str,
    username: str,
    password: str,
    full_name: str,
    raise_on_policy_violation: bool = False,
) -> Optional[User]:
    """Execute bootstrap check and creation against an active database session."""
    # Check if an admin user already exists
    existing_admin = db.scalar(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )
    if existing_admin:
        logger.info("Admin user already exists. Skipping bootstrap.")
        return None

    # Validate against existing password policy (never log the password!)
    is_compliant, policy_err = validate_password_policy(
        password=password,
        username=username,
        email=email,
    )
    if not is_compliant:
        logger.warning(
            "Bootstrap admin password failed security policy: %s. Admin user not created.",
            policy_err,
        )
        if raise_on_policy_violation:
            raise ValueError(f"Bootstrap admin password policy violation: {policy_err}")
        return None

    # Check if non-admin user exists with the same normalized email or username
    norm_email = email.lower()
    norm_username = username.lower()
    existing_user = db.scalar(
        select(User).where(
            (func.lower(User.email) == norm_email) | (func.lower(User.username) == norm_username)
        )
    )

    if existing_user:
        existing_user.role = UserRole.ADMIN
        existing_user.password_hash = hash_password(password)
        existing_user.is_active = True
        db.commit()
        db.refresh(existing_user)
        logger.info(
            "Promoted existing account '%s' (%s) to administrator.",
            existing_user.username,
            existing_user.email,
        )
        return existing_user

    # Create new administrator
    admin = User(
        email=email,
        username=username,
        full_name=full_name,
        role=UserRole.ADMIN,
        is_active=True,
        password_hash=hash_password(password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info(
        "Successfully bootstrapped initial admin user: '%s' (%s).",
        admin.username,
        admin.email,
    )
    return admin
