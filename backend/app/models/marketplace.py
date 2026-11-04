"""Marketplace model representing darknet platforms, forums, or leak sites."""

from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, Identity, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.threat_actor import ThreatActor


class Marketplace(Base, TimestampMixin):
    """Darknet market or forum platform entity."""

    __tablename__ = "marketplaces"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_fictional: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)

    # Relationships
    threat_actors: Mapped[List["ThreatActor"]] = relationship("ThreatActor", back_populates="marketplace")
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="marketplace")

