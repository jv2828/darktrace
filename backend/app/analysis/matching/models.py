"""Data structures for pure-Python threat actor matching engine."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class IndicatorRecord:
    """Input record representing an extracted indicator tied to a post and threat actor."""

    indicator_id: int
    post_id: int
    actor_id: int
    marketplace_id: int
    indicator_type: str
    normalised_value: str
    confidence: str
    posted_at: Optional[datetime] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceCandidate:
    """Pairwise correlation finding produced by matching algorithms."""

    actor_a_id: int
    actor_b_id: int
    dimension: str
    evidence_type: str
    direction: str
    strength: float
    explanation: str
    details: Dict[str, Any]
    source_post_ids: List[int]
    source_indicator_ids: List[int]

    def __post_init__(self) -> None:
        """Enforce canonical actor order actor_a_id < actor_b_id."""
        if self.actor_a_id >= self.actor_b_id:
            raise ValueError(
                f"actor_a_id ({self.actor_a_id}) must be strictly less than actor_b_id ({self.actor_b_id})"
            )
        self.strength = round(max(0.0, min(1.0, float(self.strength))), 4)


@dataclass
class SuppressedIndicator:
    """Indicator suppressed from generating pairwise evidence due to high prevalence (commonality)."""

    type: str
    normalised_value: str
    actor_count: int
    marketplace_count: int

    @property
    def indicator_type(self) -> str:
        """Alias for type compatibility."""
        return self.type

