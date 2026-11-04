"""API router for global pipeline stage metadata and capabilities."""

from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import success
from app.db.session import get_db
from app.models.user import User
from app.services.pipeline_stages import get_registered_stages_summary

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


@router.get("/stages")
def get_pipeline_stages(
    current_user: User = Depends(get_current_user),
):
    """Retrieve metadata registry of all pipeline stages and their availability."""
    stages = get_registered_stages_summary()
    return success(data=stages)
