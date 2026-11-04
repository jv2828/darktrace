"""Investigation report model managing generated forensic export artifacts."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, Identity, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.investigation import Investigation
    from app.models.user import User


class ReportFormat(str, enum.Enum):
    """File format for exported investigation reports."""
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"


class InvestigationReport(Base):
    """Exported forensic summary report document."""

    __tablename__ = "investigation_reports"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    format: Mapped[ReportFormat] = mapped_column(
        Enum(ReportFormat, name="report_format", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    generated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    parameters: Mapped[Dict[str, Any]] = mapped_column(
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
    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="reports")
    generator: Mapped[Optional["User"]] = relationship("User", back_populates="generated_reports")

