"""Pipeline orchestration service managing background analysis runs, stages, and execution lifecycle."""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import time
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.analysis.behaviour import (
    compare_actors_behaviour,
    compute_actor_behaviour_profile,
)
from app.analysis.matching.crypto import CRYPTO_INDICATOR_TYPES, match_cryptographic
from app.analysis.matching.infrastructure import INFRA_INDICATOR_TYPES, match_infrastructure
from app.analysis.matching.models import IndicatorRecord
from app.analysis.scoring import calculate_pair_score
from app.analysis.stylometry import (
    compare_actors_stylometry,
    extract_actor_features,
    get_text_sufficiency,
    mask_post_content,
    tokenize_sentences,
    tokenize_words,
)
from app.core.exceptions import APIException
from app.db.session import SessionLocal
from app.models.analysis_result import AnalysisResult, AnalysisType
from app.models.correlation_result import CorrelationResult
from app.models.evidence_record import EvidenceDimension, EvidenceDirection, EvidenceRecord
from app.models.evidence_source import EvidenceSource
from app.models.extracted_indicator import ExtractedIndicator
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_stage_run import PipelineStage, PipelineStageRun, PipelineStageStatus
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole
from app.services.pipeline_stages import (
    STAGE_REGISTRY,
    get_available_stage_names,
)
from app.services.scoring_config_service import DEFAULT_THRESHOLDS, get_or_create_default


def _verify_investigation_access(db: Session, investigation_id: int, user: User) -> Investigation:
    """Verify investigation exists and user has authorization to view or execute it."""
    inv = db.get(Investigation, investigation_id)
    if not inv:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    if user.role != UserRole.ADMIN and inv.created_by != user.id:
        raise APIException(code="NOT_FOUND", message="Investigation not found.", status_code=404)
    return inv


def create_pipeline_run(
    db: Session,
    investigation_id: int,
    user: User,
    requested_stages: Optional[List[str]] = None,
) -> PipelineRun:
    """Validate prerequisites and queue a new pipeline execution run."""
    _verify_investigation_access(db, investigation_id, user)

    # Check for active running or queued execution
    active_run = db.execute(
        select(PipelineRun).where(
            PipelineRun.investigation_id == investigation_id,
            PipelineRun.status.in_([PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING]),
        )
    ).scalar_one_or_none()

    if active_run:
        raise APIException(
            code="RUN_IN_PROGRESS",
            message="A pipeline run is already active for this investigation.",
            status_code=409,
        )

    # Verify investigation has data (posts and extracted indicators)
    posts_count = db.scalar(
        select(func.count(Post.id))
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id == investigation_id)
    ) or 0

    indicators_count = db.scalar(
        select(func.count(ExtractedIndicator.id))
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id == investigation_id)
    ) or 0

    if posts_count == 0 or indicators_count == 0:
        raise APIException(
            code="NO_DATA",
            message="Investigation has no posts or extracted indicators to analyze.",
            status_code=422,
        )

    # Determine stage execution sequence
    available_names = get_available_stage_names()
    if not requested_stages:
        stages_to_run = available_names
    else:
        for stg in requested_stages:
            if stg not in STAGE_REGISTRY or not STAGE_REGISTRY[stg]["available"]:
                raise APIException(
                    code="INVALID_STAGE",
                    message=f"Pipeline stage '{stg}' is invalid or unavailable.",
                    status_code=422,
                )
        stages_to_run = requested_stages

    # Get active scoring configuration
    active_cfg = get_or_create_default(db)

    # Initialize PipelineRun
    run = PipelineRun(
        investigation_id=investigation_id,
        scoring_config_id=active_cfg.id,
        status=PipelineRunStatus.QUEUED,
        triggered_by=user.id,
    )
    db.add(run)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise APIException(
            code="RUN_IN_PROGRESS",
            message="A pipeline run is already active for this investigation.",
            status_code=409,
        )

    # Add PipelineStageRun records in order
    for stg_name in stages_to_run:
        stage_run = PipelineStageRun(
            pipeline_run_id=run.id,
            stage=PipelineStage(stg_name),
            status=PipelineStageStatus.PENDING,
            items_processed=0,
            summary={},
        )
        db.add(stage_run)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIException(
            code="RUN_IN_PROGRESS",
            message="A pipeline run is already active for this investigation.",
            status_code=409,
        )

    db.refresh(run)
    return run


def run_pipeline_job(run_id: int, session: Optional[Session] = None) -> None:
    """Execute pipeline job. In background or production uses its own session; in tests supports session override."""
    if session is not None:
        _execute_pipeline_job(run_id, session)
        return

    from app.db.session import get_db
    try:
        from app.main import app
        if get_db in app.dependency_overrides:
            test_gen = app.dependency_overrides[get_db]()
            test_db = next(test_gen)
            _execute_pipeline_job(run_id, test_db)
            return
    except Exception:
        pass

    with SessionLocal() as db:
        _execute_pipeline_job(run_id, db)


def _execute_pipeline_job(run_id: int, db: Session) -> None:
    """Internal implementation executing all queued pipeline stages sequentially."""
    run = db.execute(
        select(PipelineRun)
        .options(
            joinedload(PipelineRun.stage_runs),
            joinedload(PipelineRun.scoring_config),
        )
        .where(PipelineRun.id == run_id)
    ).unique().scalar_one_or_none()

    if not run:
        return

    if run.status in (PipelineRunStatus.RUNNING, PipelineRunStatus.COMPLETED):
        return

    run.status = PipelineRunStatus.RUNNING
    run.started_at = datetime.now(timezone.utc)
    db.commit()

    # Capture input data snapshot
    dataset_ids = sorted(
        db.scalars(
            select(InvestigationDataset.dataset_id).where(
                InvestigationDataset.investigation_id == run.investigation_id
            )
        ).all()
    )
    posts_count = (
        db.scalar(
            select(func.count(Post.id))
            .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
            .where(InvestigationDataset.investigation_id == run.investigation_id)
        )
        or 0
    )
    indicators_count = (
        db.scalar(
            select(func.count(ExtractedIndicator.id))
            .join(Post, ExtractedIndicator.post_id == Post.id)
            .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
            .where(InvestigationDataset.investigation_id == run.investigation_id)
        )
        or 0
    )
    input_snapshot = {
        "dataset_ids": dataset_ids,
        "posts": posts_count,
        "indicators": indicators_count,
    }

    # Query all indicator records for this investigation
    indicator_query = (
        select(
            ExtractedIndicator.id,
            ExtractedIndicator.post_id,
            ExtractedIndicator.indicator_type,
            ExtractedIndicator.normalised_value,
            ExtractedIndicator.confidence,
            ExtractedIndicator.details,
            Post.actor_id,
            Post.marketplace_id,
            Post.posted_at,
        )
        .join(Post, ExtractedIndicator.post_id == Post.id)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id == run.investigation_id)
    )
    ind_rows = db.execute(indicator_query).all()
    indicator_records = [
        IndicatorRecord(
            indicator_id=row[0],
            post_id=row[1],
            indicator_type=row[2].value if hasattr(row[2], "value") else str(row[2]),
            normalised_value=row[3],
            confidence=row[4],
            details=row[5] or {},
            actor_id=row[6],
            marketplace_id=row[7],
            posted_at=row[8],
        )
        for row in ind_rows
    ]

    # Query metadata for all actors in the investigation
    actors_query = (
        select(ThreatActor.id, ThreatActor.username, Marketplace.name)
        .join(Marketplace, ThreatActor.marketplace_id == Marketplace.id)
        .join(Post, Post.actor_id == ThreatActor.id)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id == run.investigation_id)
        .distinct()
    )
    actor_rows = db.execute(actors_query).all()
    actors_info = {
        row[0]: {"username": row[1], "marketplace_name": row[2]} for row in actor_rows
    }
    all_actor_ids = set(actors_info.keys())

    # Query all post entities with their indicators for stylometry and behaviour
    post_entities = db.execute(
        select(Post)
        .options(joinedload(Post.indicators))
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id == run.investigation_id)
    ).unique().scalars().all()

    actor_posts_map: Dict[int, List[Post]] = defaultdict(list)
    for p in post_entities:
        if p.actor_id:
            actor_posts_map[p.actor_id].append(p)

    # Config thresholds and weights
    scoring_thresholds = (
        run.scoring_config.thresholds if run.scoring_config else DEFAULT_THRESHOLDS
    )
    scoring_weights = (
        run.scoring_config.weights if run.scoring_config and run.scoring_config.weights else DEFAULT_WEIGHTS
    )

    has_failed = False
    sorted_stages = sorted(run.stage_runs, key=lambda s: s.id)

    # Shared stage cache across sequence
    actor_sufficiencies: Dict[int, str] = {}
    actor_word_counts: Dict[int, int] = {}
    actor_profiles: Dict[int, Dict[str, Any]] = {}
    style_pair_z_map: Dict[Tuple[int, int], float] = {}
    behaviour_pair_z_map: Dict[Tuple[int, int], float] = {}
    behaviour_pair_records_map: Dict[Tuple[int, int], Dict[str, Any]] = {}

    for stage_run in sorted_stages:
        if has_failed:
            stage_run.status = PipelineStageStatus.SKIPPED
            stage_run.finished_at = datetime.now(timezone.utc)
            db.commit()
            continue

        stage_run.status = PipelineStageStatus.RUNNING
        stage_run.started_at = datetime.now(timezone.utc)
        db.commit()

        t0 = time.perf_counter()
        stage_val = stage_run.stage.value
        try:
            if stage_val == "crypto_matching":
                handler = STAGE_REGISTRY.get("crypto_matching", {}).get("handler", match_cryptographic)
                candidates, suppressed, coverage = handler(
                    indicator_records,
                    scoring_thresholds,
                    actors_info=actors_info,
                    all_actor_ids=all_actor_ids,
                )

                evidence_by_type: Dict[str, int] = defaultdict(int)
                for cand in candidates:
                    ev = EvidenceRecord(
                        pipeline_run_id=run.id,
                        actor_a_id=cand.actor_a_id,
                        actor_b_id=cand.actor_b_id,
                        dimension=EvidenceDimension.CRYPTOGRAPHIC,
                        evidence_type=cand.evidence_type,
                        direction=EvidenceDirection.SUPPORTING,
                        strength=Decimal(str(cand.strength)),
                        explanation=cand.explanation,
                        details=cand.details,
                    )
                    db.add(ev)
                    db.flush()
                    evidence_by_type[cand.evidence_type] += 1

                    added_pairs: Set[tuple] = set()
                    for p_id in cand.source_post_ids:
                        matching_inds = [
                            r.indicator_id
                            for r in indicator_records
                            if r.post_id == p_id and r.indicator_id in cand.source_indicator_ids
                        ]
                        if matching_inds:
                            for ind_id in matching_inds:
                                pair = (p_id, ind_id)
                                if pair not in added_pairs:
                                    db.add(EvidenceSource(evidence_id=ev.id, post_id=p_id, indicator_id=ind_id))
                                    added_pairs.add(pair)
                        else:
                            pair = (p_id, None)
                            if pair not in added_pairs:
                                db.add(EvidenceSource(evidence_id=ev.id, post_id=p_id, indicator_id=None))
                                added_pairs.add(pair)

                duration_ms = int((time.perf_counter() - t0) * 1000)
                indicators_considered = len([r for r in indicator_records if r.indicator_type in CRYPTO_INDICATOR_TYPES])

                stage_run.summary = {
                    "input_snapshot": input_snapshot,
                    "actors_considered": len(all_actor_ids),
                    "indicators_considered": indicators_considered,
                    "evidence_created": len(candidates),
                    "evidence_by_type": dict(evidence_by_type),
                    "suppressed_common_indicators": [
                        {
                            "type": s.type,
                            "normalised_value": s.normalised_value,
                            "actor_count": s.actor_count,
                            "marketplace_count": s.marketplace_count,
                        }
                        for s in suppressed[:50]
                    ],
                    "coverage": {
                        "actors_total": coverage["actors_total"],
                        "actors_with_dimension_indicators": coverage["actors_with_dimension_indicators"],
                    },
                    "duration_ms": duration_ms,
                }
                stage_run.items_processed = len(candidates)

            elif stage_val == "infrastructure_matching":
                handler = STAGE_REGISTRY.get("infrastructure_matching", {}).get("handler", match_infrastructure)
                candidates, suppressed, coverage = handler(
                    indicator_records,
                    scoring_thresholds,
                    actors_info=actors_info,
                    all_actor_ids=all_actor_ids,
                )

                evidence_by_type = defaultdict(int)
                for cand in candidates:
                    ev = EvidenceRecord(
                        pipeline_run_id=run.id,
                        actor_a_id=cand.actor_a_id,
                        actor_b_id=cand.actor_b_id,
                        dimension=EvidenceDimension.INFRASTRUCTURE,
                        evidence_type=cand.evidence_type,
                        direction=EvidenceDirection.SUPPORTING,
                        strength=Decimal(str(cand.strength)),
                        explanation=cand.explanation,
                        details=cand.details,
                    )
                    db.add(ev)
                    db.flush()
                    evidence_by_type[cand.evidence_type] += 1

                    added_pairs = set()
                    for p_id in cand.source_post_ids:
                        matching_inds = [
                            r.indicator_id
                            for r in indicator_records
                            if r.post_id == p_id and r.indicator_id in cand.source_indicator_ids
                        ]
                        if matching_inds:
                            for ind_id in matching_inds:
                                pair = (p_id, ind_id)
                                if pair not in added_pairs:
                                    db.add(EvidenceSource(evidence_id=ev.id, post_id=p_id, indicator_id=ind_id))
                                    added_pairs.add(pair)
                        else:
                            pair = (p_id, None)
                            if pair not in added_pairs:
                                db.add(EvidenceSource(evidence_id=ev.id, post_id=p_id, indicator_id=None))
                                added_pairs.add(pair)

                duration_ms = int((time.perf_counter() - t0) * 1000)
                indicators_considered = len([r for r in indicator_records if r.indicator_type in INFRA_INDICATOR_TYPES])

                stage_run.summary = {
                    "input_snapshot": input_snapshot,
                    "actors_considered": len(all_actor_ids),
                    "indicators_considered": indicators_considered,
                    "evidence_created": len(candidates),
                    "evidence_by_type": dict(evidence_by_type),
                    "suppressed_common_indicators": [
                        {
                            "type": s.type,
                            "normalised_value": s.normalised_value,
                            "actor_count": s.actor_count,
                            "marketplace_count": s.marketplace_count,
                        }
                        for s in suppressed[:50]
                    ],
                    "coverage": {
                        "actors_total": coverage["actors_total"],
                        "actors_with_dimension_indicators": coverage["actors_with_dimension_indicators"],
                    },
                    "duration_ms": duration_ms,
                }
                stage_run.items_processed = len(candidates)

            elif stage_val == "stylometric_analysis":
                style_cfg = scoring_thresholds.get("stylometry", {})
                min_sufficient = style_cfg.get("min_words_sufficient", 300)
                min_limited = style_cfg.get("min_words_limited", 100)
                z_supp = float(style_cfg.get("z_support", 1.5))
                z_fl = float(style_cfg.get("z_full", 3.5))
                style_weights = style_cfg.get("weights")

                actor_docs: Dict[int, str] = {}
                actor_features: Dict[int, Dict[str, float]] = {}
                actor_fw_features: Dict[int, Dict[str, float]] = {}
                insufficient_actors: List[int] = []

                for aid in sorted(list(all_actor_ids)):
                    posts = actor_posts_map.get(aid, [])
                    masked_texts = []
                    for p in posts:
                        p_inds = [
                            {
                                "span_start": ind.span_start,
                                "span_end": ind.span_end,
                                "indicator_type": ind.indicator_type.value if hasattr(ind.indicator_type, "value") else str(ind.indicator_type),
                            }
                            for ind in (p.indicators or [])
                        ]
                        masked_texts.append(mask_post_content(p.content or "", p_inds))

                    combined_doc = "\n\n".join(masked_texts)
                    words = tokenize_words(combined_doc)
                    sentences = tokenize_sentences(combined_doc)
                    wc = len(words)
                    suff = get_text_sufficiency(wc, min_sufficient, min_limited)

                    actor_docs[aid] = combined_doc
                    actor_word_counts[aid] = wc
                    actor_sufficiencies[aid] = suff

                    if suff in ("sufficient", "limited"):
                        feat, fw_feat = extract_actor_features(combined_doc, words, sentences, len(posts))
                        actor_features[aid] = feat
                        actor_fw_features[aid] = fw_feat
                    else:
                        insufficient_actors.append(aid)

                # Pairwise comparison
                cand_evs, tfidf_summaries, pair_records, run_metrics = compare_actors_stylometry(
                    actor_docs=actor_docs,
                    actor_word_counts=actor_word_counts,
                    actor_sufficiencies=actor_sufficiencies,
                    actor_features=actor_features,
                    actor_fw_features=actor_fw_features,
                    config_weights=style_weights,
                    z_support=z_supp,
                    z_full=z_fl,
                )

                # Store z-scores for scoring stage
                for p in pair_records:
                    style_pair_z_map[(p["actor_a_id"], p["actor_b_id"])] = p["z"]

                # Store analysis_results per actor
                for aid in sorted(list(all_actor_ids)):
                    db.add(
                        AnalysisResult(
                            pipeline_run_id=run.id,
                            actor_id=aid,
                            analysis_type=AnalysisType.STYLOMETRY_FEATURES,
                            result={
                                "features": actor_features.get(aid, {}),
                                "word_count": actor_word_counts.get(aid, 0),
                                "sufficiency": actor_sufficiencies.get(aid, "insufficient"),
                            },
                        )
                    )
                    db.add(
                        AnalysisResult(
                            pipeline_run_id=run.id,
                            actor_id=aid,
                            analysis_type=AnalysisType.TFIDF_SUMMARY,
                            result={"top_terms": tfidf_summaries.get(aid, [])},
                        )
                    )

                # Store all pair similarities in one analysis_results row
                db.add(
                    AnalysisResult(
                        pipeline_run_id=run.id,
                        actor_id=None,
                        post_id=None,
                        analysis_type=AnalysisType.OTHER,
                        result={"kind": "stylometry_pairs", "pairs": pair_records, "baseline": run_metrics["baseline"], "spread": run_metrics["spread"]},
                    )
                )

                # Store supporting evidence records
                for cand in cand_evs:
                    ev = EvidenceRecord(
                        pipeline_run_id=run.id,
                        actor_a_id=cand["actor_a_id"],
                        actor_b_id=cand["actor_b_id"],
                        dimension=EvidenceDimension.STYLOMETRIC,
                        evidence_type=cand["evidence_type"],
                        direction=EvidenceDirection.SUPPORTING,
                        strength=Decimal(str(cand["strength"])),
                        explanation=cand["explanation"],
                        details=cand["details"],
                    )
                    db.add(ev)
                    db.flush()

                    # Link evidence sources to sample posts
                    src_posts = [p.id for p in actor_posts_map.get(cand["actor_a_id"], [])[:2]] + [
                        p.id for p in actor_posts_map.get(cand["actor_b_id"], [])[:2]
                    ]
                    for pid in src_posts:
                        db.add(EvidenceSource(evidence_id=ev.id, post_id=pid, indicator_id=None))

                duration_ms = int((time.perf_counter() - t0) * 1000)
                stage_run.summary = {
                    "input_snapshot": input_snapshot,
                    "actors_compared": run_metrics["actors_compared"],
                    "actors_insufficient": insufficient_actors,
                    "baseline": run_metrics["baseline"],
                    "spread": run_metrics["spread"],
                    "pairs_supporting": run_metrics["pairs_supporting"],
                    "pairs_compared": run_metrics["pairs_compared"],
                    "coverage": {
                        "actors_total": len(all_actor_ids),
                        "actors_sufficient": len(all_actor_ids) - len(insufficient_actors),
                    },
                    "duration_ms": duration_ms,
                }
                stage_run.items_processed = run_metrics["actors_compared"]

            elif stage_val == "behavioural_analysis":
                behav_cfg = scoring_thresholds.get("behaviour", {})
                min_sufficient = behav_cfg.get("min_posts_sufficient", 10)
                min_limited = behav_cfg.get("min_posts_limited", 5)
                z_supp = float(behav_cfg.get("z_support", 1.5))
                z_fl = float(behav_cfg.get("z_full", 3.5))
                behav_weights = behav_cfg.get("weights")

                missing_timestamps_count = 0
                insufficient_behaviour_actors: List[int] = []

                for aid in sorted(list(all_actor_ids)):
                    posts = actor_posts_map.get(aid, [])
                    timestamps = [p.posted_at for p in posts if p.posted_at is not None]
                    missing_timestamps_count += sum(1 for p in posts if p.posted_at is None)

                    prof = compute_actor_behaviour_profile(timestamps, min_sufficient, min_limited)
                    actor_profiles[aid] = prof
                    if prof.get("sufficiency") == "insufficient":
                        insufficient_behaviour_actors.append(aid)

                # Pairwise comparison
                cand_evs, pair_records, run_metrics = compare_actors_behaviour(
                    actor_profiles=actor_profiles,
                    config_weights=behav_weights,
                    z_support=z_supp,
                    z_full=z_fl,
                )

                # Store z-scores for scoring stage
                for p in pair_records:
                    behaviour_pair_z_map[(p["actor_a_id"], p["actor_b_id"])] = p["z"]
                    behaviour_pair_records_map[(p["actor_a_id"], p["actor_b_id"])] = p

                # Store analysis_results per actor
                for aid in sorted(list(all_actor_ids)):
                    db.add(
                        AnalysisResult(
                            pipeline_run_id=run.id,
                            actor_id=aid,
                            analysis_type=AnalysisType.BEHAVIOUR_PROFILE,
                            result=actor_profiles.get(aid, {}),
                        )
                    )

                # Store all pair similarities in one analysis_results row
                db.add(
                    AnalysisResult(
                        pipeline_run_id=run.id,
                        actor_id=None,
                        post_id=None,
                        analysis_type=AnalysisType.OTHER,
                        result={"kind": "behaviour_pairs", "pairs": pair_records, "baseline": run_metrics["baseline"], "spread": run_metrics["spread"]},
                    )
                )

                # Store supporting evidence records
                for cand in cand_evs:
                    ev = EvidenceRecord(
                        pipeline_run_id=run.id,
                        actor_a_id=cand["actor_a_id"],
                        actor_b_id=cand["actor_b_id"],
                        dimension=EvidenceDimension.BEHAVIOURAL,
                        evidence_type=cand["evidence_type"],
                        direction=EvidenceDirection.SUPPORTING,
                        strength=Decimal(str(cand["strength"])),
                        explanation=cand["explanation"],
                        details=cand["details"],
                    )
                    db.add(ev)
                    db.flush()

                    src_posts = [p.id for p in actor_posts_map.get(cand["actor_a_id"], [])[:2]] + [
                        p.id for p in actor_posts_map.get(cand["actor_b_id"], [])[:2]
                    ]
                    for pid in src_posts:
                        db.add(EvidenceSource(evidence_id=ev.id, post_id=pid, indicator_id=None))

                duration_ms = int((time.perf_counter() - t0) * 1000)
                stage_run.summary = {
                    "input_snapshot": input_snapshot,
                    "actors_compared": run_metrics["actors_compared"],
                    "actors_insufficient": insufficient_behaviour_actors,
                    "missing_timestamps": missing_timestamps_count,
                    "baseline": run_metrics["baseline"],
                    "spread": run_metrics["spread"],
                    "pairs_supporting": run_metrics["pairs_supporting"],
                    "pairs_compared": run_metrics["pairs_compared"],
                    "coverage": {
                        "actors_total": len(all_actor_ids),
                        "actors_sufficient": len(all_actor_ids) - len(insufficient_behaviour_actors),
                    },
                    "duration_ms": duration_ms,
                }
                stage_run.items_processed = run_metrics["actors_compared"]

            elif stage_val == "scoring":
                scoring_cfg = scoring_thresholds.get("scoring", {})
                min_report_score = float(scoring_cfg.get("min_report_score", 0.20))

                # Flush all previous stage records to ensure DB visibility
                db.flush()

                # Query all supporting evidence records for this run
                supporting_evs = db.scalars(
                    select(EvidenceRecord).where(
                        EvidenceRecord.pipeline_run_id == run.id,
                        EvidenceRecord.direction == EvidenceDirection.SUPPORTING,
                    )
                ).all()

                pair_supporting_by_dim: Dict[Tuple[int, int], Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
                for ev in supporting_evs:
                    pair_key = (ev.actor_a_id, ev.actor_b_id)
                    pair_supporting_by_dim[pair_key][ev.dimension.value].append(float(ev.strength))

                # Also determine indicator presence per actor for crypto/infra
                crypto_actors = {r.actor_id for r in indicator_records if r.indicator_type in CRYPTO_INDICATOR_TYPES}
                infra_actors = {r.actor_id for r in indicator_records if r.indicator_type in INFRA_INDICATOR_TYPES}

                pairs_to_score = sorted(list(pair_supporting_by_dim.keys()))
                pairs_scored = 0
                pairs_stored = 0
                pairs_with_contradictions = 0
                levels_count: Dict[str, int] = {"strong": 0, "moderate": 0, "weak": 0, "none": 0}

                for (aid_a, aid_b) in pairs_to_score:
                    pairs_scored += 1
                    supp_dims = pair_supporting_by_dim[(aid_a, aid_b)]

                    # Build availability dict
                    dim_avail = {
                        "cryptographic": {
                            "has_data": aid_a in crypto_actors or aid_b in crypto_actors,
                        },
                        "infrastructure": {
                            "has_data": aid_a in infra_actors or aid_b in infra_actors,
                        },
                        "stylometric": {
                            "is_sufficient": (
                                actor_sufficiencies.get(aid_a) in ("sufficient", "limited")
                                and actor_sufficiencies.get(aid_b) in ("sufficient", "limited")
                            ),
                            "reason": "insufficient_text",
                        },
                        "behavioural": {
                            "is_sufficient": (
                                actor_profiles.get(aid_a, {}).get("sufficiency") in ("sufficient", "limited")
                                and actor_profiles.get(aid_b, {}).get("sufficiency") in ("sufficient", "limited")
                            ),
                            "reason": "insufficient_timestamps",
                        },
                    }

                    s_z = style_pair_z_map.get((aid_a, aid_b))
                    b_z = behaviour_pair_z_map.get((aid_a, aid_b))

                    b_rec = behaviour_pair_records_map.get((aid_a, aid_b), {})
                    b_data = {
                        "peak_a": f"{actor_profiles.get(aid_a, {}).get('peak_hour', 0):02d}:00",
                        "peak_b": f"{actor_profiles.get(aid_b, {}).get('peak_hour', 0):02d}:00",
                        "hourly": b_rec.get("hourly", 1.0),
                    }

                    scored_result = calculate_pair_score(
                        actor_a_id=aid_a,
                        actor_b_id=aid_b,
                        supporting_by_dimension=supp_dims,
                        dimension_availability=dim_avail,
                        weights=scoring_weights,
                        thresholds=scoring_thresholds,
                        style_z=s_z,
                        behaviour_z=b_z,
                        behaviour_profile_data=b_data,
                    )

                    # Persist any contradicting evidence records
                    for contra_cand in scored_result["contradicting_records"]:
                        ev_contra = EvidenceRecord(
                            pipeline_run_id=run.id,
                            actor_a_id=aid_a,
                            actor_b_id=aid_b,
                            dimension=EvidenceDimension(contra_cand["dimension"]),
                            evidence_type=contra_cand["evidence_type"],
                            direction=EvidenceDirection.CONTRADICTING,
                            strength=Decimal(str(contra_cand["strength"])),
                            explanation=contra_cand["explanation"],
                            details=contra_cand["details"],
                        )
                        db.add(ev_contra)
                        db.flush()

                        # Attach evidence sources
                        contra_posts = [p.id for p in actor_posts_map.get(aid_a, [])[:2]] + [
                            p.id for p in actor_posts_map.get(aid_b, [])[:2]
                        ]
                        for pid in contra_posts:
                            db.add(EvidenceSource(evidence_id=ev_contra.id, post_id=pid, indicator_id=None))

                        # Record evidence_id in contradiction summary
                        for c_item in scored_result["contradictions"]:
                            if c_item.get("dimension") == contra_cand["dimension"]:
                                c_item["evidence_id"] = ev_contra.id

                    lvl = scored_result["level"]
                    levels_count[lvl] = levels_count.get(lvl, 0) + 1

                    if scored_result["contradictions"]:
                        pairs_with_contradictions += 1

                    # Store in correlation_results if score >= min_report_score or contradictions
                    if scored_result["combined_score"] >= min_report_score or scored_result["contradictions"]:
                        corr = CorrelationResult(
                            pipeline_run_id=run.id,
                            actor_a_id=aid_a,
                            actor_b_id=aid_b,
                            combined_score=Decimal(str(scored_result["combined_score"])),
                            dimension_scores=scored_result["dimension_scores"],
                            contributions=scored_result["contributions"],
                            missing_dimensions=scored_result["missing_dimensions"],
                            contradictions=scored_result["contradictions"],
                            scoring_config_id=run.scoring_config_id,
                        )
                        db.add(corr)
                        pairs_stored += 1

                duration_ms = int((time.perf_counter() - t0) * 1000)
                stage_run.summary = {
                    "input_snapshot": input_snapshot,
                    "pairs_scored": pairs_scored,
                    "pairs_stored": pairs_stored,
                    "levels": levels_count,
                    "pairs_with_contradictions": pairs_with_contradictions,
                    "coverage": {
                        "pairs_total": len(pairs_to_score),
                        "pairs_scored": pairs_scored,
                    },
                    "duration_ms": duration_ms,
                }
                stage_run.items_processed = pairs_scored

            else:
                raise RuntimeError(f"Unknown pipeline stage '{stage_val}'.")

            stage_run.status = PipelineStageStatus.COMPLETED
            stage_run.finished_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as exc:
            db.rollback()
            has_failed = True
            err_msg = str(exc)
            stage_run.status = PipelineStageStatus.FAILED
            stage_run.error_message = err_msg
            stage_run.finished_at = datetime.now(timezone.utc)

            run.status = PipelineRunStatus.FAILED
            run.error_message = f"Stage '{stage_run.stage.value}' failed: {err_msg}"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()

    if not has_failed:
        run.status = PipelineRunStatus.COMPLETED
        run.finished_at = datetime.now(timezone.utc)
        db.commit()


def list_pipeline_runs(db: Session, investigation_id: int, user: User) -> List[PipelineRun]:
    """Retrieve all pipeline execution runs for an authorized investigation."""
    _verify_investigation_access(db, investigation_id, user)
    runs = db.execute(
        select(PipelineRun)
        .options(
            joinedload(PipelineRun.stage_runs),
            joinedload(PipelineRun.triggered_by_user),
        )
        .where(PipelineRun.investigation_id == investigation_id)
        .order_by(PipelineRun.created_at.desc())
    ).unique().scalars().all()
    return runs


def get_pipeline_run_detail(
    db: Session, investigation_id: int, run_id: int, user: User
) -> Dict[str, Any]:
    """Retrieve full details of a specific pipeline run, including stage statuses and staleness."""
    _verify_investigation_access(db, investigation_id, user)
    run = db.execute(
        select(PipelineRun)
        .options(
            joinedload(PipelineRun.stage_runs),
            joinedload(PipelineRun.triggered_by_user),
        )
        .where(
            PipelineRun.id == run_id,
            PipelineRun.investigation_id == investigation_id,
        )
    ).unique().scalar_one_or_none()

    if not run:
        raise APIException(code="NOT_FOUND", message="Pipeline run not found.", status_code=404)

    # Calculate whether run is stale compared to latest investigation data
    current_posts = (
        db.scalar(
            select(func.count(Post.id))
            .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
            .where(InvestigationDataset.investigation_id == investigation_id)
        )
        or 0
    )
    current_indicators = (
        db.scalar(
            select(func.count(ExtractedIndicator.id))
            .join(Post, ExtractedIndicator.post_id == Post.id)
            .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
            .where(InvestigationDataset.investigation_id == investigation_id)
        )
        or 0
    )

    snapshot: Optional[Dict[str, Any]] = None
    for stage_run in run.stage_runs:
        if stage_run.summary and "input_snapshot" in stage_run.summary:
            snapshot = stage_run.summary["input_snapshot"]
            break

    is_stale = False
    if snapshot and run.status == PipelineRunStatus.COMPLETED:
        snap_posts = snapshot.get("posts", 0)
        snap_indicators = snapshot.get("indicators", 0)
        is_stale = current_posts > snap_posts or current_indicators > snap_indicators

    return {
        "id": run.id,
        "investigation_id": run.investigation_id,
        "scoring_config_id": run.scoring_config_id,
        "status": run.status.value,
        "triggered_by": {
            "id": run.triggered_by_user.id,
            "username": run.triggered_by_user.username,
        }
        if run.triggered_by_user
        else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "error_message": run.error_message,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "is_stale": is_stale,
        "stages": [
            {
                "id": s.id,
                "stage": s.stage.value,
                "status": s.status.value,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                "items_processed": s.items_processed,
                "summary": s.summary,
                "error_message": s.error_message,
            }
            for s in sorted(run.stage_runs, key=lambda x: x.id)
        ],
    }


def recover_interrupted_pipeline_runs(session: Optional[Session] = None) -> None:
    """Startup recovery: mark any queued or running pipeline runs as failed."""
    if session is not None:
        _execute_recover_pipeline_runs(session)
        return

    from app.db.session import get_db
    try:
        from app.main import app
        if get_db in app.dependency_overrides:
            test_gen = app.dependency_overrides[get_db]()
            test_db = next(test_gen)
            _execute_recover_pipeline_runs(test_db)
            return
    except Exception:
        pass

    with SessionLocal() as db:
        _execute_recover_pipeline_runs(db)


def _execute_recover_pipeline_runs(db: Session) -> None:
    """Internal recovery execution marking active runs and their stages as failed."""
    interrupted = db.execute(
        select(PipelineRun)
        .options(joinedload(PipelineRun.stage_runs))
        .where(PipelineRun.status.in_([PipelineRunStatus.QUEUED, PipelineRunStatus.RUNNING]))
    ).unique().scalars().all()

    for run in interrupted:
        run.status = PipelineRunStatus.FAILED
        run.error_message = "Interrupted by restart"
        run.finished_at = datetime.now(timezone.utc)
        for stage_run in run.stage_runs:
            if stage_run.status in (PipelineStageStatus.RUNNING, PipelineStageStatus.PENDING):
                stage_run.status = PipelineStageStatus.FAILED
                stage_run.error_message = "Interrupted by restart"
                stage_run.finished_at = datetime.now(timezone.utc)

    db.commit()
