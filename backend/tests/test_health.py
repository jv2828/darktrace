"""Tests for the /api/v1/health endpoint and response envelope."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from sqlalchemy.exc import OperationalError

from app.main import app
from app.db.session import get_db

client = TestClient(app)


def test_health_success_envelope():
    """Test health check when database is healthy and reachable."""

    # Create a mock session that succeeds when execute() is called
    mock_db = MagicMock()
    mock_db.execute.return_value = None

    def override_get_db():
        try:
            yield mock_db
        finally:
            pass

    # Apply dependency override
    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        payload = response.json()
        # Verify standard envelope structure
        assert payload["success"] is True
        assert payload["error"] is None
        assert isinstance(payload["meta"], dict)

        # Verify health payload data
        data = payload["data"]
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["version"] == "0.1.0"
        assert "timestamp" in data
    finally:
        app.dependency_overrides.clear()


def test_health_database_unavailable_envelope():
    """Test health check when database connection fails (503 response)."""

    # Create a mock session that raises OperationalError when execute() is called
    mock_db = MagicMock()
    mock_db.execute.side_effect = OperationalError("connection refused", None, Exception("Connection refused"))

    def override_get_db():
        try:
            yield mock_db
        finally:
            pass

    # Apply dependency override to simulate DB outage
    app.dependency_overrides[get_db] = override_get_db

    try:
        response = client.get("/api/v1/health")
        assert response.status_code == 503

        payload = response.json()
        # Verify standard error envelope structure
        assert payload["success"] is False
        assert payload["data"] is None
        assert isinstance(payload["meta"], dict)

        # Verify error structure
        error = payload["error"]
        assert error["code"] == "DATABASE_UNAVAILABLE"
        assert error["message"] == "PostgreSQL database is currently unreachable."
        assert "connection refused" in error["details"].lower()
    finally:
        app.dependency_overrides.clear()


def test_global_404_error_envelope():
    """Test that unexpected routes conform to the global error envelope."""
    response = client.get("/api/v1/unknown-endpoint")
    assert response.status_code == 404

    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "HTTP_404"
    assert isinstance(payload["meta"], dict)

