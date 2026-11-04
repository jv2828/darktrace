"""Scoring configuration model governing heuristic threat weights and thresholds."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.correlation_result import CorrelationResult
    from app.models.pipeline_run import PipelineRun
    from app.models.user import User


class ScoringConfig(Base, TimestampMixin):
    """Scoring parameters for heuristic actor correlation."""

    __tablename__ = "scoring_configs"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_scoring_configs_name_version"),
        Index(
            "uq_scoring_configs_is_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    weights: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    thresholds: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User", back_populates="created_scoring_configs")
    pipeline_runs: Mapped[List["PipelineRun"]] = relationship("PipelineRun", back_populates="scoring_config")
    correlation_results: Mapped[List["CorrelationResult"]] = relationship("CorrelationResult", back_populates="scoring_config")

