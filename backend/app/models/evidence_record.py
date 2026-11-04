"""Evidence record model capturing atomic heuristic correlations between threat actors."""

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evidence_source import EvidenceSource
    from app.models.pipeline_run import PipelineRun
    from app.models.threat_actor import ThreatActor


class EvidenceDimension(str, enum.Enum):
    """Correlation feature dimensions."""
    CRYPTOGRAPHIC = "cryptographic"
    BEHAVIOURAL = "behavioural"
    STYLOMETRIC = "stylometric"
    INFRASTRUCTURE = "infrastructure"


class EvidenceDirection(str, enum.Enum):
    """Direction of evidentiary support."""
    SUPPORTING = "supporting"
    CONTRADICTING = "contradicting"


class EvidenceRecord(Base):
    """Atomic analytical finding linking or distinguishing two actors."""

    __tablename__ = "evidence_records"
    __table_args__ = (
        CheckConstraint("actor_a_id < actor_b_id", name="ck_evidence_records_actor_pair_order"),
        CheckConstraint("strength >= 0 AND strength <= 1", name="ck_evidence_records_strength_range"),
        Index("ix_evidence_records_run_actors", "pipeline_run_id", "actor_a_id", "actor_b_id"),
        Index("ix_evidence_records_run_dimension", "pipeline_run_id", "dimension"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_a_id: Mapped[int] = mapped_column(
        ForeignKey("threat_actors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_b_id: Mapped[int] = mapped_column(
        ForeignKey("threat_actors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dimension: Mapped[EvidenceDimension] = mapped_column(
        Enum(EvidenceDimension, name="evidence_dimension", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    direction: Mapped[EvidenceDirection] = mapped_column(
        Enum(EvidenceDirection, name="evidence_direction", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    strength: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="evidence_records")
    actor_a: Mapped["ThreatActor"] = relationship(
        "ThreatActor",
        foreign_keys=[actor_a_id],
        back_populates="evidence_as_actor_a",
    )
    actor_b: Mapped["ThreatActor"] = relationship(
        "ThreatActor",
        foreign_keys=[actor_b_id],
        back_populates="evidence_as_actor_b",
    )
    sources: Mapped[List["EvidenceSource"]] = relationship(
        "EvidenceSource",
        back_populates="evidence",
        cascade="all, delete-orphan",
    )

