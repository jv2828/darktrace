from pathlib import Path
from typing import Optional, Union
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate root directory (3 levels up from backend/app/core/config.py)
ROOT_DIR = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables or root .env."""

    # Environment (development | production)
    APP_ENV: str = "development"

    # PostgreSQL Database Configuration
    DATABASE_URL: Optional[str] = None
    DB_NAME: str = "darktrace"
    DB_USER: str = "darktrace"
    DB_PASSWORD: str = "change_me"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    # Isolated Test Database
    TEST_DB_NAME: str = "darktrace_test"

    # Security & JWT Authentication
    SECRET_KEY: str = "change_me_later"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15

    # Optional Admin Bootstrap (provision on startup when no admin exists)
    BOOTSTRAP_ADMIN_EMAIL: Optional[str] = None
    BOOTSTRAP_ADMIN_USERNAME: Optional[str] = None
    BOOTSTRAP_ADMIN_PASSWORD: Optional[str] = None
    BOOTSTRAP_ADMIN_FULL_NAME: Optional[str] = None

    # Reports Storage Directory
    REPORTS_DIR: Optional[str] = None

    # CORS Configuration
    CORS_ORIGINS: Union[str, list[str]] = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
    )

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """Refuse startup in production if SECRET_KEY is insecure or placeholder."""
        if self.APP_ENV.lower() == "production":
            placeholders = {"change_me_later", "change_me", "secret", ""}
            secret = (self.SECRET_KEY or "").strip()
            if secret in placeholders or len(secret) < 32:
                raise ValueError(
                    "SECRET_KEY must be a secure random string of at least 32 characters in production mode."
                )
        return self

    @property
    def database_url(self) -> str:
        """Construct the SQLAlchemy PostgreSQL connection URL using the psycopg 3 driver."""
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            url = self.DATABASE_URL.strip()
            if url.startswith("postgres://"):
                return "postgresql+psycopg://" + url[len("postgres://") :]
            if url.startswith("postgresql://"):
                return "postgresql+psycopg://" + url[len("postgresql://") :]
            return url
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def test_database_url(self) -> str:
        """Construct the SQLAlchemy connection URL for the isolated test database."""
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.TEST_DB_NAME}"
        )

    @property
    def reports_dir_path(self) -> Path:
        """Resolve directory path for generated reports (defaults to backend/reports)."""
        if self.REPORTS_DIR and self.REPORTS_DIR.strip():
            return Path(self.REPORTS_DIR.strip()).resolve()
        return (Path(__file__).resolve().parents[2] / "reports").resolve()

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list of allowed origins."""
        if not self.CORS_ORIGINS:
            return []
        if isinstance(self.CORS_ORIGINS, list):
            return [str(origin).strip() for origin in self.CORS_ORIGINS if str(origin).strip()]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Global singleton instance
settings = Settings()


