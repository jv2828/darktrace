"""Pipeline stage execution record for discrete analytical passes."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.pipeline_run import PipelineRun


class PipelineStage(str, enum.Enum):
    """Analytical pipeline stages."""
    CRYPTO_MATCHING = "crypto_matching"
    INFRASTRUCTURE_MATCHING = "infrastructure_matching"
    BEHAVIOURAL_ANALYSIS = "behavioural_analysis"
    STYLOMETRIC_ANALYSIS = "stylometric_analysis"
    SCORING = "scoring"


class PipelineStageStatus(str, enum.Enum):
    """Status of an individual pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStageRun(Base):
    """Execution status and metrics for an individual analytical stage."""

    __tablename__ = "pipeline_stage_runs"
    __table_args__ = (
        UniqueConstraint("pipeline_run_id", "stage", name="uq_pipeline_stage_runs_run_id_stage"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[PipelineStage] = mapped_column(
        Enum(PipelineStage, name="pipeline_stage", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    status: Mapped[PipelineStageStatus] = mapped_column(
        Enum(PipelineStageStatus, name="pipeline_stage_status", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        default=PipelineStageStatus.PENDING,
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    items_processed: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    summary: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="stage_runs")

