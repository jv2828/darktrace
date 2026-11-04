"""Pipeline run execution record for investigation analytics."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Identity, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.analysis_result import AnalysisResult
    from app.models.correlation_result import CorrelationResult
    from app.models.evidence_record import EvidenceRecord
    from app.models.investigation import Investigation
    from app.models.pipeline_stage_run import PipelineStageRun
    from app.models.scoring_config import ScoringConfig
    from app.models.user import User


class PipelineRunStatus(str, enum.Enum):
    """Pipeline execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineRun(Base):
    """Execution run instance executing an investigation analysis pipeline."""

    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index(
            "uq_pipeline_runs_active_investigation",
            "investigation_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scoring_config_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("scoring_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        Enum(PipelineRunStatus, name="pipeline_run_status", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        default=PipelineRunStatus.QUEUED,
        nullable=False,
    )
    triggered_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="pipeline_runs")
    scoring_config: Mapped[Optional["ScoringConfig"]] = relationship("ScoringConfig", back_populates="pipeline_runs")
    triggered_by_user: Mapped[Optional["User"]] = relationship("User", back_populates="pipeline_runs")
    stage_runs: Mapped[List["PipelineStageRun"]] = relationship(
        "PipelineStageRun",
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )
    evidence_records: Mapped[List["EvidenceRecord"]] = relationship(
        "EvidenceRecord",
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )
    correlation_results: Mapped[List["CorrelationResult"]] = relationship(
        "CorrelationResult",
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )
    analysis_results: Mapped[List["AnalysisResult"]] = relationship(
        "AnalysisResult",
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )

