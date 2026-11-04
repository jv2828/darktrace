"""Threat actor entity model representing an identity handle on a marketplace."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Identity, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.actor_alias import ActorAlias
    from app.models.analysis_result import AnalysisResult
    from app.models.correlation_result import CorrelationResult
    from app.models.evidence_record import EvidenceRecord
    from app.models.marketplace import Marketplace
    from app.models.post import Post


class ThreatActor(Base, TimestampMixin):
    """Threat actor identity tracked across illicit platforms."""

    __tablename__ = "threat_actors"
    __table_args__ = (
        UniqueConstraint("marketplace_id", "normalised_username", name="uq_threat_actors_marketplace_id_normalised_username"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    marketplace_id: Mapped[int] = mapped_column(
        ForeignKey("marketplaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    normalised_username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    marketplace: Mapped["Marketplace"] = relationship("Marketplace", back_populates="threat_actors")
    aliases: Mapped[List["ActorAlias"]] = relationship("ActorAlias", back_populates="actor", cascade="all, delete-orphan")
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="actor")
    evidence_as_actor_a: Mapped[List["EvidenceRecord"]] = relationship(
        "EvidenceRecord",
        foreign_keys="EvidenceRecord.actor_a_id",
        back_populates="actor_a",
    )
    evidence_as_actor_b: Mapped[List["EvidenceRecord"]] = relationship(
        "EvidenceRecord",
        foreign_keys="EvidenceRecord.actor_b_id",
        back_populates="actor_b",
    )
    correlations_as_actor_a: Mapped[List["CorrelationResult"]] = relationship(
        "CorrelationResult",
        foreign_keys="CorrelationResult.actor_a_id",
        back_populates="actor_a",
    )
    correlations_as_actor_b: Mapped[List["CorrelationResult"]] = relationship(
        "CorrelationResult",
        foreign_keys="CorrelationResult.actor_b_id",
        back_populates="actor_b",
    )
    analysis_results: Mapped[List["AnalysisResult"]] = relationship("AnalysisResult", back_populates="actor")

