"""Database service for post indicator extraction, querying, and rerun pipelines."""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.analysis.extraction import EXTRACTOR_VERSION, extract_all
from app.core.exceptions import APIException
from app.models.dataset import Dataset
from app.models.evidence_source import EvidenceSource
from app.models.extracted_indicator import ExtractedIndicator, ExtractionMethod, IndicatorType
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.post import Post
from app.models.user import User, UserRole


def get_investigation_or_404(db: Session, user: User, investigation_id: int) -> Investigation:
    """Retrieve investigation ensuring user authorization under ownership scoping."""
    inv = db.get(Investigation, investigation_id)
    if not inv:
        raise APIException(status_code=404, code="NOT_FOUND", message="Investigation not found.")
    if user.role != UserRole.ADMIN and inv.created_by != user.id:
        raise APIException(status_code=404, code="NOT_FOUND", message="Investigation not found.")
    return inv


def extract_post(db: Session, post: Post) -> int:
    """Extract and persist technical indicators for a post within the caller's transaction."""
    structured_data = post.raw_metadata.get("structured_indicators") if post.raw_metadata else None
    res = extract_all(post.content, structured=structured_data)

    # Update post extraction metadata
    post.extractor_version = EXTRACTOR_VERSION
    post.extracted_at = datetime.now(timezone.utc)
    db.flush()

    # Clear existing indicators for this post if any
    existing = db.execute(
        select(ExtractedIndicator).where(ExtractedIndicator.post_id == post.id)
    ).scalars().all()
    for e in existing:
        db.delete(e)
    if existing:
        db.flush()

    new_indicators: List[ExtractedIndicator] = []
    for item in res.indicators:
        ind_type_val = IndicatorType(item.indicator_type)
        ext_method_val = ExtractionMethod(item.extraction_method)

        ind_obj = ExtractedIndicator(
            post_id=post.id,
            indicator_type=ind_type_val,
            raw_value=item.raw_value,
            normalised_value=item.normalised_value,
            span_start=item.span_start,
            span_end=item.span_end,
            extraction_method=ext_method_val,
            extractor_version=EXTRACTOR_VERSION,
            is_valid_format=item.is_valid_format,
            confidence=item.confidence,
            details=item.details,
        )
        new_indicators.append(ind_obj)

    if new_indicators:
        db.add_all(new_indicators)
        db.flush()

    return len(new_indicators)


def rerun_investigation_extraction(
    db: Session,
    user: User,
    investigation_id: int,
    force: bool = False,
) -> Dict[str, int]:
    """Re-run indicator extraction across all posts attached to the investigation."""
    get_investigation_or_404(db, user, investigation_id)

    # Fetch all posts in datasets attached to this investigation
    stmt = (
        select(Post)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id == investigation_id)
    )
    posts = db.execute(stmt).scalars().all()

    posts_to_process = []
    posts_skipped = 0

    for p in posts:
        if force or p.extractor_version is None or p.extractor_version != EXTRACTOR_VERSION:
            posts_to_process.append(p)
        else:
            posts_skipped += 1

    if not posts_to_process:
        return {
            "posts_processed": 0,
            "posts_skipped": posts_skipped,
            "indicators_created": 0,
            "indicators_removed": 0,
        }

    post_ids = [p.id for p in posts_to_process]

    # Check if any indicators to be replaced are referenced by evidence_sources
    existing_inds = db.execute(
        select(ExtractedIndicator.id).where(ExtractedIndicator.post_id.in_(post_ids))
    ).scalars().all()

    if existing_inds:
        evidence_count = db.execute(
            select(func.count(EvidenceSource.id)).where(EvidenceSource.indicator_id.in_(existing_inds))
        ).scalar() or 0
        if evidence_count > 0:
            raise APIException(
                status_code=409,
                code="EVIDENCE_EXISTS",
                message=f"Cannot re-extract indicators: {evidence_count} existing indicator(s) are bound to evidence sources.",
            )

    indicators_removed = len(existing_inds)
    indicators_created = 0

    for p in posts_to_process:
        created = extract_post(db, p)
        indicators_created += created

    db.commit()

    return {
        "posts_processed": len(posts_to_process),
        "posts_skipped": posts_skipped,
        "indicators_created": indicators_created,
        "indicators_removed": indicators_removed,
    }


def list_investigation_indicators(
    db: Session,
    user: User,
    investigation_id: int,
    indicator_type: Optional[str] = None,
    q: Optional[str] = None,
    post_id: Optional[int] = None,
    marketplace: Optional[str] = None,
    username: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """List paginated indicators for an investigation with rich filtering."""
    get_investigation_or_404(db, user, investigation_id)

    base_conditions = [InvestigationDataset.investigation_id == investigation_id]

    if indicator_type:
        base_conditions.append(ExtractedIndicator.indicator_type == indicator_type)
    if q:
        base_conditions.append(ExtractedIndicator.normalised_value.ilike(f"%{q.strip()}%"))
    if post_id:
        base_conditions.append(Post.id == post_id)
    if marketplace:
        base_conditions.append(Marketplace.name.ilike(f"%{marketplace.strip()}%"))
    if username:
        base_conditions.append(Post.author_username.ilike(f"%{username.strip()}%"))

    # Count matching indicators
    count_stmt = (
        select(func.count(distinct(ExtractedIndicator.id)))
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .join(Marketplace, Post.marketplace_id == Marketplace.id)
        .where(*base_conditions)
    )
    total = db.execute(count_stmt).scalar() or 0
    total_pages = math.ceil(total / page_size) if page_size > 0 else 0
    offset = (page - 1) * page_size

    # Fetch items
    stmt = (
        select(ExtractedIndicator)
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .join(Marketplace, Post.marketplace_id == Marketplace.id)
        .options(joinedload(ExtractedIndicator.post).joinedload(Post.marketplace))
        .where(*base_conditions)
        .order_by(ExtractedIndicator.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    indicators = db.execute(stmt).scalars().all()

    items = []
    for ind in indicators:
        p = ind.post
        mkt_name = p.marketplace.name if p and p.marketplace else "Unknown"
        items.append({
            "id": ind.id,
            "indicator_type": ind.indicator_type.value if hasattr(ind.indicator_type, "value") else str(ind.indicator_type),
            "raw_value": ind.raw_value,
            "normalised_value": ind.normalised_value,
            "confidence": ind.confidence,
            "extraction_method": ind.extraction_method.value if hasattr(ind.extraction_method, "value") else str(ind.extraction_method),
            "span_start": ind.span_start,
            "span_end": ind.span_end,
            "details": ind.details,
            "post": {
                "id": p.id if p else None,
                "marketplace": mkt_name,
                "author_username": p.author_username if p else "Unknown",
                "posted_at": p.posted_at.isoformat() if p and p.posted_at else None,
            } if p else None,
        })

    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    return items, meta


def get_indicators_summary(
    db: Session,
    user: User,
    investigation_id: int,
) -> Dict[str, Any]:
    """Compute aggregate counts by indicator type (total and distinct values)."""
    get_investigation_or_404(db, user, investigation_id)

    stmt = (
        select(
            ExtractedIndicator.indicator_type,
            func.count(ExtractedIndicator.id).label("total"),
            func.count(distinct(ExtractedIndicator.normalised_value)).label("distinct_vals"),
        )
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id == investigation_id)
        .group_by(ExtractedIndicator.indicator_type)
    )
    rows = db.execute(stmt).all()

    by_type: Dict[str, Dict[str, int]] = {}
    grand_total = 0
    grand_distinct = 0

    for r in rows:
        t_str = r[0].value if hasattr(r[0], "value") else str(r[0])
        by_type[t_str] = {
            "total": r[1],
            "distinct": r[2],
        }
        grand_total += r[1]
        grand_distinct += r[2]

    return {
        "by_type": by_type,
        "total": grand_total,
        "total_indicators": grand_total,
        "distinct_indicators": grand_distinct,
    }


def get_investigation_post_detail(
    db: Session,
    user: User,
    investigation_id: int,
    post_id: int,
) -> Dict[str, Any]:
    """Retrieve full post details, original content, highlighted spans, and provenance."""
    get_investigation_or_404(db, user, investigation_id)

    # Confirm post is in a dataset attached to this investigation
    stmt = (
        select(Post)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .options(
            joinedload(Post.marketplace),
            joinedload(Post.dataset),
            joinedload(Post.ingested_by_user),
            joinedload(Post.indicators),
        )
        .where(
            InvestigationDataset.investigation_id == investigation_id,
            Post.id == post_id,
        )
    )
    post = db.execute(stmt).scalars().first()
    if not post:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Post not found in this investigation.",
        )

    # Format indicators
    indicators_list = []
    for ind in sorted(post.indicators, key=lambda x: (x.span_start if x.span_start is not None else 999999, x.id)):
        indicators_list.append({
            "id": ind.id,
            "indicator_type": ind.indicator_type.value if hasattr(ind.indicator_type, "value") else str(ind.indicator_type),
            "raw_value": ind.raw_value,
            "normalised_value": ind.normalised_value,
            "span_start": ind.span_start,
            "span_end": ind.span_end,
            "confidence": ind.confidence,
            "extraction_method": ind.extraction_method.value if hasattr(ind.extraction_method, "value") else str(ind.extraction_method),
            "details": ind.details,
        })

    structured_indicators = (
        post.raw_metadata.get("structured_indicators") if post.raw_metadata else {}
    )

    return {
        "id": post.id,
        "marketplace": post.marketplace.name if post.marketplace else "Unknown",
        "author_username": post.author_username,
        "posted_at": post.posted_at.isoformat() if post.posted_at else None,
        "content": post.content,  # ORIGINAL exact text
        "source_reference": post.source_reference,
        "extractor_version": post.extractor_version,
        "extracted_at": post.extracted_at.isoformat() if post.extracted_at else None,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "dataset": {
            "id": post.dataset.id if post.dataset else None,
            "name": post.dataset.name if post.dataset else "Unknown",
            "source_type": post.dataset.source_type.value if hasattr(post.dataset.source_type, "value") else str(post.dataset.source_type),
        } if post.dataset else None,
        "ingested_by": post.ingested_by_user.username if post.ingested_by_user else None,
        "structured_indicators": structured_indicators,
        "indicators": indicators_list,
    }
