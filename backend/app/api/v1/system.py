"""System status and diagnostics endpoints for DARKTRACE."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.config import settings
from app.core.responses import error, success
from app.db.session import get_db
from app.models.user import User

router = APIRouter()

MODEL_TABLES = [
    "users",
    "datasets",
    "investigations",
    "investigation_datasets",
    "marketplaces",
    "threat_actors",
    "actor_aliases",
    "posts",
    "extracted_indicators",
    "scoring_configs",
    "pipeline_runs",
    "pipeline_stage_runs",
    "evidence_records",
    "evidence_sources",
    "correlation_results",
    "analysis_results",
    "investigation_reports",
]


@router.get("/system/info", status_code=status.HTTP_200_OK)
def get_system_info(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    """Retrieve database schema revision, real table row counts, and environment."""
    try:
        # 1. Read current Alembic revision from alembic_version table
        try:
            revision_query = text("SELECT version_num FROM alembic_version LIMIT 1")
            schema_revision = db.execute(revision_query).scalar_one_or_none()
        except Exception:
            schema_revision = None

        # 2. Query real row counts for every model table
        table_counts: dict[str, int] = {}
        for table_name in MODEL_TABLES:
            count_query = text(f"SELECT count(*) FROM {table_name}")
            row_count = db.execute(count_query).scalar()
            table_counts[table_name] = int(row_count or 0)

        data = {
            "schema_revision": schema_revision,
            "tables": table_counts,
            "environment": settings.APP_ENV,
        }
        return success(data=data)

    except Exception as exc:
        details = str(exc) if settings.APP_ENV == "development" else None
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error(
                code="SYSTEM_INFO_ERROR",
                message="Unable to retrieve system diagnostic information.",
                details=details,
            ),
        )

