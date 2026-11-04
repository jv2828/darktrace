"""Chronology service providing temporal activity profiles, indicator emergence, and pipeline runs."""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIException
from app.models.evidence_record import EvidenceRecord
from app.models.extracted_indicator import ExtractedIndicator
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_stage_run import PipelineStageRun
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole
from app.services.correlation_service import get_latest_completed_run_id


def _verify_investigation_access(db: Session, investigation_id: int, user: User) -> Investigation:
    """Check existence and verify investigator ownership (404 for other investigators)."""
    inv = db.scalar(select(Investigation).where(Investigation.id == investigation_id))
    if not inv:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    if user.role != UserRole.ADMIN and inv.created_by != user.id:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    return inv


def get_investigation_chronology(
    db: Session,
    investigation_id: int,
    user: User,
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve temporal activity timeline, first-seen indicator chronology, runs, and evidence events."""
    _verify_investigation_access(db, investigation_id, user)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)

    # Datasets
    dataset_ids = db.scalars(
        select(InvestigationDataset.dataset_id).where(
            InvestigationDataset.investigation_id == investigation_id
        )
    ).all()

    if not dataset_ids:
        return {
            "posts_by_day": [],
            "indicator_first_seen": [],
            "runs": [],
            "evidence_events": [],
            "run_id": target_run_id,
        }

    # 1. Posts by Day
    day_counts = db.execute(
        select(
            func.date(Post.posted_at).label("day"),
            Post.actor_id,
            Marketplace.name.label("marketplace"),
            func.count(Post.id).label("count"),
        )
        .join(Marketplace, Post.marketplace_id == Marketplace.id)
        .where(
            Post.dataset_id.in_(dataset_ids),
            Post.posted_at.isnot(None),
            Post.actor_id.isnot(None),
        )
        .group_by(func.date(Post.posted_at), Post.actor_id, Marketplace.name)
        .order_by(func.date(Post.posted_at).asc())
    ).all()

    posts_by_day = [
        {
            "date": str(row[0]),
            "actor_id": row[1],
            "marketplace": row[2],
            "count": row[3],
        }
        for row in day_counts
    ]

    # 2. Suppressed indicators for target run
    suppressed_indicators: Set[Tuple[str, str]] = set()
    if target_run_id:
        stage_runs = db.scalars(
            select(PipelineStageRun).where(PipelineStageRun.pipeline_run_id == target_run_id)
        ).all()
        for sr in stage_runs:
            if sr.summary and "suppressed_common_indicators" in sr.summary:
                for s in sr.summary["suppressed_common_indicators"]:
                    suppressed_indicators.add((s["type"], s["normalised_value"]))

    # 3. Indicator First Seen
    # First compute actor counts per indicator across investigation
    indicator_actor_counts = db.execute(
        select(
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            func.count(distinct(Post.actor_id)).label("actor_count"),
        )
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .where(Post.dataset_id.in_(dataset_ids), Post.actor_id.isnot(None))
        .group_by(ExtractedIndicator.indicator_type, ExtractedIndicator.normalised_value)
    ).all()

    shared_set = {
        (row[0].value if hasattr(row[0], "value") else str(row[0]), row[1])
        for row in indicator_actor_counts
        if row[2] >= 2
    }

    # Group first appearance per (indicator_type, normalised_value, actor_id)
    first_seen_rows = db.execute(
        select(
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            Post.actor_id,
            func.min(Post.posted_at).label("first_seen"),
            func.min(Post.id).label("post_id"),
        )
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .where(
            Post.dataset_id.in_(dataset_ids),
            Post.actor_id.isnot(None),
            Post.posted_at.isnot(None),
        )
        .group_by(
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            Post.actor_id,
        )
    ).all()

    indicators_list = []
    for row in first_seen_rows:
        itype = row[0].value if hasattr(row[0], "value") else str(row[0])
        nval = row[1]
        aid = row[2]
        fseen = row[3].isoformat() if row[3] else None
        pid = row[4]
        is_shared = (itype, nval) in shared_set
        is_common = (itype, nval) in suppressed_indicators

        indicators_list.append({
            "indicator_type": itype,
            "normalised_value": nval,
            "actor_id": aid,
            "first_seen": fseen,
            "post_id": pid,
            "shared": is_shared,
            "common": is_common,
        })

    # Sort: non-common shared first (shared=True, common=False), then by first_seen
    indicators_list.sort(
        key=lambda item: (
            not (item["shared"] and not item["common"]),  # False (0) comes first
            item["first_seen"] or "",
        )
    )
    indicator_first_seen = indicators_list[:300]

    # 4. Pipeline Runs
    runs_entities = db.scalars(
        select(PipelineRun)
        .options(joinedload(PipelineRun.stage_runs))
        .where(PipelineRun.investigation_id == investigation_id)
        .order_by(PipelineRun.created_at.desc())
    ).unique().all()

    runs_data = []
    for r in runs_entities:
        pairs_scored = 0
        scoring_stage = next((s for s in r.stage_runs if s.stage.value == "scoring"), None)
        if scoring_stage and scoring_stage.summary:
            pairs_scored = scoring_stage.summary.get("pairs_scored", 0)

        runs_data.append({
            "id": r.id,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "pairs_scored": pairs_scored,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    # 5. Top 100 Evidence Events for target_run_id
    evidence_events = []
    if target_run_id:
        ev_records = db.scalars(
            select(EvidenceRecord)
            .options(
                joinedload(EvidenceRecord.actor_a).joinedload(ThreatActor.marketplace),
                joinedload(EvidenceRecord.actor_b).joinedload(ThreatActor.marketplace),
            )
            .where(EvidenceRecord.pipeline_run_id == target_run_id)
            .order_by(EvidenceRecord.strength.desc())
            .limit(100)
        ).all()

        for ev in ev_records:
            evidence_events.append({
                "id": ev.id,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
                "dimension": ev.dimension.value if hasattr(ev.dimension, "value") else str(ev.dimension),
                "direction": ev.direction.value if hasattr(ev.direction, "value") else str(ev.direction),
                "evidence_type": ev.evidence_type,
                "strength": float(ev.strength),
                "explanation": ev.explanation,
                "actor_a": {
                    "id": ev.actor_a_id,
                    "username": ev.actor_a.username if ev.actor_a else "Unknown",
                    "marketplace": ev.actor_a.marketplace.name if (ev.actor_a and ev.actor_a.marketplace) else "Unknown",
                },
                "actor_b": {
                    "id": ev.actor_b_id,
                    "username": ev.actor_b.username if ev.actor_b else "Unknown",
                    "marketplace": ev.actor_b.marketplace.name if (ev.actor_b and ev.actor_b.marketplace) else "Unknown",
                },
            })

    return {
        "posts_by_day": posts_by_day,
        "indicator_first_seen": indicator_first_seen,
        "runs": runs_data,
        "evidence_events": evidence_events,
        "run_id": target_run_id,
    }

