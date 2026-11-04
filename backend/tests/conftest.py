"""Pytest fixtures for isolated database testing."""

import pytest
import psycopg
from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import get_db
from app.main import app

# Path to alembic.ini
BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = BACKEND_DIR / "alembic.ini"



@pytest.fixture(scope="session")
def setup_test_db():
    """Ensure the isolated test database exists and has schema applied."""
    # 1. Connect to default postgres DB with autocommit to create test DB if needed
    admin_conn = psycopg.connect(
        dbname="postgres",
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        autocommit=True,
    )
    cur = admin_conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.TEST_DB_NAME,))
    if not cur.fetchone():
        cur.execute(f"CREATE DATABASE {settings.TEST_DB_NAME}")
    admin_conn.close()

    # 2. Run Alembic upgrade head against the test DB
    alembic_cfg = Config(str(ALEMBIC_INI_PATH))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.test_database_url)
    command.upgrade(alembic_cfg, "head")

    yield

    # Clean up can be added if needed, but keeping the test DB is standard for speed


@pytest.fixture(scope="session")
def test_engine(setup_test_db):
    """Provide a SQLAlchemy engine bound to the test database."""
    engine = create_engine(settings.test_database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """Provide a database session with automatic transaction rollback per test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Provide a TestClient with get_db overridden to use the isolated test session."""
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def alembic_cfg():
    """Provide an Alembic Config instance pointed at the test database."""
    cfg = Config(str(ALEMBIC_INI_PATH))
    cfg.set_main_option("sqlalchemy.url", settings.test_database_url)
    return cfg

