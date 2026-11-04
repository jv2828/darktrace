"""Analysis result model storing per-actor or per-post analytical representations."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Identity, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.pipeline_run import PipelineRun
    from app.models.post import Post
    from app.models.threat_actor import ThreatActor


class AnalysisType(str, enum.Enum):
    """Types of analytical representations generated."""
    STYLOMETRY_FEATURES = "stylometry_features"
    BEHAVIOUR_PROFILE = "behaviour_profile"
    TFIDF_SUMMARY = "tfidf_summary"
    OTHER = "other"


class AnalysisResult(Base):
    """Feature vectors, stylistic signatures, or behavioral profiles from pipeline stages."""

    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    pipeline_run_id: Mapped[int] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("threat_actors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    post_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_type: Mapped[AnalysisType] = mapped_column(
        Enum(AnalysisType, name="analysis_type", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    result: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    pipeline_run: Mapped["PipelineRun"] = relationship("PipelineRun", back_populates="analysis_results")
    actor: Mapped[Optional["ThreatActor"]] = relationship("ThreatActor", back_populates="analysis_results")
    post: Mapped[Optional["Post"]] = relationship("Post", back_populates="analysis_results")

