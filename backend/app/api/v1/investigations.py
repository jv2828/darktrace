"""API endpoints for managing threat intelligence investigations."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import success
from app.db.session import get_db
from app.models.user import User
from app.schemas.extraction import ExtractionRerunRequest
from app.schemas.ingestion import ManualPostRequest
from app.schemas.investigation import InvestigationCreateRequest
from app.schemas.pipeline import PipelineRunCreateRequest
from app.schemas.report import ReportCreateRequest
from app.services.actor_service import get_actor_profile, list_investigation_actors
from app.services.chronology_service import get_investigation_chronology
from app.services.correlation_service import (
    get_correlation_detail,
    get_investigation_actors_analysis,
    list_investigation_correlations,
)
from app.services.graph_service import get_investigation_graph
from app.services.infrastructure_service import get_investigation_infrastructure
from app.services.report_service import (
    create_investigation_report,
    get_report_file_for_download,
    list_investigation_reports,
)
from app.services.evidence_service import (
    get_evidence_detail,
    list_investigation_evidence,
    list_investigation_pairs,
)
from app.services.extraction_service import (
    get_indicators_summary,
    get_investigation_post_detail,
    list_investigation_indicators,
    rerun_investigation_extraction,
)
from app.services.ingestion_service import (
    commit_file_upload,
    commit_manual_post,
    list_investigation_datasets,
    list_investigation_posts,
    load_sample_to_investigation,
    preview_file_upload,
    preview_manual_post,
)
from app.services.investigation_service import (
    create_investigation,
    get_investigation_by_id,
    list_investigations,
)
from app.services.pipeline_service import (
    create_pipeline_run,
    get_pipeline_run_detail,
    list_pipeline_runs,
    run_pipeline_job,
)

router = APIRouter(prefix="/investigations", tags=["Investigations"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_new_investigation(
    payload: InvestigationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new investigation in draft status owned by current user."""
    data = create_investigation(db=db, user=current_user, payload=payload)
    return success(data=data)


@router.get("", status_code=status.HTTP_200_OK)
def get_investigations_list(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    q: Optional[str] = Query(None, description="Title search keyword"),
    status: Optional[str] = Query(None, description="Filter by status (draft, processing, completed, failed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List paginated investigations with search, filter, and ownership scoping."""
    items, meta = list_investigations(
        db=db,
        user=current_user,
        page=page,
        page_size=page_size,
        q=q,
        status_filter=status,
    )
    return success(data=items, meta=meta)


@router.get("/{investigation_id}", status_code=status.HTTP_200_OK)
def get_investigation_details(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details for a single investigation scoped by ownership (404 on unowned)."""
    data = get_investigation_by_id(db=db, user=current_user, investigation_id=investigation_id)
    return success(data=data)


# ---------------------------------------------------------------------------
# Ingestion Endpoints (Phase 5)
# ---------------------------------------------------------------------------

@router.post("/{investigation_id}/datasets/samples/{key}", status_code=status.HTTP_200_OK)
def load_sample_dataset_route(
    investigation_id: int,
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load a synthetic benchmark sample into the DB and link to the investigation."""
    data = load_sample_to_investigation(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        sample_key=key,
    )
    return success(data=data)


@router.post("/{investigation_id}/ingest/manual/preview", status_code=status.HTTP_200_OK)
def preview_manual_post_route(
    investigation_id: int,
    payload: ManualPostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate a single manual darknet post entry without writing to DB."""
    data = preview_manual_post(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        payload=payload.model_dump(),
    )
    return success(data=data)


@router.post("/{investigation_id}/ingest/manual/commit", status_code=status.HTTP_201_CREATED)
def commit_manual_post_route(
    investigation_id: int,
    payload: ManualPostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit a validated manual darknet post into a new manual dataset."""
    data = commit_manual_post(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        payload=payload.model_dump(),
    )
    return success(data=data)


@router.post("/{investigation_id}/ingest/file/preview", status_code=status.HTTP_200_OK)
async def preview_file_upload_route(
    investigation_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate uploaded CSV or JSON file in memory without persisting records."""
    data = await preview_file_upload(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        file=file,
    )
    return success(data=data)


@router.post("/{investigation_id}/ingest/file/commit", status_code=status.HTTP_201_CREATED)
async def commit_file_upload_route(
    investigation_id: int,
    file: UploadFile = File(...),
    on_error: str = Form("skip_invalid"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit validated CSV or JSON records into a new dataset atomically."""
    data = await commit_file_upload(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        file=file,
        on_error=on_error,
    )
    return success(data=data)


@router.get("/{investigation_id}/posts", status_code=status.HTTP_200_OK)
def get_investigation_posts_route(
    investigation_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    marketplace: Optional[str] = Query(None, description="Filter by marketplace"),
    username: Optional[str] = Query(None, description="Filter by author username"),
    q: Optional[str] = Query(None, description="Search post content keyword"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List paginated posts belonging to this investigation with filtering."""
    items, meta = list_investigation_posts(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        page=page,
        page_size=page_size,
        marketplace=marketplace,
        username=username,
        q=q,
        start_date=start_date,
        end_date=end_date,
    )
    return success(data=items, meta=meta)


@router.get("/{investigation_id}/datasets", status_code=status.HTTP_200_OK)
def get_investigation_datasets_route(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List datasets attached to this investigation with real post counts."""
    items = list_investigation_datasets(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
    )
    return success(data=items)


# ---------------------------------------------------------------------------
# Phase 6: Extraction Endpoints
# ---------------------------------------------------------------------------

@router.post("/{investigation_id}/extraction/rerun", status_code=status.HTTP_200_OK)
def rerun_extraction_route(
    investigation_id: int,
    payload: Optional[ExtractionRerunRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger indicator extraction rerun for all posts in an investigation."""
    force = payload.force if payload else False
    data = rerun_investigation_extraction(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        force=force,
    )
    return success(data=data)


@router.get("/{investigation_id}/indicators", status_code=status.HTTP_200_OK)
def get_investigation_indicators_route(
    investigation_id: int,
    type: Optional[str] = Query(None, description="Filter by indicator_type"),
    indicator_type: Optional[str] = Query(None, description="Filter by indicator_type alias"),
    q: Optional[str] = Query(None, description="Search normalized indicator value"),
    post_id: Optional[int] = Query(None, description="Filter by post ID"),
    marketplace: Optional[str] = Query(None, description="Filter by marketplace name"),
    username: Optional[str] = Query(None, description="Filter by author username"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List paginated extracted indicators for this investigation with filters."""
    selected_type = indicator_type or type
    items, meta = list_investigation_indicators(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        indicator_type=selected_type,
        q=q,
        post_id=post_id,
        marketplace=marketplace,
        username=username,
        page=page,
        page_size=page_size,
    )
    return success(data=items, meta=meta)


@router.get("/{investigation_id}/indicators/summary", status_code=status.HTTP_200_OK)
def get_indicators_summary_route(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve aggregate indicator counts by type (total and distinct)."""
    data = get_indicators_summary(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
    )
    return success(data=data)


@router.get("/{investigation_id}/posts/{post_id}", status_code=status.HTTP_200_OK)
def get_investigation_post_detail_route(
    investigation_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full post details with original text, highlighted spans, and provenance."""
    data = get_investigation_post_detail(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        post_id=post_id,
    )
    return success(data=data)


# ---------------------------------------------------------------------------
# Pipeline Execution & Analytics Routes
# ---------------------------------------------------------------------------


@router.post("/{investigation_id}/pipeline/runs", status_code=status.HTTP_202_ACCEPTED)
def trigger_pipeline_run_route(
    investigation_id: int,
    background_tasks: BackgroundTasks,
    payload: Optional[PipelineRunCreateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue a new analytical pipeline run and trigger asynchronous background execution."""
    stages = payload.stages if payload else None
    run = create_pipeline_run(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        requested_stages=stages,
    )
    background_tasks.add_task(run_pipeline_job, run.id)
    detail = get_pipeline_run_detail(db, investigation_id, run.id, current_user)
    return success(data=detail)


@router.get("/{investigation_id}/pipeline/runs", status_code=status.HTTP_200_OK)
def list_pipeline_runs_route(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all pipeline execution runs for an investigation, newest first."""
    runs = list_pipeline_runs(db, investigation_id, current_user)
    items = [
        get_pipeline_run_detail(db, investigation_id, r.id, current_user)
        for r in runs
    ]
    return success(data=items)


@router.get("/{investigation_id}/pipeline/runs/{run_id}", status_code=status.HTTP_200_OK)
def get_pipeline_run_route(
    investigation_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve specific pipeline run details, stage timings, item counts, and staleness."""
    detail = get_pipeline_run_detail(db, investigation_id, run_id, current_user)
    return success(data=detail)


# ---------------------------------------------------------------------------
# Evidence & Pair Linkage Routes
# ---------------------------------------------------------------------------


@router.get("/{investigation_id}/evidence", status_code=status.HTTP_200_OK)
def list_evidence_route(
    investigation_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    dimension: Optional[str] = Query(None, description="Evidence dimension (cryptographic, infrastructure)"),
    evidence_type: Optional[str] = Query(None, description="Specific evidence type string"),
    actor_id: Optional[int] = Query(None, description="Filter for evidence involving a threat actor ID"),
    min_strength: Optional[float] = Query(None, description="Minimum strength threshold"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List paginated evidence records supporting linkages between threat actors."""
    result = list_investigation_evidence(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        run_id=run_id,
        dimension=dimension,
        evidence_type=evidence_type,
        actor_id=actor_id,
        min_strength=min_strength,
        page=page,
        page_size=page_size,
    )
    return success(data=result["items"], meta=result["meta"])


@router.get("/{investigation_id}/evidence/{evidence_id}", status_code=status.HTTP_200_OK)
def get_evidence_detail_route(
    investigation_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full finding details, technical details JSON, and contributing source origins."""
    data = get_evidence_detail(
        db=db,
        investigation_id=investigation_id,
        evidence_id=evidence_id,
        user=current_user,
    )
    return success(data=data)


@router.get("/{investigation_id}/pairs", status_code=status.HTTP_200_OK)
def list_pairs_route(
    investigation_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve correlated actor pairs for the run, ordered by maximum evidence strength."""
    result = list_investigation_pairs(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        run_id=run_id,
    )
    return success(data=result["items"], meta={"run_id": result["run_id"]})


# ---------------------------------------------------------------------------
# Phase 8: Correlation Results & Actor Writeprint Analysis Endpoints
# ---------------------------------------------------------------------------

@router.get("/{investigation_id}/correlations", status_code=status.HTTP_200_OK)
def list_correlations_route(
    investigation_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    min_score: Optional[float] = Query(None, description="Minimum combined score threshold"),
    level: Optional[str] = Query(None, description="Filter by level: strong, moderate, weak, none"),
    actor_id: Optional[int] = Query(None, description="Filter by participating threat actor ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve stored multi-dimensional correlation results for an investigation."""
    res = list_investigation_correlations(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        run_id=run_id,
        min_score=min_score,
        level=level,
        actor_id=actor_id,
        page=page,
        page_size=page_size,
    )
    return success(
        data=res["items"],
        meta={
            "total": res["total"],
            "page": res["page"],
            "page_size": res["page_size"],
            "run_id": res["run_id"],
        },
    )


@router.get("/{investigation_id}/correlations/{actor_a}/{actor_b}", status_code=status.HTTP_200_OK)
def get_correlation_detail_route(
    investigation_id: int,
    actor_a: int,
    actor_b: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full pair correlation details including contributions, missing dimensions, and evidence."""
    data = get_correlation_detail(
        db=db,
        investigation_id=investigation_id,
        actor_a_id=actor_a,
        actor_b_id=actor_b,
        user=current_user,
        run_id=run_id,
    )
    return success(data=data)


@router.get("/{investigation_id}/analysis/actors", status_code=status.HTTP_200_OK)
def get_actors_analysis_route(
    investigation_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve per-actor stylometry writeprints, TF-IDF summaries, and behavioural profiles."""
    data = get_investigation_actors_analysis(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        run_id=run_id,
    )
    return success(data=data)


@router.get("/{investigation_id}/graph", status_code=status.HTTP_200_OK)
def get_investigation_graph_route(
    investigation_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    min_score: float = Query(0.25, ge=0.0, le=1.0, description="Minimum correlation score for persona edges"),
    max_nodes: int = Query(250, ge=10, le=2000, description="Maximum graph nodes before truncation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve node-link topology for Cytoscape with personas, marketplaces, and shared indicators."""
    data = get_investigation_graph(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        run_id=run_id,
        min_score=min_score,
        max_nodes=max_nodes,
    )
    return success(data=data)


@router.get("/{investigation_id}/chronology", status_code=status.HTTP_200_OK)
def get_investigation_chronology_route(
    investigation_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve temporal posting activity, indicator emergence timeline, pipeline runs, and evidence events."""
    data = get_investigation_chronology(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        run_id=run_id,
    )
    return success(data=data)


@router.get("/{investigation_id}/infrastructure", status_code=status.HTTP_200_OK)
def get_investigation_infrastructure_route(
    investigation_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve grouped infrastructure and crypto indicators with actor linkages and evidence pairs."""
    data = get_investigation_infrastructure(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        run_id=run_id,
    )
    return success(data=data)


@router.get("/{investigation_id}/actors", status_code=status.HTTP_200_OK)
def list_investigation_actors_route(
    investigation_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List threat actor personas in investigation with activity metrics and best correlation score."""
    data = list_investigation_actors(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        run_id=run_id,
    )
    return success(data=data)


@router.get("/{investigation_id}/actors/{actor_id}", status_code=status.HTTP_200_OK)
def get_actor_profile_route(
    investigation_id: int,
    actor_id: int,
    run_id: Optional[int] = Query(None, description="Pipeline run ID (defaults to latest completed)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve deep persona profile including aliases, indicators, writeprints, and possible related personas."""
    data = get_actor_profile(
        db=db,
        investigation_id=investigation_id,
        actor_id=actor_id,
        user=current_user,
        run_id=run_id,
    )
    return success(data=data)


@router.post("/{investigation_id}/reports", status_code=status.HTTP_201_CREATED)
def create_report_route(
    investigation_id: int,
    payload: ReportCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and store an exported forensic dossier report (PDF, CSV, or JSON)."""
    data = create_investigation_report(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
        report_format=payload.format,
        run_id=payload.run_id,
        csv_kind=payload.csv_kind,
    )
    return success(data=data)


@router.get("/{investigation_id}/reports", status_code=status.HTTP_200_OK)
def list_reports_route(
    investigation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all previously generated dossier export reports for this investigation."""
    data = list_investigation_reports(
        db=db,
        investigation_id=investigation_id,
        user=current_user,
    )
    return success(data=data)


@router.get("/{investigation_id}/reports/{report_id}/download")
def download_report_route(
    investigation_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream exported dossier report file with proper authentication and headers."""
    file_path, filename, mime = get_report_file_for_download(
        db=db,
        investigation_id=investigation_id,
        report_id=report_id,
        user=current_user,
    )
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=mime,
    )



