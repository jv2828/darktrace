"""Pydantic schemas for technical indicator extraction endpoints."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExtractionPreviewRequest(BaseModel):
    """Payload for stateless indicator extraction preview."""
    content: str = Field(..., min_length=1, max_length=20000, description="Raw post text to analyse")
    structured_indicators: Optional[Dict[str, Any]] = Field(None, description="Optional pre-structured indicators")


class ExtractionRerunRequest(BaseModel):
    """Payload for triggering investigation indicator extraction rerun."""
    force: bool = Field(False, description="Whether to re-extract all posts even if already on current version")

