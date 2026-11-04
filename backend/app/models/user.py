"""User model representing system accounts and investigators."""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, Enum, Identity, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.dataset import Dataset
    from app.models.investigation import Investigation
    from app.models.investigation_report import InvestigationReport
    from app.models.pipeline_run import PipelineRun
    from app.models.post import Post
    from app.models.scoring_config import ScoringConfig


class UserRole(str, enum.Enum):
    """Roles for role-based access control."""
    ADMIN = "admin"
    INVESTIGATOR = "investigator"


class User(Base, TimestampMixin):
    """User account entity."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    created_datasets: Mapped[List["Dataset"]] = relationship("Dataset", back_populates="creator")
    created_investigations: Mapped[List["Investigation"]] = relationship("Investigation", back_populates="creator")
    created_scoring_configs: Mapped[List["ScoringConfig"]] = relationship("ScoringConfig", back_populates="creator")
    pipeline_runs: Mapped[List["PipelineRun"]] = relationship("PipelineRun", back_populates="triggered_by_user")
    ingested_posts: Mapped[List["Post"]] = relationship("Post", back_populates="ingested_by_user")
    generated_reports: Mapped[List["InvestigationReport"]] = relationship("InvestigationReport", back_populates="generator")

