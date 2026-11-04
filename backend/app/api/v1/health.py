"""Health check endpoint for DARKTRACE."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.responses import error, success
from app.db.session import get_db

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
def check_health(db: Session = Depends(get_db)):
    """Check system health and database connectivity.

    Executes 'SELECT 1' against PostgreSQL.
    If database is reachable: returns 200 with status envelope.
    If database is unreachable: returns 503 with standard error envelope.
    """
    try:
        db.execute(text("SELECT 1"))
        data = {
            "status": "ok",
            "database": "connected",
            "version": "0.1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return success(data=data)
    except Exception as exc:
        details = str(exc) if settings.APP_ENV == "development" else None
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=error(
                code="DATABASE_UNAVAILABLE",
                message="PostgreSQL database is currently unreachable.",
                details=details,
            ),
        )

