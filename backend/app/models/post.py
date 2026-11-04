"""Post model representing darknet messages, listings, or forum posts."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.analysis_result import AnalysisResult
    from app.models.dataset import Dataset
    from app.models.evidence_source import EvidenceSource
    from app.models.extracted_indicator import ExtractedIndicator
    from app.models.marketplace import Marketplace
    from app.models.threat_actor import ThreatActor
    from app.models.user import User


class Post(Base):
    """Immutable post, listing, or forum communication."""

    __tablename__ = "posts"
    __table_args__ = (
        UniqueConstraint("dataset_id", "dedupe_hash", name="uq_posts_dataset_id_dedupe_hash"),
        Index("ix_posts_actor_id", "actor_id"),
        Index("ix_posts_marketplace_id", "marketplace_id"),
        Index("ix_posts_posted_at", "posted_at"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    marketplace_id: Mapped[int] = mapped_column(
        ForeignKey("marketplaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("threat_actors.id", ondelete="RESTRICT"),
        nullable=True,
    )
    author_username: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    dedupe_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_reference: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    raw_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    ingested_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="posts")
    marketplace: Mapped["Marketplace"] = relationship("Marketplace", back_populates="posts")
    actor: Mapped[Optional["ThreatActor"]] = relationship("ThreatActor", back_populates="posts")
    indicators: Mapped[List["ExtractedIndicator"]] = relationship(
        "ExtractedIndicator",
        back_populates="post",
        cascade="all, delete-orphan",
    )
    evidence_sources: Mapped[List["EvidenceSource"]] = relationship("EvidenceSource", back_populates="post")
    analysis_results: Mapped[List["AnalysisResult"]] = relationship("AnalysisResult", back_populates="post")
    ingested_by_user: Mapped[Optional["User"]] = relationship("User", back_populates="ingested_posts")

