"""API endpoints for stateless stylometric writeprint comparisons."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.responses import success
from app.models.user import User
from app.schemas.correlation import StylometryCompareRequest
from app.services.correlation_service import stateless_stylometry_compare

router = APIRouter(prefix="/stylometry", tags=["Stylometry"])


@router.post("/compare")
def compare_stylometry_samples(
    payload: StylometryCompareRequest,
    current_user: User = Depends(get_current_user),
):
    """Perform stateless writeprint and TF-IDF comparison across 2-5 text samples."""
    samples = [{"label": s.label, "text": s.text} for s in payload.samples]
    result = stateless_stylometry_compare(samples)
    return success(data=result)

