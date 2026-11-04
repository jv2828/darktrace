"""Graph service generating Cytoscape-compatible topology of personas, marketplaces, and indicators."""

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import APIException
from app.models.correlation_result import CorrelationResult
from app.models.extracted_indicator import ExtractedIndicator
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_stage_run import PipelineStageRun
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


def get_investigation_graph(
    db: Session,
    investigation_id: int,
    user: User,
    run_id: Optional[int] = None,
    min_score: float = 0.25,
    max_nodes: int = 250,
) -> Dict[str, Any]:
    """Build Cytoscape-formatted node-link graph with personas, marketplaces, and shared indicators."""
    _verify_investigation_access(db, investigation_id, user)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)
    if not target_run_id:
        return {"nodes": [], "edges": [], "truncated": False, "run_id": None}

    # 1. Datasets in this investigation
    dataset_ids = db.scalars(
        select(InvestigationDataset.dataset_id).where(
            InvestigationDataset.investigation_id == investigation_id
        )
    ).all()
    if not dataset_ids:
        return {"nodes": [], "edges": [], "truncated": False, "run_id": target_run_id}

    # 2. Suppressed common indicators for this run
    suppressed_indicators: Set[Tuple[str, str]] = set()
    stage_runs = db.scalars(
        select(PipelineStageRun).where(PipelineStageRun.pipeline_run_id == target_run_id)
    ).all()
    for sr in stage_runs:
        if sr.summary and "suppressed_common_indicators" in sr.summary:
            for s in sr.summary["suppressed_common_indicators"]:
                suppressed_indicators.add((s["type"], s["normalised_value"]))

    # 3. Personas and marketplaces
    posts_with_actors = db.execute(
        select(
            Post.actor_id,
            Post.marketplace_id,
            func.count(Post.id).label("post_count"),
            func.min(Post.posted_at).label("first_seen"),
            func.max(Post.posted_at).label("last_seen"),
        )
        .where(Post.dataset_id.in_(dataset_ids), Post.actor_id.isnot(None))
        .group_by(Post.actor_id, Post.marketplace_id)
    ).all()

    actor_ids = {row[0] for row in posts_with_actors}
    actors = db.execute(
        select(ThreatActor)
        .options(joinedload(ThreatActor.marketplace))
        .where(ThreatActor.id.in_(actor_ids))
    ).scalars().all()
    actor_map = {a.id: a for a in actors}

    actor_post_counts: Dict[int, int] = defaultdict(int)
    actor_marketplaces: Dict[int, int] = {}
    for row in posts_with_actors:
        aid, mid, pcount = row[0], row[1], row[2]
        actor_post_counts[aid] += pcount
        actor_marketplaces[aid] = mid

    marketplaces = db.execute(
        select(Marketplace).where(Marketplace.id.in_(set(actor_marketplaces.values())))
    ).scalars().all()
    marketplace_map = {m.id: m for m in marketplaces}

    # 4. Correlations for this run
    correlations = db.scalars(
        select(CorrelationResult)
        .where(
            CorrelationResult.pipeline_run_id == target_run_id,
            CorrelationResult.combined_score >= Decimal(str(min_score)),
        )
        .order_by(CorrelationResult.combined_score.desc())
    ).all()

    # Track best score per actor for prioritization
    actor_best_score: Dict[int, float] = defaultdict(float)
    for c in correlations:
        score_f = float(c.combined_score)
        if score_f > actor_best_score[c.actor_a_id]:
            actor_best_score[c.actor_a_id] = score_f
        if score_f > actor_best_score[c.actor_b_id]:
            actor_best_score[c.actor_b_id] = score_f

    # 5. Indicators used by personas in this investigation
    indicator_usage = db.execute(
        select(
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            Post.actor_id,
            func.count(distinct(Post.id)).label("post_count"),
            func.min(Post.posted_at).label("first_seen"),
            func.max(Post.posted_at).label("last_seen"),
        )
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .where(
            Post.dataset_id.in_(dataset_ids),
            Post.actor_id.isnot(None),
        )
        .group_by(
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            Post.actor_id,
        )
    ).all()

    # Group by indicator: count unique actors using it
    indicator_actors_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in indicator_usage:
        itype = row[0].value if hasattr(row[0], "value") else str(row[0])
        nval = row[1]
        aid = row[2]
        pcount = row[3]
        fseen = row[4].isoformat() if row[4] else None
        lseen = row[5].isoformat() if row[5] else None
        indicator_actors_map[(itype, nval)].append({
            "actor_id": aid,
            "post_count": pcount,
            "first_seen": fseen,
            "last_seen": lseen,
        })

    # Filter indicators: ONLY NON-common and used by >= 2 personas
    shared_indicators: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for (itype, nval), usages in indicator_actors_map.items():
        if len(usages) >= 2 and (itype, nval) not in suppressed_indicators:
            shared_indicators[(itype, nval)] = usages

    # 6. Construct candidates and node prioritization
    # Sort personas: highest score first, then post count
    sorted_actor_ids = sorted(
        list(actor_ids),
        key=lambda aid: (actor_best_score.get(aid, 0.0), actor_post_counts.get(aid, 0)),
        reverse=True,
    )

    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()
    truncated = False

    # Add persona nodes
    for aid in sorted_actor_ids:
        if len(nodes) >= max_nodes:
            truncated = True
            break
        actor = actor_map.get(aid)
        if not actor:
            continue
        mid = actor_marketplaces.get(aid)
        mkt_name = marketplace_map[mid].name if mid in marketplace_map else "Unknown"
        node_id = f"actor_{aid}"
        nodes.append({
            "data": {
                "id": node_id,
                "label": actor.username,
                "type": "persona",
                "username": actor.username,
                "marketplace": mkt_name,
                "marketplace_id": mid,
                "post_count": actor_post_counts[aid],
                "actor_id": aid,
                "best_score": round(actor_best_score.get(aid, 0.0), 4),
            }
        })
        node_ids.add(node_id)

    # Add marketplace nodes for included personas
    included_actor_ids = {int(nid.split("_")[1]) for nid in node_ids if nid.startswith("actor_")}
    used_marketplace_ids = {
        actor_marketplaces[aid] for aid in included_actor_ids if aid in actor_marketplaces
    }

    for mid in sorted(list(used_marketplace_ids)):
        if len(nodes) >= max_nodes:
            truncated = True
            break
        mkt = marketplace_map.get(mid)
        if mkt:
            node_id = f"mkt_{mid}"
            if node_id not in node_ids:
                nodes.append({
                    "data": {
                        "id": node_id,
                        "label": mkt.name,
                        "type": "marketplace",
                        "marketplace_id": mid,
                    }
                })
                node_ids.add(node_id)

    # Add shared indicator nodes connecting included personas
    for (itype, nval), usages in shared_indicators.items():
        # Only add if at least 2 included personas use it
        connected_included = [u for u in usages if u["actor_id"] in included_actor_ids]
        if len(connected_included) < 2:
            continue

        if len(nodes) >= max_nodes:
            truncated = True
            break

        # Node type classification
        if itype == "pgp_fingerprint":
            node_type = "pgp"
            node_id = f"ind_pgp_{nval}"
            short_label = nval[-8:] if len(nval) >= 8 else nval
        elif itype in ("btc_address", "monero_address"):
            node_type = "wallet"
            node_id = f"ind_wallet_{nval}"
            short_label = f"{nval[:6]}…{nval[-4:]}" if len(nval) >= 12 else nval
        else:
            node_type = "infrastructure"
            node_id = f"ind_infra_{itype}_{nval}"
            short_label = nval if len(nval) <= 24 else f"{nval[:22]}…"

        if node_id not in node_ids:
            nodes.append({
                "data": {
                    "id": node_id,
                    "label": short_label,
                    "type": node_type,
                    "indicator_type": itype,
                    "value": nval,
                    "full_value": nval,
                    "persona_count": len(connected_included),
                }
            })
            node_ids.add(node_id)

    # 7. Construct edges
    # a. "posts_on" edges: persona -> marketplace
    for aid in included_actor_ids:
        mid = actor_marketplaces.get(aid)
        if mid and f"mkt_{mid}" in node_ids and f"actor_{aid}" in node_ids:
            edges.append({
                "data": {
                    "id": f"edge:posts_on:actor_{aid}:mkt_{mid}",
                    "source": f"actor_{aid}",
                    "target": f"mkt_{mid}",
                    "type": "posts_on",
                }
            })

    # b. "uses" edges: persona -> indicator
    for (itype, nval), usages in shared_indicators.items():
        if itype == "pgp_fingerprint":
            node_id = f"ind_pgp_{nval}"
        elif itype in ("btc_address", "monero_address"):
            node_id = f"ind_wallet_{nval}"
        else:
            node_id = f"ind_infra_{itype}_{nval}"

        if node_id in node_ids:
            for u in usages:
                aid = u["actor_id"]
                if f"actor_{aid}" in node_ids:
                    edges.append({
                        "data": {
                            "id": f"edge:uses:actor_{aid}:{node_id}",
                            "source": f"actor_{aid}",
                            "target": node_id,
                            "type": "uses",
                            "post_count": u["post_count"],
                            "first_seen": u["first_seen"],
                            "last_seen": u["last_seen"],
                        }
                    })

    # c. "correlated" edges: persona <-> persona
    for c in correlations:
        src = f"actor_{c.actor_a_id}"
        tgt = f"actor_{c.actor_b_id}"
        if src in node_ids and tgt in node_ids:
            lvl, cov = compute_correlation_level_and_coverage(c)
            edges.append({
                "data": {
                    "id": f"edge:corr:{target_run_id}:{c.actor_a_id}:{c.actor_b_id}",
                    "source": src,
                    "target": tgt,
                    "type": "correlated",
                    "combined_score": round(float(c.combined_score), 4),
                    "level": lvl,
                    "coverage": round(float(cov), 4),
                    "dimension_scores": c.dimension_scores,
                    "contradiction_count": len(c.contradictions),
                }
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "truncated": truncated,
        "run_id": target_run_id,
    }
