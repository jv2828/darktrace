"""Pydantic schemas for scoring configurations."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class ScoringConfigResponse(BaseModel):
    """Active scoring configuration parameters."""

    id: int
    name: str
    version: int
    weights: Dict[str, Any]
    thresholds: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScoringConfigUpdateRequest(BaseModel):
    """Request payload to upgrade or modify active scoring configuration."""

    weights: Dict[str, float]
    thresholds: Optional[Dict[str, Any]] = None


