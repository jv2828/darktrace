"""Dataset model representing curated or synthetic threat-intelligence collections."""

import enum
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, Enum, ForeignKey, Identity, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.investigation_dataset import InvestigationDataset
    from app.models.post import Post
    from app.models.user import User


class DatasetSourceType(str, enum.Enum):
    """Source provenance for intelligence datasets."""
    SAMPLE = "sample"
    MANUAL = "manual"
    CSV = "csv"
    JSON = "json"


class Dataset(Base, TimestampMixin):
    """Dataset entity grouping ingested dark web records."""

    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[DatasetSourceType] = mapped_column(
        Enum(DatasetSourceType, name="dataset_source_type", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    is_fictional: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    creator: Mapped[Optional["User"]] = relationship("User", back_populates="created_datasets")
    investigation_associations: Mapped[List["InvestigationDataset"]] = relationship(
        "InvestigationDataset",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="dataset", cascade="all, delete-orphan")

