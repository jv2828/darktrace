"""Actor service for persona catalogs, deep actor profiles, writeprints, and potential linkages."""

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIException
from app.models.actor_alias import ActorAlias
from app.models.analysis_result import AnalysisResult, AnalysisType
from app.models.correlation_result import CorrelationResult
from app.models.evidence_record import EvidenceRecord
from app.models.extracted_indicator import ExtractedIndicator
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole
from app.services.correlation_service import (
    compute_correlation_level_and_coverage,
    get_latest_completed_run_id,
)


def _verify_investigation_access(db: Session, investigation_id: int, user: User) -> Investigation:
    """Check existence and verify investigator ownership (404 for other investigators)."""
    inv = db.scalar(select(Investigation).where(Investigation.id == investigation_id))
    if not inv:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    if user.role != UserRole.ADMIN and inv.created_by != user.id:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    return inv


def list_investigation_actors(
    db: Session,
    investigation_id: int,
    user: User,
    run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """List all personas in the investigation with activity metrics, indicator counts, and best link score."""
    _verify_investigation_access(db, investigation_id, user)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)

    dataset_ids = db.scalars(
        select(InvestigationDataset.dataset_id).where(
            InvestigationDataset.investigation_id == investigation_id
        )
    ).all()
    if not dataset_ids:
        return []

    # 1. Post metrics per actor
    post_stats = db.execute(
        select(
            Post.actor_id,
            func.count(Post.id).label("post_count"),
            func.min(Post.posted_at).label("first_seen"),
            func.max(Post.posted_at).label("last_seen"),
        )
        .where(Post.dataset_id.in_(dataset_ids), Post.actor_id.isnot(None))
        .group_by(Post.actor_id)
    ).all()
    actor_stats_map = {row[0]: (row[1], row[2], row[3]) for row in post_stats}
    actor_ids = list(actor_stats_map.keys())

    if not actor_ids:
        return []

    # 2. Actors with marketplaces
    actors = db.execute(
        select(ThreatActor)
        .options(joinedload(ThreatActor.marketplace))
        .where(ThreatActor.id.in_(actor_ids))
    ).scalars().all()
    actor_obj_map = {a.id: a for a in actors}

    # 3. Indicator counts by type per actor
    ind_counts = db.execute(
        select(
            Post.actor_id,
            ExtractedIndicator.indicator_type,
            func.count(distinct(ExtractedIndicator.id)).label("count"),
        )
        .join(ExtractedIndicator, ExtractedIndicator.post_id == Post.id)
        .where(Post.dataset_id.in_(dataset_ids), Post.actor_id.in_(actor_ids))
        .group_by(Post.actor_id, ExtractedIndicator.indicator_type)
    ).all()
    actor_indicators_map: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for aid, itype, cnt in ind_counts:
        t_str = itype.value if hasattr(itype, "value") else str(itype)
        actor_indicators_map[aid][t_str] = cnt

    # 4. Best correlation score per actor in target run
    best_partner_scores: Dict[int, float] = {}
    if target_run_id:
        corrs = db.scalars(
            select(CorrelationResult).where(CorrelationResult.pipeline_run_id == target_run_id)
        ).all()
        for c in corrs:
            sc = float(c.combined_score)
            if c.actor_a_id not in best_partner_scores or sc > best_partner_scores[c.actor_a_id]:
                best_partner_scores[c.actor_a_id] = sc
            if c.actor_b_id not in best_partner_scores or sc > best_partner_scores[c.actor_b_id]:
                best_partner_scores[c.actor_b_id] = sc

    # Assemble response
    result = []
    for aid in sorted(actor_ids):
        actor = actor_obj_map.get(aid)
        if not actor:
            continue
        p_count, f_seen, l_seen = actor_stats_map[aid]
        result.append({
            "id": aid,
            "username": actor.username,
            "marketplace": actor.marketplace.name if actor.marketplace else "Unknown",
            "marketplace_id": actor.marketplace_id,
            "post_count": p_count,
            "first_seen": f_seen.isoformat() if f_seen else None,
            "last_seen": l_seen.isoformat() if l_seen else None,
            "indicator_counts": dict(actor_indicators_map[aid]),
            "best_correlated_partner_score": best_partner_scores.get(aid),
        })

    # Sort by post count descending
    result.sort(key=lambda x: (x["best_correlated_partner_score"] or 0.0, x["post_count"]), reverse=True)
    return result


def get_actor_profile(
    db: Session,
    investigation_id: int,
    actor_id: int,
    user: User,
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve detailed threat actor profile with evidence-based possible related personas."""
    _verify_investigation_access(db, investigation_id, user)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)

    dataset_ids = db.scalars(
        select(InvestigationDataset.dataset_id).where(
            InvestigationDataset.investigation_id == investigation_id
        )
    ).all()

    # Verify actor exists in this investigation
    actor_in_inv = db.scalar(
        select(Post.id)
        .where(Post.dataset_id.in_(dataset_ids), Post.actor_id == actor_id)
        .limit(1)
    )
    if not actor_in_inv:
        raise APIException(code="NOT_FOUND", message="Threat actor not found in this investigation.", status_code=404)

    actor = db.execute(
        select(ThreatActor)
        .options(
            joinedload(ThreatActor.marketplace),
            joinedload(ThreatActor.aliases),
        )
        .where(ThreatActor.id == actor_id)
    ).unique().scalar_one()

    # 1. Known Aliases
    aliases_list = [a.alias for a in actor.aliases]

    # 2. Marketplaces
    mkt_names = db.scalars(
        select(Marketplace.name).distinct()
        .join(Post, Post.marketplace_id == Marketplace.id)
        .where(Post.dataset_id.in_(dataset_ids), Post.actor_id == actor_id)
    ).all()
    marketplaces = list(mkt_names) if mkt_names else ([actor.marketplace.name] if actor.marketplace else [])

    # 3. Categorised Indicators used by this actor
    ind_rows = db.execute(
        select(
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            func.count(distinct(Post.id)).label("post_count"),
        )
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .where(Post.dataset_id.in_(dataset_ids), Post.actor_id == actor_id)
        .group_by(ExtractedIndicator.indicator_type, ExtractedIndicator.normalised_value)
        .order_by(func.count(distinct(Post.id)).desc())
    ).all()

    pgp_identifiers: List[Dict[str, Any]] = []
    wallet_identifiers: List[Dict[str, Any]] = []
    infrastructure_indicators: List[Dict[str, Any]] = []

    for row in ind_rows:
        itype = row[0].value if hasattr(row[0], "value") else str(row[0])
        nval = row[1]
        cnt = row[2]
        item = {"type": itype, "value": nval, "post_count": cnt}

        if itype == "pgp_fingerprint":
            pgp_identifiers.append(item)
        elif itype in ("btc_address", "monero_address"):
            wallet_identifiers.append(item)
        else:
            infrastructure_indicators.append(item)

    # 4. Behaviour and Stylometry Summaries from analysis_results
    behaviour_summary = {}
    stylometry_summary = {}

    if target_run_id:
        b_res = db.scalar(
            select(AnalysisResult.result).where(
                AnalysisResult.pipeline_run_id == target_run_id,
                AnalysisResult.actor_id == actor_id,
                AnalysisResult.analysis_type == AnalysisType.BEHAVIOUR_PROFILE,
            )
        )
        if b_res:
            behaviour_summary = b_res

        s_res = db.scalar(
            select(AnalysisResult.result).where(
                AnalysisResult.pipeline_run_id == target_run_id,
                AnalysisResult.actor_id == actor_id,
                AnalysisResult.analysis_type == AnalysisType.STYLOMETRY_FEATURES,
            )
        )
        if s_res:
            stylometry_summary = s_res

    # 5. Possible Related Personas (Correlations >= 0.45 in target_run_id)
    # Strictly worded as possible related personas, NEVER that they are the same person.
    possible_related_personas: List[Dict[str, Any]] = []
    actor_contradictions: List[Dict[str, Any]] = []

    if target_run_id:
        corrs = db.execute(
            select(CorrelationResult)
            .options(
                joinedload(CorrelationResult.actor_a).joinedload(ThreatActor.marketplace),
                joinedload(CorrelationResult.actor_b).joinedload(ThreatActor.marketplace),
            )
            .where(
                CorrelationResult.pipeline_run_id == target_run_id,
                (CorrelationResult.actor_a_id == actor_id) | (CorrelationResult.actor_b_id == actor_id),
            )
            .order_by(CorrelationResult.combined_score.desc())
        ).unique().scalars().all()

        for c in corrs:
            other_actor = c.actor_b if c.actor_a_id == actor_id else c.actor_a
            if not other_actor:
                continue

            # Record any contradictions involving this pair
            if c.contradictions:
                for contra in c.contradictions:
                    actor_contradictions.append({
                        "partner_id": other_actor.id,
                        "partner_username": other_actor.username,
                        "partner_marketplace": other_actor.marketplace.name if other_actor.marketplace else "Unknown",
                        "dimension": contra.get("dimension"),
                        "strength": contra.get("strength"),
                        "short_text": contra.get("short_text"),
                        "evidence_id": contra.get("evidence_id"),
                    })

            # Check if reaches strong or moderate threshold (>= 0.45)
            if c.combined_score >= Decimal("0.45"):
                # Fetch strongest evidence record explanation for this pair
                pair_a = min(c.actor_a_id, c.actor_b_id)
                pair_b = max(c.actor_a_id, c.actor_b_id)
                top_ev = db.scalar(
                    select(EvidenceRecord)
                    .where(
                        EvidenceRecord.pipeline_run_id == target_run_id,
                        EvidenceRecord.actor_a_id == pair_a,
                        EvidenceRecord.actor_b_id == pair_b,
                        EvidenceRecord.direction == "supporting",
                    )
                    .order_by(EvidenceRecord.strength.desc())
                    .limit(1)
                )

                lvl, cov = compute_correlation_level_and_coverage(c)
                possible_related_personas.append({
                    "actor_id": other_actor.id,
                    "username": other_actor.username,
                    "marketplace": other_actor.marketplace.name if other_actor.marketplace else "Unknown",
                    "score": round(float(c.combined_score), 4),
                    "level": lvl,
                    "coverage": round(float(cov), 4),
                    "top_explanation": top_ev.explanation if top_ev else "Correlated across multiple behavioral dimensions.",
                    "disclaimer": "Heuristic evidence score. Does not represent definitive identity confirmation.",
                })

    # 6. Recent Posts (up to 10)
    posts = db.execute(
        select(Post)
        .options(joinedload(Post.marketplace))
        .where(Post.dataset_id.in_(dataset_ids), Post.actor_id == actor_id)
        .order_by(Post.posted_at.desc())
        .limit(10)
    ).scalars().all()

    recent_posts = [
        {
            "id": p.id,
            "title": (p.raw_metadata or {}).get("title") or (p.raw_metadata or {}).get("subject") or f"Post #{p.id}",
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
            "marketplace": p.marketplace.name if p.marketplace else "Unknown",
            "content_preview": (p.content[:240] + "…") if len(p.content) > 240 else p.content,
        }
        for p in posts
    ]

    return {
        "actor_id": actor_id,
        "primary_username": actor.username,
        "marketplace": actor.marketplace.name if actor.marketplace else "Unknown",
        "marketplace_id": actor.marketplace_id,
        "aliases": aliases_list,
        "marketplaces": marketplaces,
        "pgp_identifiers": pgp_identifiers,
        "wallet_identifiers": wallet_identifiers,
        "infrastructure_indicators": infrastructure_indicators,
        "behaviour_summary": behaviour_summary,
        "stylometry_summary": stylometry_summary,
        "possible_related_personas": possible_related_personas,
        "contradictions": actor_contradictions,
        "recent_posts": recent_posts,
        "run_id": target_run_id,
    }
