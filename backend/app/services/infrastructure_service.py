"""Infrastructure service managing grouped indicators, shared footprints, and corroborating evidence."""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIException
from app.models.evidence_record import EvidenceDimension, EvidenceRecord
from app.models.evidence_source import EvidenceSource
from app.models.extracted_indicator import ExtractedIndicator, IndicatorType
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.pipeline_stage_run import PipelineStageRun
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole
from app.services.correlation_service import get_latest_completed_run_id

CRYPTO_TYPES = {
    "btc_address",
    "monero_address",
    "pgp_fingerprint",
}


def _verify_investigation_access(db: Session, investigation_id: int, user: User) -> Investigation:
    """Check existence and verify investigator ownership (404 for other investigators)."""
    inv = db.scalar(select(Investigation).where(Investigation.id == investigation_id))
    if not inv:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    if user.role != UserRole.ADMIN and inv.created_by != user.id:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    return inv


def get_investigation_infrastructure(
    db: Session,
    investigation_id: int,
    user: User,
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve infrastructure & crypto indicators grouped by value, with associated personas and evidence."""
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
            "indicators": [],
            "evidence_pairs": [],
            "run_id": target_run_id,
        }

    # Suppressed common indicators for target run
    suppressed_indicators: Set[Tuple[str, str]] = set()
    if target_run_id:
        stage_runs = db.scalars(
            select(PipelineStageRun).where(PipelineStageRun.pipeline_run_id == target_run_id)
        ).all()
        for sr in stage_runs:
            if sr.summary and "suppressed_common_indicators" in sr.summary:
                for s in sr.summary["suppressed_common_indicators"]:
                    suppressed_indicators.add((s["type"], s["normalised_value"]))

    # Query all indicators in these datasets linked to actors
    rows = db.execute(
        select(
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            Post.actor_id,
            ThreatActor.username,
            Marketplace.name.label("marketplace"),
            func.count(distinct(Post.id)).label("post_count"),
            func.min(Post.posted_at).label("first_seen"),
            func.max(Post.posted_at).label("last_seen"),
        )
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .join(ThreatActor, Post.actor_id == ThreatActor.id)
        .join(Marketplace, ThreatActor.marketplace_id == Marketplace.id)
        .where(Post.dataset_id.in_(dataset_ids))
        .group_by(
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            Post.actor_id,
            ThreatActor.username,
            Marketplace.name,
        )
    ).all()

    # Group by (indicator_type, normalised_value)
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in rows:
        itype = r[0].value if hasattr(r[0], "value") else str(r[0])
        nval = r[1]
        aid = r[2]
        username = r[3]
        mkt_name = r[4]
        pcount = r[5]
        fseen = r[6].isoformat() if r[6] else None
        lseen = r[7].isoformat() if r[7] else None

        key = (itype, nval)
        if key not in grouped:
            is_crypto = itype in CRYPTO_TYPES
            grouped[key] = {
                "indicator_type": itype,
                "normalised_value": nval,
                "kind": "cryptographic" if is_crypto else "infrastructure",
                "personas": [],
                "total_posts": 0,
            }

        grouped[key]["personas"].append({
            "id": aid,
            "username": username,
            "marketplace": mkt_name,
            "post_count": pcount,
            "first_seen": fseen,
            "last_seen": lseen,
        })
        grouped[key]["total_posts"] += pcount

    indicators_list = []
    for (itype, nval), item in grouped.items():
        is_suppressed = (itype, nval) in suppressed_indicators
        persona_count = len(item["personas"])
        if is_suppressed:
            status = "common_suppressed"
        elif persona_count >= 2:
            status = "shared"
        else:
            status = "single"

        item["status"] = status
        item["persona_count"] = persona_count
        indicators_list.append(item)

    # Sort indicators: shared first, then common_suppressed, then single
    status_order = {"shared": 0, "common_suppressed": 1, "single": 2}
    indicators_list.sort(key=lambda x: (status_order.get(x["status"], 99), -x["persona_count"], x["indicator_type"]))

    # Evidence pairs for infrastructure and crypto
    evidence_pairs = []
    if target_run_id:
        ev_records = db.scalars(
            select(EvidenceRecord)
            .options(
                joinedload(EvidenceRecord.actor_a).joinedload(ThreatActor.marketplace),
                joinedload(EvidenceRecord.actor_b).joinedload(ThreatActor.marketplace),
                joinedload(EvidenceRecord.sources),
            )
            .where(
                EvidenceRecord.pipeline_run_id == target_run_id,
                EvidenceRecord.dimension.in_([EvidenceDimension.INFRASTRUCTURE, EvidenceDimension.CRYPTOGRAPHIC]),
            )
            .order_by(EvidenceRecord.strength.desc())
        ).unique().all()

        for ev in ev_records:
            source_post_ids = list({s.post_id for s in ev.sources if s.post_id is not None})
            evidence_pairs.append({
                "id": ev.id,
                "dimension": ev.dimension.value if hasattr(ev.dimension, "value") else str(ev.dimension),
                "direction": ev.direction.value if hasattr(ev.direction, "value") else str(ev.direction),
                "evidence_type": ev.evidence_type,
                "strength": float(ev.strength),
                "explanation": ev.explanation,
                "details": ev.details or {},
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
                "source_post_ids": source_post_ids,
            })

    return {
        "indicators": indicators_list,
        "evidence_pairs": evidence_pairs,
        "run_id": target_run_id,
    }

