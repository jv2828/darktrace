"""Service for querying correlation evidence, source provenance, and actor pair linkages."""

from collections import defaultdict
from decimal import Decimal
from math import ceil
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIException
from app.models.evidence_record import EvidenceRecord
from app.models.evidence_source import EvidenceSource
from app.models.investigation import Investigation
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole


def _verify_investigation_access(db: Session, investigation_id: int, user: User) -> Investigation:
    """Verify investigation exists and user has authorization."""
    inv = db.get(Investigation, investigation_id)
    if not inv:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    if user.role != UserRole.ADMIN and inv.created_by != user.id:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    return inv


def get_latest_completed_run_id(db: Session, investigation_id: int) -> Optional[int]:
    """Retrieve the primary ID of the most recently completed pipeline run."""
    run_id = db.scalar(
        select(PipelineRun.id)
        .where(
            PipelineRun.investigation_id == investigation_id,
            PipelineRun.status == PipelineRunStatus.COMPLETED,
        )
        .order_by(PipelineRun.finished_at.desc().nullslast(), PipelineRun.created_at.desc())
        .limit(1)
    )
    return run_id


def list_investigation_evidence(
    db: Session,
    investigation_id: int,
    user: User,
    run_id: Optional[int] = None,
    dimension: Optional[str] = None,
    evidence_type: Optional[str] = None,
    actor_id: Optional[int] = None,
    min_strength: Optional[float] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """List paginated evidence records for an investigation."""
    _verify_investigation_access(db, investigation_id, user)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)
    if not target_run_id:
        return {
            "items": [],
            "meta": {"page": page, "page_size": page_size, "total": 0, "total_pages": 0, "run_id": None},
        }

    # Verify run belongs to this investigation
    run = db.get(PipelineRun, target_run_id)
    if not run or run.investigation_id != investigation_id:
        raise APIException(code="NOT_FOUND", message="Pipeline run not found.", status_code=404)

    query = (
        select(EvidenceRecord)
        .options(
            joinedload(EvidenceRecord.actor_a).joinedload(ThreatActor.marketplace),
            joinedload(EvidenceRecord.actor_b).joinedload(ThreatActor.marketplace),
            joinedload(EvidenceRecord.sources),
        )
        .where(EvidenceRecord.pipeline_run_id == target_run_id)
    )

    if dimension:
        query = query.where(EvidenceRecord.dimension == dimension)
    if evidence_type:
        query = query.where(EvidenceRecord.evidence_type == evidence_type)
    if actor_id:
        query = query.where(
            (EvidenceRecord.actor_a_id == actor_id) | (EvidenceRecord.actor_b_id == actor_id)
        )
    if min_strength is not None:
        query = query.where(EvidenceRecord.strength >= Decimal(str(min_strength)))

    # Count total matching
    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query) or 0

    page_size = max(1, min(100, page_size))
    total_pages = ceil(total / page_size) if total > 0 else 0
    offset = (max(1, page) - 1) * page_size

    records = db.execute(
        query.order_by(EvidenceRecord.strength.desc(), EvidenceRecord.id.asc())
        .offset(offset)
        .limit(page_size)
    ).unique().scalars().all()

    items = [
        {
            "id": r.id,
            "dimension": r.dimension.value if hasattr(r.dimension, "value") else str(r.dimension),
            "evidence_type": r.evidence_type,
            "direction": r.direction.value if hasattr(r.direction, "value") else str(r.direction),
            "strength": float(r.strength),
            "explanation": r.explanation,
            "actor_a": {
                "id": r.actor_a.id,
                "username": r.actor_a.username,
                "marketplace": r.actor_a.marketplace.name if r.actor_a.marketplace else "Dark Web",
            },
            "actor_b": {
                "id": r.actor_b.id,
                "username": r.actor_b.username,
                "marketplace": r.actor_b.marketplace.name if r.actor_b.marketplace else "Dark Web",
            },
            "source_count": len(r.sources),
        }
        for r in records
    ]

    return {
        "items": items,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "run_id": target_run_id,
        },
    }


def get_evidence_detail(
    db: Session,
    investigation_id: int,
    evidence_id: int,
    user: User,
) -> Dict[str, Any]:
    """Retrieve full details of an individual evidence finding with source origins."""
    _verify_investigation_access(db, investigation_id, user)

    record = db.execute(
        select(EvidenceRecord)
        .options(
            joinedload(EvidenceRecord.pipeline_run),
            joinedload(EvidenceRecord.actor_a).joinedload(ThreatActor.marketplace),
            joinedload(EvidenceRecord.actor_b).joinedload(ThreatActor.marketplace),
            joinedload(EvidenceRecord.sources).joinedload(EvidenceSource.post).joinedload(Post.marketplace),
            joinedload(EvidenceRecord.sources).joinedload(EvidenceSource.post).joinedload(Post.actor),
            joinedload(EvidenceRecord.sources).joinedload(EvidenceSource.indicator),
        )
        .where(EvidenceRecord.id == evidence_id)
    ).unique().scalar_one_or_none()

    if not record or record.pipeline_run.investigation_id != investigation_id:
        raise APIException(code="NOT_FOUND", message="Evidence record not found.", status_code=404)

    sources_data = []
    for src in record.sources:
        p_data = None
        if src.post:
            post_content = src.post.content or ""
            excerpt = (post_content[:160] + "…") if len(post_content) > 160 else post_content
            p_data = {
                "id": src.post.id,
                "marketplace": src.post.marketplace.name if src.post.marketplace else "Dark Web",
                "author": src.post.author_username or (src.post.actor.username if src.post.actor else "unknown"),
                "posted_at": src.post.posted_at.isoformat() if src.post.posted_at else None,
                "excerpt": excerpt,
            }

        ind_data = None
        if src.indicator:
            ind_type = (
                src.indicator.indicator_type.value
                if hasattr(src.indicator.indicator_type, "value")
                else str(src.indicator.indicator_type)
            )
            ind_data = {
                "id": src.indicator.id,
                "type": ind_type,
                "raw_value": src.indicator.raw_value,
                "normalised_value": src.indicator.normalised_value,
                "span": (src.indicator.details or {}).get("span"),
            }

        sources_data.append({"post": p_data, "indicator": ind_data})

    return {
        "id": record.id,
        "dimension": record.dimension.value if hasattr(record.dimension, "value") else str(record.dimension),
        "evidence_type": record.evidence_type,
        "direction": record.direction.value if hasattr(record.direction, "value") else str(record.direction),
        "strength": float(record.strength),
        "explanation": record.explanation,
        "details": record.details,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "actor_a": {
            "id": record.actor_a.id,
            "username": record.actor_a.username,
            "marketplace": record.actor_a.marketplace.name if record.actor_a.marketplace else "Dark Web",
        },
        "actor_b": {
            "id": record.actor_b.id,
            "username": record.actor_b.username,
            "marketplace": record.actor_b.marketplace.name if record.actor_b.marketplace else "Dark Web",
        },
        "sources": sources_data,
    }


def list_investigation_pairs(
    db: Session,
    investigation_id: int,
    user: User,
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve correlated actor pairs for the chosen run, aggregated by dimension with max strength."""
    _verify_investigation_access(db, investigation_id, user)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)
    if not target_run_id:
        return {"items": [], "run_id": None}

    run = db.get(PipelineRun, target_run_id)
    if not run or run.investigation_id != investigation_id:
        raise APIException(code="NOT_FOUND", message="Pipeline run not found.", status_code=404)

    records = db.execute(
        select(EvidenceRecord)
        .options(
            joinedload(EvidenceRecord.actor_a).joinedload(ThreatActor.marketplace),
            joinedload(EvidenceRecord.actor_b).joinedload(ThreatActor.marketplace),
        )
        .where(EvidenceRecord.pipeline_run_id == target_run_id)
    ).unique().scalars().all()

    # Aggregate by actor pair (actor_a_id, actor_b_id)
    pair_evidence = defaultdict(list)
    actors_map = {}

    for r in records:
        key = (r.actor_a_id, r.actor_b_id)
        pair_evidence[key].append(r)
        if r.actor_a_id not in actors_map:
            actors_map[r.actor_a_id] = {
                "id": r.actor_a.id,
                "username": r.actor_a.username,
                "marketplace": r.actor_a.marketplace.name if r.actor_a.marketplace else "Dark Web",
            }
        if r.actor_b_id not in actors_map:
            actors_map[r.actor_b_id] = {
                "id": r.actor_b.id,
                "username": r.actor_b.username,
                "marketplace": r.actor_b.marketplace.name if r.actor_b.marketplace else "Dark Web",
            }

    pair_items = []
    for (a_id, b_id), rec_list in pair_evidence.items():
        per_dimension: Dict[str, Dict[str, Any]] = {}
        max_str = 0.0

        for r in rec_list:
            dim_str = r.dimension.value if hasattr(r.dimension, "value") else str(r.dimension)
            val = float(r.strength)
            if val > max_str:
                max_str = val
            if dim_str not in per_dimension:
                per_dimension[dim_str] = {"count": 1, "max_strength": val}
            else:
                per_dimension[dim_str]["count"] += 1
                if val > per_dimension[dim_str]["max_strength"]:
                    per_dimension[dim_str]["max_strength"] = val

        pair_items.append({
            "actors": {
                "actor_a": actors_map[a_id],
                "actor_b": actors_map[b_id],
            },
            "evidence_count": len(rec_list),
            "per_dimension": per_dimension,
            "max_strength": round(max_str, 4),
        })

    # Sort strictly by max_strength desc, then actor ids
    pair_items.sort(
        key=lambda p: (
            -p["max_strength"],
            p["actors"]["actor_a"]["id"],
            p["actors"]["actor_b"]["id"],
        )
    )

    return {"items": pair_items, "run_id": target_run_id}
