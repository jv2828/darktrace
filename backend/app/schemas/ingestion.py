"""Pydantic schemas for data ingestion endpoints."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ManualPostRequest(BaseModel):
    """Payload for manual darknet post entry."""
    marketplace: str = Field(..., min_length=1, max_length=100, description="Name of the dark web marketplace or forum")
    username: Optional[str] = Field(None, min_length=1, max_length=64, description="Author handle or vendor alias")
    author_username: Optional[str] = Field(None, min_length=1, max_length=64, description="Alias for username")
    content: str = Field(..., min_length=1, max_length=20000, description="Original raw communication text")
    timestamp: Optional[str] = Field(None, description="ISO 8601 or YYYY-MM-DD HH:MM:SS timestamp")
    posted_at: Optional[str] = Field(None, description="Alias for timestamp")
    source_reference: Optional[str] = Field(None, max_length=512, description="Thread ID, URL slug, or archive identifier")
    title: Optional[str] = Field(None, max_length=512, description="Optional title")
    thread_id: Optional[str] = Field(None, max_length=512, description="Optional thread id")
    structured_indicators: Optional[Dict[str, Any]] = Field(None, description="Optional structured indicators (PGP, wallet, etc.)")
    raw_indicators: Optional[Dict[str, Any]] = Field(None, description="Alias for structured_indicators")
