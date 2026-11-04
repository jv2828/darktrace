"""Pydantic schemas for analytical pipeline execution and stage progress."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class PipelineRunCreateRequest(BaseModel):
    """Payload to trigger a new pipeline analysis run."""

    stages: Optional[List[str]] = None


class PipelineStageInfo(BaseModel):
    """Static stage registration metadata."""

    name: str
    label: str
    description: str
    available: bool


class PipelineStageRunResponse(BaseModel):
    """Status and metrics of an executed pipeline stage."""

    id: int
    stage: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    items_processed: int = 0
    summary: Dict[str, Any] = {}
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PipelineRunResponse(BaseModel):
    """Complete status record for a pipeline run instance."""

    id: int
    investigation_id: int
    scoring_config_id: Optional[int] = None
    status: str
    triggered_by: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    is_stale: bool = False
    stages: List[PipelineStageRunResponse] = []

    model_config = ConfigDict(from_attributes=True)

