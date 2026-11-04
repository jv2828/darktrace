"""API endpoints for scoring configuration."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.responses import success
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.scoring_config import ScoringConfigResponse, ScoringConfigUpdateRequest
from app.services.scoring_config_service import get_or_create_default, update_active_config

router = APIRouter(prefix="/scoring-configs", tags=["Scoring Configs"])


@router.get("/active")
def get_active_scoring_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the currently active scoring configuration."""
    cfg = get_or_create_default(db)
    payload = ScoringConfigResponse.model_validate(cfg).model_dump(mode="json")
    return success(data=payload)


@router.put("/active")
def update_active_scoring_config(
    payload: ScoringConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Atomically upgrade active scoring configuration parameters (Admin only)."""
    cfg = update_active_config(
        db=db,
        weights=payload.weights,
        thresholds=payload.thresholds,
        user_id=current_user.id,
    )
    result = ScoringConfigResponse.model_validate(cfg).model_dump(mode="json")
    return success(data=result)
