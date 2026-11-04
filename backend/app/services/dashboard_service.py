"""Business logic and aggregate queries for Dashboard summary metrics."""

from decimal import Decimal
from typing import Any, Dict, List
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.correlation_result import CorrelationResult
from app.models.dataset import Dataset
from app.models.extracted_indicator import ExtractedIndicator
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun
from app.models.post import Post
from app.models.user import User, UserRole


def get_dashboard_summary(db: Session, user: User) -> Dict[str, Any]:
    """Calculate dashboard summary metrics, recent investigations, and pipeline runs."""
    is_admin = user.role == UserRole.ADMIN

    # 1. Total Investigations
    inv_count_stmt = select(func.count(Investigation.id))
    if not is_admin:
        inv_count_stmt = inv_count_stmt.where(Investigation.created_by == user.id)
    total_investigations = db.execute(inv_count_stmt).scalar() or 0

    # 2. Total Collected Posts
    if is_admin:
        post_count_stmt = select(func.count(Post.id))
    else:
        post_count_stmt = (
            select(func.count(distinct(Post.id)))
            .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
            .join(Investigation, InvestigationDataset.investigation_id == Investigation.id)
            .where(Investigation.created_by == user.id)
        )
    total_posts = db.execute(post_count_stmt).scalar() or 0

    # 3. Total Extracted Indicators
    if is_admin:
        indicator_count_stmt = select(func.count(ExtractedIndicator.id))
    else:
        indicator_count_stmt = (
            select(func.count(distinct(ExtractedIndicator.id)))
            .join(Post, ExtractedIndicator.post_id == Post.id)
            .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
            .join(Investigation, InvestigationDataset.investigation_id == Investigation.id)
            .where(Investigation.created_by == user.id)
        )
    total_indicators = db.execute(indicator_count_stmt).scalar() or 0

    # 4. Potential Linkages (Correlation results linked to user's investigations)
    from app.services.scoring_config_service import get_or_create_default
    active_cfg = get_or_create_default(db)
    scoring_cfg = active_cfg.thresholds.get("scoring", {}) if active_cfg.thresholds else {}
    pot_link_thresh = float(scoring_cfg.get("potential_link", 0.45))

    latest_run_subq = (
        select(
            PipelineRun.investigation_id,
            func.max(PipelineRun.id).label("max_run_id"),
        )
        .where(PipelineRun.status == "completed")
        .group_by(PipelineRun.investigation_id)
        .subquery()
    )

    linkage_count_stmt = (
        select(func.count(CorrelationResult.id))
        .join(latest_run_subq, CorrelationResult.pipeline_run_id == latest_run_subq.c.max_run_id)
        .join(Investigation, latest_run_subq.c.investigation_id == Investigation.id)
        .where(CorrelationResult.combined_score >= Decimal(str(pot_link_thresh)))
    )
    if not is_admin:
        linkage_count_stmt = linkage_count_stmt.where(Investigation.created_by == user.id)

    total_potential_linkages = db.execute(linkage_count_stmt).scalar() or 0

    # 5. Total Datasets (Scoped)
    if is_admin:
        ds_count_stmt = select(func.count(Dataset.id))
    else:
        ds_count_stmt = (
            select(func.count(distinct(Dataset.id)))
            .join(InvestigationDataset, Dataset.id == InvestigationDataset.dataset_id)
            .join(Investigation, InvestigationDataset.investigation_id == Investigation.id)
            .where(Investigation.created_by == user.id)
        )
    total_datasets = db.execute(ds_count_stmt).scalar() or 0

    # 6. Total Marketplaces (Scoped)
    if is_admin:
        mkt_count_stmt = select(func.count(Marketplace.id))
    else:
        mkt_count_stmt = (
            select(func.count(distinct(Marketplace.id)))
            .join(Post, Marketplace.id == Post.marketplace_id)
            .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
            .join(Investigation, InvestigationDataset.investigation_id == Investigation.id)
            .where(Investigation.created_by == user.id)
        )
    total_marketplaces = db.execute(mkt_count_stmt).scalar() or 0

    # 5. Recent Investigations (Up to 5)
    recent_inv_stmt = select(Investigation)
    if not is_admin:
        recent_inv_stmt = recent_inv_stmt.where(Investigation.created_by == user.id)
    recent_inv_stmt = recent_inv_stmt.order_by(Investigation.created_at.desc()).limit(5)
    recent_invs = db.execute(recent_inv_stmt).scalars().all()

    recent_investigations: List[Dict[str, Any]] = [
        {
            "id": inv.id,
            "title": inv.title,
            "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
        }
        for inv in recent_invs
    ]

    # 6. Recent Correlation Activity / Pipeline Runs (Up to 5)
    recent_run_stmt = (
        select(PipelineRun)
        .options(joinedload(PipelineRun.investigation))
    )
    if not is_admin:
        recent_run_stmt = recent_run_stmt.join(Investigation).where(Investigation.created_by == user.id)
    recent_run_stmt = recent_run_stmt.order_by(PipelineRun.created_at.desc()).limit(5)
    recent_runs = db.execute(recent_run_stmt).scalars().all()

    recent_correlation_activity: List[Dict[str, Any]] = [
        {
            "id": run.id,
            "investigation_id": run.investigation_id,
            "investigation_title": run.investigation.title if run.investigation else f"Investigation #{run.investigation_id}",
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }
        for run in recent_runs
    ]

    return {
        "totals": {
            "investigations": total_investigations,
            "posts": total_posts,
            "datasets": total_datasets,
            "marketplaces": total_marketplaces,
            "indicators": total_indicators,
            "potential_linkages": total_potential_linkages,
        },
        "recent_investigations": recent_investigations,
        "recent_correlation_activity": recent_correlation_activity,
    }

