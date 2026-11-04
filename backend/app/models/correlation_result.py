"""Correlation result model capturing aggregate heuristic affinity between actors."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.pipeline_run import PipelineRun
    from app.models.scoring_config import ScoringConfig
    from app.models.threat_actor import ThreatActor


class CorrelationResult(Base):
    """Aggregate heuristic correlation between a pair of threat actors."""

    __tablename__ = "correlation_results"
    __table_args__ = (
        UniqueConstraint(
            "pipeline_run_id",
            "actor_a_id",
            "actor_b_id",
            name="uq_correlation_results_run_actors",
        ),
        CheckConstraint("actor_a_id < actor_b_id", name="ck_correlation_results_actor_pair_order"),
        CheckConstraint("combined_score >= 0 AND combined_score <= 1", name="ck_correlation_results_score_range"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_a_id: Mapped[int] = mapped_column(
        ForeignKey("threat_actors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_b_id: Mapped[int] = mapped_column(
        ForeignKey("threat_actors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    combined_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        comment="Heuristic evidence score. NOT a verified probability of common identity.",
    )
    dimension_scores: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    contributions: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    missing_dimensions: Mapped[List[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    contradictions: Mapped[List[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=text("'[]'::jsonb"),
        nullable=False,
    )
    scoring_config_id: Mapped[int] = mapped_column(
        ForeignKey("scoring_configs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="correlation_results")
    actor_a: Mapped["ThreatActor"] = relationship(
        "ThreatActor",
        foreign_keys=[actor_a_id],
        back_populates="correlations_as_actor_a",
    )
    actor_b: Mapped["ThreatActor"] = relationship(
        "ThreatActor",
        foreign_keys=[actor_b_id],
        back_populates="correlations_as_actor_b",
    )
    scoring_config: Mapped["ScoringConfig"] = relationship("ScoringConfig", back_populates="correlation_results")

