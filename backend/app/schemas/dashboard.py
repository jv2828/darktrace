"""Pydantic schemas for the Dashboard overview endpoints."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DashboardTotals(BaseModel):
    """Aggregate metric counters scoped to user visibility."""
    investigations: int = 0
    posts: int = 0
    datasets: int = 0
    marketplaces: int = 0
    indicators: int = 0
    potential_linkages: int = 0


class RecentInvestigationItem(BaseModel):
    """Brief summary of a recent investigation."""
    id: int
    title: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecentCorrelationItem(BaseModel):
    """Summary of a recent pipeline run and correlation activity."""
    id: int
    investigation_id: int
    investigation_title: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DashboardSummaryResponse(BaseModel):
    """Dashboard overview payload."""
    totals: DashboardTotals
    recent_investigations: List[RecentInvestigationItem]
    recent_correlation_activity: List[RecentCorrelationItem]

