"""Stateless indicator extraction preview API endpoint."""

from fastapi import APIRouter, Depends, status

from app.analysis.extraction import extract_all
from app.api.deps import get_current_user
from app.core.responses import success
from app.models.user import User
from app.schemas.extraction import ExtractionPreviewRequest

router = APIRouter(prefix="/extraction", tags=["Extraction"])


@router.post("/preview", status_code=status.HTTP_200_OK)
def preview_extraction_route(
    payload: ExtractionPreviewRequest,
    current_user: User = Depends(get_current_user),
):
    """Stateless indicator extraction preview on raw text and optional structured fields."""
    result = extract_all(
        content=payload.content,
        structured=payload.structured_indicators,
        debug=True,
    )
    return success(data=result.to_dict())

