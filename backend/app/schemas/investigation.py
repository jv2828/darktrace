"""Pydantic schemas for Investigation endpoints."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.investigation import InvestigationStatus


class InvestigationCreateRequest(BaseModel):
    """Payload for creating a new investigation."""
    title: str = Field(..., description="Investigation title (3-200 characters)")
    description: Optional[str] = Field(None, max_length=2000, description="Optional case notes or description")

    @field_validator("title")
    @classmethod
    def validate_and_strip_title(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 3:
            raise ValueError("Title must be at least 3 characters long after trimming.")
        if len(trimmed) > 200:
            raise ValueError("Title cannot exceed 200 characters.")
        return trimmed

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        return trimmed if trimmed else None


class InvestigationCreatorSummary(BaseModel):
    """Minimal representation of the user who created an investigation."""
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class InvestigationCounts(BaseModel):
    """Aggregated entity counts linked to an investigation."""
    posts: int = 0
    indicators: int = 0


class InvestigationResponse(BaseModel):
    """Public representation of an investigation."""
    id: int
    title: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    created_by: InvestigationCreatorSummary
    counts: InvestigationCounts

    model_config = ConfigDict(from_attributes=True)

