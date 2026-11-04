"""Evidence source traceability model linking findings back to ground-truth posts or indicators."""

from typing import TYPE_CHECKING, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Identity
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.evidence_record import EvidenceRecord
    from app.models.extracted_indicator import ExtractedIndicator
    from app.models.post import Post


class EvidenceSource(Base):
    """Provenance pointer tying an evidence finding directly to source posts or indicators."""

    __tablename__ = "evidence_sources"
    __table_args__ = (
        CheckConstraint(
            "post_id IS NOT NULL OR indicator_id IS NOT NULL",
            name="ck_evidence_sources_has_origin",
        ),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    evidence_id: Mapped[int] = mapped_column(
        ForeignKey("evidence_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    indicator_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("extracted_indicators.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    evidence: Mapped["EvidenceRecord"] = relationship("EvidenceRecord", back_populates="sources")
    post: Mapped[Optional["Post"]] = relationship("Post", back_populates="evidence_sources")
    indicator: Mapped[Optional["ExtractedIndicator"]] = relationship("ExtractedIndicator", back_populates="evidence_sources")

