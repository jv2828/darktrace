"""Pydantic schemas for request validation and response serialization."""

from app.schemas.auth import ChangePasswordRequest, LoginRequest
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    DashboardTotals,
    RecentCorrelationItem,
    RecentInvestigationItem,
)
from app.schemas.ingestion import ManualPostRequest
from app.schemas.investigation import (
    InvestigationCounts,
    InvestigationCreateRequest,
    InvestigationCreatorSummary,
    InvestigationResponse,
)
from app.schemas.user import (
    UserCreateRequest,
    UserResetPasswordRequest,
    UserResponse,
    UserUpdateRequest,
)

__all__ = [
    "LoginRequest",
    "ChangePasswordRequest",
    "UserCreateRequest",
    "UserUpdateRequest",
    "UserResetPasswordRequest",
    "UserResponse",
    "InvestigationCreateRequest",
    "InvestigationResponse",
    "InvestigationCounts",
    "InvestigationCreatorSummary",
    "DashboardSummaryResponse",
    "DashboardTotals",
    "RecentInvestigationItem",
    "RecentCorrelationItem",
]
