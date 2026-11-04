"""Pydantic schemas for forensic dossier export requests and responses."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReportCreateRequest(BaseModel):
    """Payload for generating an investigation dossier report."""
    format: str = Field(..., pattern="^(?i)(pdf|csv|json)$", description="Export file format")
    run_id: Optional[int] = Field(None, description="Pipeline run ID (defaults to latest completed)")
    csv_kind: Optional[str] = Field(None, pattern="^(?i)(pairs|evidence|indicators)$", description="Type of CSV export")


class ReportResponse(BaseModel):
    """Metadata response for an exported report artifact."""
    id: int
    investigation_id: int
    format: str
    filename: str
    file_size: int
    created_at: Optional[str]
    parameters: Dict[str, Any]

