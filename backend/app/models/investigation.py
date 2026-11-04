"""Investigation model representing an investigative case workspace."""

import enum
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Enum, ForeignKey, Identity, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.investigation_dataset import InvestigationDataset
    from app.models.investigation_report import InvestigationReport
    from app.models.pipeline_run import PipelineRun
    from app.models.user import User


class InvestigationStatus(str, enum.Enum):
    """Investigation lifecycle statuses."""
    DRAFT = "draft"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Investigation(Base, TimestampMixin):
    """Investigation case container."""

    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[InvestigationStatus] = mapped_column(
        Enum(InvestigationStatus, name="investigation_status", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        default=InvestigationStatus.DRAFT,
        nullable=False,
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", back_populates="created_investigations")
    dataset_associations: Mapped[List["InvestigationDataset"]] = relationship(
        "InvestigationDataset",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    pipeline_runs: Mapped[List["PipelineRun"]] = relationship(
        "PipelineRun",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )
    reports: Mapped[List["InvestigationReport"]] = relationship(
        "InvestigationReport",
        back_populates="investigation",
        cascade="all, delete-orphan",
    )

