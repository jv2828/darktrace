"""Tests for application configuration, database URL conversion, CORS, and security validators."""

from pathlib import Path
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.report_service import get_reports_base_dir


def test_database_url_from_components(monkeypatch):
    """When DATABASE_URL is unset, database_url must be built from individual DB_* components."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(
        DATABASE_URL=None,
        DB_USER="custom_user",
        DB_PASSWORD="custom_password",
        DB_HOST="db.internal",
        DB_PORT=5433,
        DB_NAME="custom_db",
    )
    assert s.database_url == "postgresql+psycopg://custom_user:custom_password@db.internal:5433/custom_db"


def test_database_url_postgres_prefix_converted():
    """Render/Heroku style postgres:// URL must be converted to postgresql+psycopg://."""
    s = Settings(DATABASE_URL="postgres://render_user:secret_pass@dpg-xxx-a:5432/darktrace_db")
    assert s.database_url == "postgresql+psycopg://render_user:secret_pass@dpg-xxx-a:5432/darktrace_db"


def test_database_url_postgresql_prefix_converted():
    """Standard postgresql:// URL must be converted to postgresql+psycopg://."""
    s = Settings(DATABASE_URL="postgresql://render_user:secret_pass@dpg-xxx-a:5432/darktrace_db")
    assert s.database_url == "postgresql+psycopg://render_user:secret_pass@dpg-xxx-a:5432/darktrace_db"


def test_database_url_psycopg_prefix_preserved():
    """Explicit postgresql+psycopg:// URL must be preserved intact."""
    s = Settings(DATABASE_URL="postgresql+psycopg://render_user:secret_pass@dpg-xxx-a:5432/darktrace_db")
    assert s.database_url == "postgresql+psycopg://render_user:secret_pass@dpg-xxx-a:5432/darktrace_db"


def test_database_url_empty_or_whitespace_falls_back():
    """Empty or whitespace-only DATABASE_URL falls back to DB_* components."""
    s = Settings(
        DATABASE_URL="   ",
        DB_USER="darktrace",
        DB_PASSWORD="secretpassword",
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_NAME="darktrace",
    )
    assert s.database_url == "postgresql+psycopg://darktrace:secretpassword@localhost:5432/darktrace"


def test_secret_key_production_validation_rejects_weak():
    """In production mode, a short or placeholder SECRET_KEY must raise a validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(APP_ENV="production", SECRET_KEY="change_me_later")
    assert "SECRET_KEY must be a secure random string" in str(exc_info.value)

    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", SECRET_KEY="short-secret-key")

    with pytest.raises(ValidationError):
        Settings(APP_ENV="production", SECRET_KEY="")


def test_secret_key_production_validation_accepts_strong():
    """In production mode, a 32+ character random SECRET_KEY is accepted."""
    secure_key = "a" * 32
    s = Settings(APP_ENV="production", SECRET_KEY=secure_key)
    assert s.SECRET_KEY == secure_key


def test_secret_key_development_allows_placeholder():
    """In development mode, weak or placeholder keys remain permitted for local ease of use."""
    s = Settings(APP_ENV="development", SECRET_KEY="change_me_later")
    assert s.SECRET_KEY == "change_me_later"


def test_cors_origins_comma_separated_list():
    """CORS_ORIGINS must parse comma-separated strings into trimmed lists."""
    s = Settings(
        CORS_ORIGINS="https://darktrace.vercel.app, http://localhost:5173 , https://app.darktrace.io"
    )
    assert s.cors_origins_list == [
        "https://darktrace.vercel.app",
        "http://localhost:5173",
        "https://app.darktrace.io",
    ]


def test_cors_origins_wildcard():
    """CORS_ORIGINS with a single wildcard or domain parses cleanly."""
    s = Settings(CORS_ORIGINS="*")
    assert s.cors_origins_list == ["*"]


def test_cors_origins_empty():
    """Empty CORS_ORIGINS parses to empty list."""
    s = Settings(CORS_ORIGINS="")
    assert s.cors_origins_list == []


def test_reports_dir_default():
    """When REPORTS_DIR is unset, reports_dir_path points to backend/reports."""
    s = Settings(REPORTS_DIR=None)
    assert s.reports_dir_path.name == "reports"
    assert s.reports_dir_path.is_absolute()


def test_reports_dir_custom_configurable(tmp_path):
    """When REPORTS_DIR is set, reports_dir_path resolves to the specified path."""
    custom_dir = str(tmp_path / "custom_reports")
    s = Settings(REPORTS_DIR=custom_dir)
    assert s.reports_dir_path == Path(custom_dir).resolve()


def test_report_service_base_dir_resolution(tmp_path, monkeypatch):
    """Report service get_reports_base_dir respects settings.reports_dir_path and creates directory."""
    target_path = tmp_path / "gen_reports"
    assert not target_path.exists()

    monkeypatch.setattr("app.core.config.settings.REPORTS_DIR", str(target_path))
    resolved = get_reports_base_dir()
    assert resolved == target_path.resolve()
    assert resolved.exists()
    assert resolved.is_dir()
