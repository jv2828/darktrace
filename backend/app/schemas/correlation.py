"""Pydantic schemas for multi-dimensional correlation results and analysis."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActorSummary(BaseModel):
    """Concise actor identity summary."""
    id: int
    username: str
    marketplace: str


class CorrelationItemResponse(BaseModel):
    """ListItem for stored correlation result."""
    id: int
    pipeline_run_id: int
    actors: Dict[str, ActorSummary]
    combined_score: float
    level: str
    coverage: float
    dimension_scores: Dict[str, Any]
    contradiction_count: int


class CorrelationDetailResponse(BaseModel):
    """Full detail of a correlation result between an actor pair."""
    id: int
    pipeline_run_id: int
    actors: Dict[str, ActorSummary]
    combined_score: float
    level: str
    coverage: float
    dimension_scores: Dict[str, Any]
    contributions: Dict[str, Any]
    missing_dimensions: List[Dict[str, Any]]
    contradictions: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]


class ActorAnalysisResponse(BaseModel):
    """Analytical writeprints and behavioral profile for an actor."""
    actor_id: int
    username: str
    marketplace: str
    stylometry: Dict[str, Any]
    tfidf_summary: List[Dict[str, Any]]
    behaviour: Dict[str, Any]


class StylometrySampleInput(BaseModel):
    """Single sample text for comparison."""
    label: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=20000)


class StylometryCompareRequest(BaseModel):
    """Request payload for stateless stylometry comparison."""
    samples: List[StylometrySampleInput] = Field(..., min_length=2, max_length=5)


class StylometryCompareResponse(BaseModel):
    """Stateless comparison findings and caveats."""
    samples: List[Dict[str, Any]]
    pairwise_similarities: List[Dict[str, Any]]
    caveats: List[str]

