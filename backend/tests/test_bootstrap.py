"""Tests for administrator startup bootstrap logic and security enforcement."""

import logging
import pytest
from sqlalchemy import func, select

from app.core.bootstrap import bootstrap_admin_user
from app.core.security import hash_password, verify_password
from app.main import app, lifespan
from app.models.user import User, UserRole


def test_bootstrap_noop_when_env_vars_missing(db_session, monkeypatch):
    """When bootstrap environment variables are unset, bootstrap does nothing and returns None."""
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    admin = bootstrap_admin_user(db=db_session)
    assert admin is None

    # Verify no admin was created
    admin_count = db_session.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
    )
    assert admin_count == 0


@pytest.mark.parametrize(
    "email,username,password",
    [
        ("admin@darktrace.local", "admin", ""),  # missing password
        ("admin@darktrace.local", "", "StrongPass123!"),  # missing username
        ("", "admin", "StrongPass123!"),  # missing email
        ("   ", "admin", "StrongPass123!"),  # whitespace email
        ("admin@darktrace.local", "   ", "StrongPass123!"),  # whitespace username
        ("admin@darktrace.local", "admin", "   "),  # whitespace password
    ],
)
def test_bootstrap_noop_when_credentials_partial(db_session, monkeypatch, email, username, password):
    """If any of the three required bootstrap environment variables is missing or blank, do nothing."""
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", email)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", username)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", password)

    result = bootstrap_admin_user(db=db_session)
    assert result is None

    admin_count = db_session.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
    )
    assert admin_count == 0


def test_bootstrap_noop_when_admin_already_exists(db_session, monkeypatch):
    """If an administrator account already exists, bootstrap does nothing."""
    # Pre-existing admin
    existing = User(
        email="root_admin@darktrace.local",
        username="root_admin",
        full_name="Root Admin",
        role=UserRole.ADMIN,
        is_active=True,
        password_hash=hash_password("ExistingPass123!"),
    )
    db_session.add(existing)
    db_session.commit()

    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "new_admin@darktrace.local")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "new_admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "NewStrongPass123!")

    result = bootstrap_admin_user(db=db_session)
    assert result is None

    # Total admin count remains exactly 1
    admin_count = db_session.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
    )
    assert admin_count == 1

    # New admin was not created
    new_user = db_session.scalar(
        select(User).where(User.username == "new_admin")
    )
    assert new_user is None


def test_bootstrap_creates_new_admin_successfully(db_session, monkeypatch):
    """When all variables are set, no admin exists, and password is valid, admin is created."""
    email = "bootstrap_chief@darktrace.local"
    username = "bootstrap_chief"
    plain_password = "SuperSecurePassword123!"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", email)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", username)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", plain_password)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_FULL_NAME", "Chief Security Officer")

    admin = bootstrap_admin_user(db=db_session)
    assert admin is not None
    assert admin.email == email
    assert admin.username == username
    assert admin.full_name == "Chief Security Officer"
    assert admin.role == UserRole.ADMIN
    assert admin.is_active is True

    # Password hash verification using Argon2id
    is_valid, _ = verify_password(plain_password, admin.password_hash)
    assert is_valid is True

    # Verify persistent state in database
    db_admin = db_session.scalar(
        select(User).where(User.username == username)
    )
    assert db_admin is not None
    assert db_admin.id == admin.id
    assert db_admin.role == UserRole.ADMIN


def test_bootstrap_promotes_existing_non_admin_user(db_session, monkeypatch):
    """If an investigator exists with the same email/username, but no admin exists yet, promote them."""
    analyst = User(
        email="analyst_target@darktrace.local",
        username="analyst_target",
        full_name="Junior Analyst",
        role=UserRole.INVESTIGATOR,
        is_active=True,
        password_hash=hash_password("OldAnalystPass123!"),
    )
    db_session.add(analyst)
    db_session.commit()

    new_password = "PromotedPassword123!"
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", analyst.email)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", analyst.username)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", new_password)

    promoted = bootstrap_admin_user(db=db_session)
    assert promoted is not None
    assert promoted.id == analyst.id
    assert promoted.role == UserRole.ADMIN

    # Check updated password hash
    is_valid, _ = verify_password(new_password, promoted.password_hash)
    assert is_valid is True


def test_bootstrap_rejects_weak_password_and_never_logs_secret(db_session, monkeypatch, caplog):
    """When password violates policy, no admin is created, and the password is never logged."""
    weak_password = "short"  # Fails < 10 chars policy

    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@darktrace.local")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "admin_candidate")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", weak_password)

    with caplog.at_level(logging.DEBUG):
        result = bootstrap_admin_user(db=db_session)

    assert result is None
    admin_count = db_session.scalar(
        select(func.count()).select_from(User).where(User.role == UserRole.ADMIN)
    )
    assert admin_count == 0

    # Ensure secret is NOT in logs
    assert weak_password not in caplog.text

    # With explicit raise_on_policy_violation=True
    with pytest.raises(ValueError) as exc_info:
        bootstrap_admin_user(db=db_session, raise_on_policy_violation=True)
    assert "Bootstrap admin password policy violation" in str(exc_info.value)
    assert weak_password not in str(exc_info.value)


def test_bootstrap_password_matching_username_rejected(db_session, monkeypatch):
    """Password equal to username violates policy and results in no creation."""
    username = "system_admin"
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "system_admin@darktrace.local")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", username)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", username)

    result = bootstrap_admin_user(db=db_session)
    assert result is None


def test_bootstrap_password_never_logged_on_success(db_session, monkeypatch, caplog):
    """Even during successful bootstrap, the plaintext password must never appear in logs."""
    canary_password = "Un1queC@naryPassw0rd99!"
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "canary_admin@darktrace.local")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_USERNAME", "canary_admin")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", canary_password)

    with caplog.at_level(logging.DEBUG):
        admin = bootstrap_admin_user(db=db_session)

    assert admin is not None
    assert canary_password not in caplog.text


@pytest.mark.anyio
async def test_lifespan_invokes_bootstrap(monkeypatch):
    """FastAPI lifespan startup hook calls bootstrap_admin_user."""
    called = False

    def mock_bootstrap():
        nonlocal called
        called = True

    monkeypatch.setattr("app.main.bootstrap_admin_user", mock_bootstrap)
    monkeypatch.setattr("app.main.recover_interrupted_pipeline_runs", lambda: None)

    async with lifespan(app):
        pass

    assert called is True
