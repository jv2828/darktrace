"""API endpoint for high-level dashboard metrics and recent activity."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import success
from app.db.session import get_db
from app.models.user import User
from app.services.dashboard_service import get_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", status_code=status.HTTP_200_OK)
def get_dashboard_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve aggregate counts and recent activity scoped to user's investigations."""
    data = get_dashboard_summary(db=db, user=current_user)
    return success(data=data)

