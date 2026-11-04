from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Locate root directory (3 levels up from backend/app/core/config.py)
ROOT_DIR = Path(__file__).resolve().parents[3]
ROOT_ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables or root .env."""

    # PostgreSQL Database Configuration
    DB_NAME: str = "darktrace"
    DB_USER: str = "darktrace"
    DB_PASSWORD: str = "change_me"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    # Security
    SECRET_KEY: str = "change_me_later"

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """Construct the SQLAlchemy PostgreSQL connection URL using the psycopg 3 driver."""
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list of allowed origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Global singleton instance
settings = Settings()

