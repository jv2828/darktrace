"""Actor alias model for secondary or cross-platform handles linked to a threat actor."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, Identity, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.threat_actor import ThreatActor


class ActorAlias(Base):
    """Known alias or moniker attributed to an actor."""

    __tablename__ = "actor_aliases"
    __table_args__ = (
        UniqueConstraint("actor_id", "normalised_alias", name="uq_actor_aliases_actor_id_normalised_alias"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("threat_actors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    normalised_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    source_post_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    actor: Mapped["ThreatActor"] = relationship("ThreatActor", back_populates="aliases")
    source_post: Mapped[Optional["Post"]] = relationship("Post")

