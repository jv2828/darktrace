"""API endpoints for managing threat intelligence investigations."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import success
from app.db.session import get_db
from app.models.user import User
from app.schemas.ingestion import ManualPostRequest
from app.schemas.investigation import InvestigationCreateRequest
from app.services.ingestion_service import (
    commit_file_upload,
    commit_manual_post,
    list_investigation_datasets,
    list_investigation_posts,
    load_sample_to_investigation,
    preview_file_upload,
    preview_manual_post,
)
from app.services.investigation_service import (
    create_investigation,
    get_investigation_by_id,
    list_investigations,
)

router = APIRouter(prefix="/investigations", tags=["Investigations"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_new_investigation(
    payload: InvestigationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new investigation in draft status owned by current user."""
    data = create_investigation(db=db, user=current_user, payload=payload)
    return success(data=data)


@router.get("", status_code=status.HTTP_200_OK)
def get_investigations_list(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Title search keyword"),
    status: Optional[str] = Query(None, description="Filter by status (draft, processing, completed, failed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List paginated investigations with search, filter, and ownership scoping."""
    items, meta = list_investigations(
        db=db,
        user=current_user,
        page=page,
        page_size=page_size,
        q=q,
        status_filter=status,
    )
    return success(data=items, meta=meta)


@router.get("/{investigation_id}", status_code=status.HTTP_200_OK)
def get_investigation_details(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details for a single investigation scoped by ownership (404 on unowned)."""
    data = get_investigation_by_id(db=db, user=current_user, investigation_id=investigation_id)
    return success(data=data)


# ---------------------------------------------------------------------------
# Ingestion Endpoints (Phase 5)
# ---------------------------------------------------------------------------

@router.post("/{investigation_id}/datasets/samples/{key}", status_code=status.HTTP_200_OK)
def load_sample_dataset_route(
    investigation_id: int,
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load a synthetic benchmark sample into the DB and link to the investigation."""
    data = load_sample_to_investigation(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        sample_key=key,
    )
    return success(data=data)


@router.post("/{investigation_id}/ingest/manual/preview", status_code=status.HTTP_200_OK)
def preview_manual_post_route(
    investigation_id: int,
    payload: ManualPostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate a single manual darknet post entry without writing to DB."""
    data = preview_manual_post(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        payload=payload.model_dump(),
    )
    return success(data=data)


@router.post("/{investigation_id}/ingest/manual/commit", status_code=status.HTTP_201_CREATED)
def commit_manual_post_route(
    investigation_id: int,
    payload: ManualPostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit a validated manual darknet post into a new manual dataset."""
    data = commit_manual_post(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        payload=payload.model_dump(),
    )
    return success(data=data)


@router.post("/{investigation_id}/ingest/file/preview", status_code=status.HTTP_200_OK)
async def preview_file_upload_route(
    investigation_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate uploaded CSV or JSON file in memory without persisting records."""
    data = await preview_file_upload(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        file=file,
    )
    return success(data=data)


@router.post("/{investigation_id}/ingest/file/commit", status_code=status.HTTP_201_CREATED)
async def commit_file_upload_route(
    investigation_id: int,
    file: UploadFile = File(...),
    on_error: str = Form("skip_invalid"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit validated CSV or JSON records into a new dataset atomically."""
    data = await commit_file_upload(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        file=file,
        on_error=on_error,
    )
    return success(data=data)


@router.get("/{investigation_id}/posts", status_code=status.HTTP_200_OK)
def get_investigation_posts_route(
    investigation_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    marketplace: Optional[str] = Query(None, description="Filter by marketplace"),
    username: Optional[str] = Query(None, description="Filter by author username"),
    q: Optional[str] = Query(None, description="Search post content keyword"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List paginated posts belonging to this investigation with filtering."""
    items, meta = list_investigation_posts(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        page=page,
        page_size=page_size,
        marketplace=marketplace,
        username=username,
        q=q,
        start_date=start_date,
        end_date=end_date,
    )
    return success(data=items, meta=meta)


@router.get("/{investigation_id}/datasets", status_code=status.HTTP_200_OK)
def get_investigation_datasets_route(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List datasets attached to this investigation with real post counts."""
    items = list_investigation_datasets(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
    )
    return success(data=items)

