"""Service for querying correlation results, actor writeprint analyses, and pair details."""

from math import ceil
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.analysis.stylometry import (
    compare_actors_stylometry,
    extract_actor_features,
    get_text_sufficiency,
    tokenize_sentences,
    tokenize_words,
)
from app.core.exceptions import APIException
from app.models.analysis_result import AnalysisResult, AnalysisType
from app.models.correlation_result import CorrelationResult
from app.models.evidence_record import EvidenceRecord
from app.models.evidence_source import EvidenceSource
from app.models.investigation import Investigation
from app.models.marketplace import Marketplace
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
    """Retrieve the ID of the most recently completed pipeline run."""
    return db.scalar(
        select(PipelineRun.id)
        .where(
            PipelineRun.investigation_id == investigation_id,
            PipelineRun.status == PipelineRunStatus.COMPLETED,
        )
        .order_by(PipelineRun.finished_at.desc().nullslast(), PipelineRun.created_at.desc())
        .limit(1)
    )


def compute_correlation_level_and_coverage(corr: CorrelationResult) -> Tuple[str, float]:
    """Compute qualitative confidence level and indicator dimension coverage for a correlation result."""
    score = float(corr.combined_score)
    lvl = "none"
    if score >= 0.70:
        lvl = "strong"
    elif score >= 0.45:
        lvl = "moderate"
    elif score >= 0.25:
        lvl = "weak"

    pos_dims = [d for d, dinfo in (corr.dimension_scores or {}).items() if dinfo.get("score", 0.0) > 0 and dinfo.get("counted")]
    if len(pos_dims) == 1:
        if not (pos_dims[0] == "cryptographic" and (corr.dimension_scores or {}).get("cryptographic", {}).get("score", 0.0) >= 0.90):
            if lvl == "strong":
                lvl = "moderate"

    max_contra = max([c.get("strength", 0.0) for c in (corr.contradictions or [])], default=0.0)
    if max_contra >= 0.60 and lvl == "strong":
        lvl = "moderate"

    counted_weights = sum(c.get("weight", 0.0) for c in (corr.contributions or {}).values())
    coverage = min(1.0, counted_weights)
    return lvl, coverage


def list_investigation_correlations(
    db: Session,
    investigation_id: int,
    user: User,
    run_id: Optional[int] = None,
    min_score: Optional[float] = None,
    level: Optional[str] = None,
    actor_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """List stored correlation results for an investigation."""
    _verify_investigation_access(db, investigation_id, user)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)
    if not target_run_id:
        return {"items": [], "total": 0, "page": page, "page_size": page_size, "run_id": None}

    query = (
        select(CorrelationResult)
        .options(
            joinedload(CorrelationResult.actor_a).joinedload(ThreatActor.marketplace),
            joinedload(CorrelationResult.actor_b).joinedload(ThreatActor.marketplace),
            joinedload(CorrelationResult.pipeline_run),
        )
        .join(PipelineRun, CorrelationResult.pipeline_run_id == PipelineRun.id)
        .where(
            CorrelationResult.pipeline_run_id == target_run_id,
            PipelineRun.investigation_id == investigation_id,
        )
    )

    if min_score is not None:
        query = query.where(CorrelationResult.combined_score >= min_score)

    if actor_id is not None:
        query = query.where(
            or_(
                CorrelationResult.actor_a_id == actor_id,
                CorrelationResult.actor_b_id == actor_id,
            )
        )

    # Note: level filtering is handled post-query or via thresholds if stored,
    # but level is computed from combined_score & rules.
    all_results = db.execute(query.order_by(CorrelationResult.combined_score.desc())).unique().scalars().all()

    items: List[Dict[str, Any]] = []
    for r in all_results:
        lvl, coverage = compute_correlation_level_and_coverage(r)
        score = float(r.combined_score)
        contra_count = len(r.contradictions or [])

        if level is not None and lvl.lower() != level.lower():
            continue

        items.append({
            "id": r.id,
            "pipeline_run_id": r.pipeline_run_id,
            "actors": {
                "actor_a": {
                    "id": r.actor_a.id,
                    "username": r.actor_a.username,
                    "marketplace": r.actor_a.marketplace.name if r.actor_a.marketplace else "Unknown",
                },
                "actor_b": {
                    "id": r.actor_b.id,
                    "username": r.actor_b.username,
                    "marketplace": r.actor_b.marketplace.name if r.actor_b.marketplace else "Unknown",
                },
            },
            "combined_score": round(score, 4),
            "level": lvl,
            "coverage": round(coverage, 4),
            "dimension_scores": r.dimension_scores,
            "contradiction_count": contra_count,
        })

    total = len(items)
    start_idx = (page - 1) * page_size
    paginated_items = items[start_idx : start_idx + page_size]

    return {
        "items": paginated_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "run_id": target_run_id,
    }


def get_correlation_detail(
    db: Session,
    investigation_id: int,
    actor_a_id: int,
    actor_b_id: int,
    user: User,
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Retrieve full detail for a specific correlated actor pair."""
    _verify_investigation_access(db, investigation_id, user)

    a = min(actor_a_id, actor_b_id)
    b = max(actor_a_id, actor_b_id)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)
    if not target_run_id:
        raise APIException(code="NOT_FOUND", message="No completed pipeline run found for case.", status_code=404)

    corr = db.execute(
        select(CorrelationResult)
        .options(
            joinedload(CorrelationResult.actor_a).joinedload(ThreatActor.marketplace),
            joinedload(CorrelationResult.actor_b).joinedload(ThreatActor.marketplace),
        )
        .where(
            CorrelationResult.pipeline_run_id == target_run_id,
            CorrelationResult.actor_a_id == a,
            CorrelationResult.actor_b_id == b,
        )
    ).unique().scalar_one_or_none()

    if not corr:
        raise APIException(
            code="NOT_FOUND",
            message=f"No correlation record found for actors {a} and {b} in run {target_run_id}.",
            status_code=404,
        )

    # Query all evidence records for this pair (both supporting and contradicting)
    ev_records = db.execute(
        select(EvidenceRecord)
        .options(
            joinedload(EvidenceRecord.sources).joinedload(EvidenceSource.post).joinedload(Post.marketplace),
            joinedload(EvidenceRecord.sources).joinedload(EvidenceSource.indicator),
        )
        .where(
            EvidenceRecord.pipeline_run_id == target_run_id,
            EvidenceRecord.actor_a_id == a,
            EvidenceRecord.actor_b_id == b,
        )
        .order_by(EvidenceRecord.direction.asc(), EvidenceRecord.strength.desc())
    ).unique().scalars().all()

    evidence_list: List[Dict[str, Any]] = []
    for ev in ev_records:
        src_items = []
        for src in ev.sources:
            p = src.post
            ind = src.indicator
            src_items.append({
                "post": {
                    "id": p.id,
                    "author": p.author_username,
                    "marketplace": p.marketplace.name if p and p.marketplace else "Unknown",
                    "excerpt": p.content[:200] + ("..." if len(p.content) > 200 else "") if p and p.content else "",
                } if p else None,
                "indicator": {
                    "id": ind.id,
                    "type": ind.indicator_type.value if hasattr(ind.indicator_type, "value") else str(ind.indicator_type),
                    "normalised_value": ind.normalised_value,
                } if ind else None,
            })

        evidence_list.append({
            "id": ev.id,
            "dimension": ev.dimension.value if hasattr(ev.dimension, "value") else str(ev.dimension),
            "evidence_type": ev.evidence_type,
            "direction": ev.direction.value if hasattr(ev.direction, "value") else str(ev.direction),
            "strength": float(ev.strength),
            "explanation": ev.explanation,
            "details": ev.details,
            "sources": src_items,
        })

    lvl, coverage = compute_correlation_level_and_coverage(corr)
    score = float(corr.combined_score)

    return {
        "id": corr.id,
        "pipeline_run_id": corr.pipeline_run_id,
        "actors": {
            "actor_a": {
                "id": corr.actor_a.id,
                "username": corr.actor_a.username,
                "marketplace": corr.actor_a.marketplace.name if corr.actor_a.marketplace else "Unknown",
            },
            "actor_b": {
                "id": corr.actor_b.id,
                "username": corr.actor_b.username,
                "marketplace": corr.actor_b.marketplace.name if corr.actor_b.marketplace else "Unknown",
            },
        },
        "combined_score": round(score, 4),
        "level": lvl,
        "coverage": round(coverage, 4),
        "dimension_scores": corr.dimension_scores,
        "contributions": corr.contributions,
        "missing_dimensions": corr.missing_dimensions,
        "contradictions": corr.contradictions,
        "evidence": evidence_list,
    }


def get_investigation_actors_analysis(
    db: Session,
    investigation_id: int,
    user: User,
    run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieve per-actor writeprint features, tfidf summary, and behaviour profile."""
    _verify_investigation_access(db, investigation_id, user)

    target_run_id = run_id or get_latest_completed_run_id(db, investigation_id)
    if not target_run_id:
        return []

    results = db.execute(
        select(AnalysisResult)
        .options(
            joinedload(AnalysisResult.actor).joinedload(ThreatActor.marketplace)
        )
        .where(
            AnalysisResult.pipeline_run_id == target_run_id,
            AnalysisResult.actor_id.is_not(None),
        )
    ).unique().scalars().all()

    actors_map: Dict[int, Dict[str, Any]] = {}

    for r in results:
        aid = r.actor_id
        if aid not in actors_map:
            actor = r.actor
            actors_map[aid] = {
                "actor_id": aid,
                "username": actor.username if actor else f"Actor #{aid}",
                "marketplace": actor.marketplace.name if actor and actor.marketplace else "Unknown",
                "stylometry": {},
                "tfidf_summary": [],
                "behaviour": {},
            }

        atype = r.analysis_type.value if hasattr(r.analysis_type, "value") else str(r.analysis_type)
        if atype == "stylometry_features":
            actors_map[aid]["stylometry"] = r.result
        elif atype == "tfidf_summary":
            actors_map[aid]["tfidf_summary"] = r.result.get("top_terms", [])
        elif atype == "behaviour_profile":
            actors_map[aid]["behaviour"] = r.result

    return sorted(list(actors_map.values()), key=lambda x: x["actor_id"])


def stateless_stylometry_compare(samples: List[Dict[str, str]]) -> Dict[str, Any]:
    """Execute stateless TF-IDF and feature vector comparisons across submitted text samples."""
    sample_analyses: List[Dict[str, Any]] = []
    docs: Dict[int, str] = {}
    word_counts: Dict[int, int] = {}
    sufficiencies: Dict[int, str] = {}
    features: Dict[int, Dict[str, float]] = {}
    fw_features: Dict[int, Dict[str, float]] = {}

    for idx, s in enumerate(samples):
        text = s["text"]
        label = s["label"]
        words = tokenize_words(text)
        sentences = tokenize_sentences(text)
        wc = len(words)
        suff = get_text_sufficiency(wc, min_sufficient=300, min_limited=100)

        gen_feat, fw_feat = extract_actor_features(text, words, sentences, 1)

        docs[idx] = text
        word_counts[idx] = wc
        sufficiencies[idx] = suff
        features[idx] = gen_feat
        fw_features[idx] = fw_feat

        sample_analyses.append({
            "label": label,
            "word_count": wc,
            "sufficiency": suff,
            "features": gen_feat,
        })

    _, _, pair_records, _ = compare_actors_stylometry(
        actor_docs=docs,
        actor_word_counts=word_counts,
        actor_sufficiencies={idx: "sufficient" for idx in docs},  # Compare all submitted samples
        actor_features=features,
        actor_fw_features=fw_features,
    )

    formatted_pairs: List[Dict[str, Any]] = []
    for p in pair_records:
        idx_a = p["actor_a_id"]
        idx_b = p["actor_b_id"]
        formatted_pairs.append({
            "sample_a": samples[idx_a]["label"],
            "sample_b": samples[idx_b]["label"],
            "char_ngram": p["char_ngram"],
            "word_ngram": p["word_ngram"],
            "function_words": p["function_words"],
            "feature_vector": p["feature_vector"],
            "overall": p["overall"],
            "shared_top_terms": p["shared_top_terms"],
        })

    caveats = [
        "TF-IDF vectorizer was fitted exclusively over the submitted sample set.",
        "Results on short texts (< 300 words) are statistically volatile and unreliable.",
        "Style similarity is heuristic evidence and must not be interpreted as definitive proof of identity.",
    ]

    return {
        "samples": sample_analyses,
        "pairwise_similarities": formatted_pairs,
        "caveats": caveats,
    }

