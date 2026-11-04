"""Business logic and database queries for Investigations."""

import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIException
from app.models.extracted_indicator import ExtractedIndicator
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_dataset import InvestigationDataset
from app.models.post import Post
from app.models.user import User, UserRole
from app.schemas.investigation import InvestigationCreateRequest


def get_investigation_counts(db: Session, investigation_ids: List[int]) -> Dict[int, Dict[str, int]]:
    """Compute distinct posts and indicators counts linked to investigations via datasets."""
    if not investigation_ids:
        return {}

    # Query distinct post counts
    post_stmt = (
        select(InvestigationDataset.investigation_id, func.count(distinct(Post.id)))
        .join(Post, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id.in_(investigation_ids))
        .group_by(InvestigationDataset.investigation_id)
    )
    post_counts = {row[0]: row[1] for row in db.execute(post_stmt).all()}

    # Query distinct indicator counts
    indicator_stmt = (
        select(InvestigationDataset.investigation_id, func.count(distinct(ExtractedIndicator.id)))
        .join(Post, Post.dataset_id == InvestigationDataset.dataset_id)
        .join(ExtractedIndicator, ExtractedIndicator.post_id == Post.id)
        .where(InvestigationDataset.investigation_id.in_(investigation_ids))
        .group_by(InvestigationDataset.investigation_id)
    )
    indicator_counts = {row[0]: row[1] for row in db.execute(indicator_stmt).all()}

    return {
        inv_id: {
            "posts": post_counts.get(inv_id, 0),
            "indicators": indicator_counts.get(inv_id, 0),
        }
        for inv_id in investigation_ids
    }


def serialize_investigation(
    investigation: Investigation,
    counts: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    """Serialize an Investigation entity with creator info and counts."""
    status_val = (
        investigation.status.value
        if hasattr(investigation.status, "value")
        else str(investigation.status)
    )
    creator = investigation.creator
    creator_id = creator.id if creator else investigation.created_by
    creator_username = creator.username if creator else f"user_{investigation.created_by}"

    effective_counts = counts or {"posts": 0, "indicators": 0}

    return {
        "id": investigation.id,
        "title": investigation.title,
        "description": investigation.description,
        "status": status_val,
        "created_at": investigation.created_at.isoformat() if investigation.created_at else None,
        "updated_at": investigation.updated_at.isoformat() if investigation.updated_at else None,
        "created_by": {
            "id": creator_id,
            "username": creator_username,
        },
        "counts": {
            "posts": effective_counts.get("posts", 0),
            "indicators": effective_counts.get("indicators", 0),
        },
    }


def create_investigation(
    db: Session,
    user: User,
    payload: InvestigationCreateRequest,
) -> Dict[str, Any]:
    """Create a new investigation in draft status owned by current user."""
    investigation = Investigation(
        title=payload.title,
        description=payload.description,
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db.add(investigation)
    db.commit()
    db.refresh(investigation)

    # Attach current user as creator for serialization
    investigation.creator = user
    return serialize_investigation(investigation, counts={"posts": 0, "indicators": 0})


def get_investigation_by_id(
    db: Session,
    user: User,
    investigation_id: int,
) -> Dict[str, Any]:
    """Retrieve an investigation by ID, enforcing ownership scoping (404 on unowned)."""
    stmt = (
        select(Investigation)
        .options(joinedload(Investigation.creator))
        .where(Investigation.id == investigation_id)
    )
    investigation = db.execute(stmt).scalar_one_or_none()

    if not investigation:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Investigation not found.",
        )

    # Ownership enforcement: Investigators can only view their own investigations;
    # access to other investigations returns 404 NOT_FOUND to prevent enumeration.
    if user.role != UserRole.ADMIN and investigation.created_by != user.id:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Investigation not found.",
        )

    counts_map = get_investigation_counts(db, [investigation.id])
    counts = counts_map.get(investigation.id, {"posts": 0, "indicators": 0})
    return serialize_investigation(investigation, counts=counts)


def list_investigations(
    db: Session,
    user: User,
    page: int = 1,
    page_size: int = 10,
    q: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """List paginated investigations with search, filter, and ownership scoping."""
    base_conditions = []

    # Ownership filter: non-admins only see their own investigations
    if user.role != UserRole.ADMIN:
        base_conditions.append(Investigation.created_by == user.id)

    # Text search in title
    if q and q.strip():
        base_conditions.append(Investigation.title.ilike(f"%{q.strip()}%"))

    # Status filter
    if status_filter and status_filter.strip():
        clean_status = status_filter.strip().lower()
        matching_status = next(
            (s for s in InvestigationStatus if s.value == clean_status),
            None,
        )
        if matching_status:
            base_conditions.append(Investigation.status == matching_status)
        else:
            # If invalid status requested, return 0 results
            base_conditions.append(Investigation.id == -1)

    # Total matching records count
    count_stmt = select(func.count(Investigation.id)).where(*base_conditions)
    total = db.execute(count_stmt).scalar() or 0

    total_pages = math.ceil(total / page_size) if page_size > 0 else 0
    offset = (page - 1) * page_size

    # Fetch paginated items ordered newest first
    stmt = (
        select(Investigation)
        .options(joinedload(Investigation.creator))
        .where(*base_conditions)
        .order_by(Investigation.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    investigations = list(db.execute(stmt).scalars().all())

    # Fetch counts in batch for returned investigations
    inv_ids = [inv.id for inv in investigations]
    counts_map = get_investigation_counts(db, inv_ids)

    items = [
        serialize_investigation(inv, counts=counts_map.get(inv.id, {"posts": 0, "indicators": 0}))
        for inv in investigations
    ]

    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    return items, meta

