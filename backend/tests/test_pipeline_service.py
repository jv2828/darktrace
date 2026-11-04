"""Integration tests for analytical pipeline lifecycle, stage orchestration, and evidence generation."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models.dataset import Dataset, DatasetSourceType
from app.models.evidence_record import EvidenceRecord
from app.models.evidence_source import EvidenceSource
from app.models.extracted_indicator import ExtractedIndicator, ExtractionMethod, IndicatorType
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_stage_run import PipelineStage, PipelineStageRun, PipelineStageStatus
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole
from app.services.ingestion_service import load_sample_to_investigation
from app.services.pipeline_service import (
    create_pipeline_run,
    get_pipeline_run_detail,
    recover_interrupted_pipeline_runs,
    run_pipeline_job,
)
from app.services.pipeline_stages import STAGE_REGISTRY


def _create_user(db_session, email="pipe_user@example.com", username="pipe_user", role=UserRole.INVESTIGATOR) -> User:
    user = User(
        email=email,
        username=username,
        full_name="Pipeline Tester",
        role=role,
        is_active=True,
        password_hash=hash_password("ValidPassword123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_investigation(db_session, user: User, title="Pipeline Case") -> Investigation:
    inv = Investigation(
        title=title,
        description="Testing pipeline runs",
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def test_pipeline_stages_registry_endpoint(client, db_session):
    """GET /api/v1/pipeline/stages returns all stages with availability."""
    user = _create_user(db_session, "user_stage@test.com", "user_stage")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/pipeline/stages", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    stage_names = [s["name"] for s in data]
    assert "crypto_matching" in stage_names
    assert "infrastructure_matching" in stage_names
    assert "behavioural_analysis" in stage_names
    assert "stylometric_analysis" in stage_names
    assert "scoring" in stage_names

    crypto_s = next(s for s in data if s["name"] == "crypto_matching")
    assert crypto_s["available"] is True
    stylometric_s = next(s for s in data if s["name"] == "stylometric_analysis")
    assert stylometric_s["available"] is True


def test_pipeline_no_data_rejected(client, db_session):
    """Empty investigation returns 422 with code NO_DATA."""
    user = _create_user(db_session, "empty_pipe@test.com", "empty_pipe")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Empty Case")

    resp = client.post(f"/api/v1/investigations/{inv.id}/pipeline/runs", headers=headers)
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NO_DATA"


def test_pipeline_lifecycle_and_evidence(client, db_session):
    """Pipeline execution completes stages, populates summaries, and produces real evidence."""
    user = _create_user(db_session, "life_user@test.com", "life_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Lifecycle Case")

    # Load Alpha benchmark sample into investigation
    load_sample_to_investigation(db_session, user, inv.id, "alpha")

    # Trigger pipeline run via API
    resp = client.post(f"/api/v1/investigations/{inv.id}/pipeline/runs", headers=headers)
    assert resp.status_code == 202
    body = resp.json()
    assert body["success"] is True
    run_id = body["data"]["id"]
    assert body["data"]["status"] == "queued"

    # Execute background job synchronously for testing
    run_pipeline_job(run_id)

    # Fetch run detail
    resp2 = client.get(f"/api/v1/investigations/{inv.id}/pipeline/runs/{run_id}", headers=headers)
    assert resp2.status_code == 200
    run_data = resp2.json()["data"]
    assert run_data["status"] == "completed"
    assert run_data["is_stale"] is False
    assert len(run_data["stages"]) == 5

    # Check stage summaries
    for stg in run_data["stages"]:
        assert stg["status"] == "completed"
        assert stg["items_processed"] >= 0
        assert "input_snapshot" in stg["summary"]
        assert "coverage" in stg["summary"]
        assert "duration_ms" in stg["summary"]

    # Verify evidence records endpoint
    ev_resp = client.get(f"/api/v1/investigations/{inv.id}/evidence", headers=headers)
    assert ev_resp.status_code == 200
    ev_data = ev_resp.json()["data"]
    assert len(ev_data) > 0

    first_ev = ev_data[0]
    assert "dimension" in first_ev
    assert "strength" in first_ev
    assert "actor_a" in first_ev
    assert "actor_b" in first_ev

    # Verify single evidence detail endpoint with sources
    ev_detail_resp = client.get(f"/api/v1/investigations/{inv.id}/evidence/{first_ev['id']}", headers=headers)
    assert ev_detail_resp.status_code == 200
    ev_detail = ev_detail_resp.json()["data"]
    assert len(ev_detail["sources"]) > 0
    assert "post" in ev_detail["sources"][0]
    assert "indicator" in ev_detail["sources"][0]

    # Verify pairs endpoint
    pairs_resp = client.get(f"/api/v1/investigations/{inv.id}/pairs", headers=headers)
    assert pairs_resp.status_code == 200
    pairs_data = pairs_resp.json()["data"]
    assert len(pairs_data) > 0
    # Pairs must be sorted by max_strength descending
    strengths = [p["max_strength"] for p in pairs_data]
    assert strengths == sorted(strengths, reverse=True)


def test_concurrent_active_run_conflict(client, db_session):
    """Triggering a run while another is active returns 409 RUN_IN_PROGRESS."""
    user = _create_user(db_session, "conflict_user@test.com", "conflict_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Conflict Case")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")

    # Create first run
    run1 = create_pipeline_run(db_session, inv.id, user)
    assert run1.status == PipelineRunStatus.QUEUED

    # Attempt second run via API
    resp = client.post(f"/api/v1/investigations/{inv.id}/pipeline/runs", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RUN_IN_PROGRESS"


def test_stage_error_handling_sanitized(client, db_session, monkeypatch):
    """If a stage throws an exception, run and stage fail gracefully without leaking tracebacks."""
    user = _create_user(db_session, "err_user@test.com", "err_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Error Case")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")

    # Monkeypatch crypto handler to simulate crash
    def mock_failing_handler(*args, **kwargs):
        raise ValueError("Simulated algorithmic fault in crypto matching engine")

    monkeypatch.setitem(STAGE_REGISTRY["crypto_matching"], "handler", mock_failing_handler)

    run = create_pipeline_run(db_session, inv.id, user)
    run_pipeline_job(run.id)

    resp = client.get(f"/api/v1/investigations/{inv.id}/pipeline/runs/{run.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert "Simulated algorithmic fault" in data["error_message"]
    assert "Traceback" not in data["error_message"]  # Clean error without stack trace

    # Check that second stage was skipped
    assert data["stages"][0]["status"] == "failed"
    assert data["stages"][1]["status"] == "skipped"


def test_startup_recovery(db_session):
    """Startup recovery routine marks queued and running pipeline runs as failed."""
    user = _create_user(db_session, "restart_user@test.com", "restart_user")
    inv = _create_investigation(db_session, user, "Restart Case")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")

    run = create_pipeline_run(db_session, inv.id, user)
    assert run.status == PipelineRunStatus.QUEUED

    # Execute recovery routine passing test session
    recover_interrupted_pipeline_runs(session=db_session)

    db_session.refresh(run)
    assert run.status == PipelineRunStatus.FAILED
    assert run.error_message == "Interrupted by restart"


def test_ownership_enforcement(client, db_session):
    """Investigator cannot access or execute pipeline on another investigator's case (404 NOT_FOUND)."""
    user1 = _create_user(db_session, "owner1@test.com", "owner1", role=UserRole.INVESTIGATOR)
    user2 = _create_user(db_session, "owner2@test.com", "owner2", role=UserRole.INVESTIGATOR)
    admin = _create_user(db_session, "admin_pipe@test.com", "admin_pipe", role=UserRole.ADMIN)

    inv = _create_investigation(db_session, user1, "User1 Private Case")
    load_sample_to_investigation(db_session, user1, inv.id, "alpha")

    tok2 = create_access_token(user2)
    headers2 = {"Authorization": f"Bearer {tok2}"}

    # User2 gets 404
    resp = client.post(f"/api/v1/investigations/{inv.id}/pipeline/runs", headers=headers2)
    assert resp.status_code == 404

    resp_ev = client.get(f"/api/v1/investigations/{inv.id}/evidence", headers=headers2)
    assert resp_ev.status_code == 404

    # Admin gets 202
    tok_admin = create_access_token(admin)
    headers_admin = {"Authorization": f"Bearer {tok_admin}"}
    resp_adm = client.post(f"/api/v1/investigations/{inv.id}/pipeline/runs", headers=headers_admin)
    assert resp_adm.status_code == 202


def test_staleness_detection(client, db_session):
    """is_stale transitions to true when new posts or indicators are added after run completion."""
    user = _create_user(db_session, "stale_user@test.com", "stale_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Stale Case")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")

    run = create_pipeline_run(db_session, inv.id, user)
    run_pipeline_job(run.id)

    detail_1 = get_pipeline_run_detail(db_session, inv.id, run.id, user)
    assert detail_1["is_stale"] is False

    # Add a new manual post with indicators
    mkt = db_session.execute(select(Marketplace)).scalars().first()
    actor = ThreatActor(marketplace_id=mkt.id, username="fresh_actor", normalised_username="fresh_actor")
    db_session.add(actor)
    db_session.flush()

    ds = Dataset(name="stale_delta", source_type=DatasetSourceType.MANUAL)
    db_session.add(ds)
    db_session.flush()
    db_session.add(InvestigationDataset(investigation_id=inv.id, dataset_id=ds.id))

    new_post = Post(
        dataset_id=ds.id,
        marketplace_id=mkt.id,
        actor_id=actor.id,
        author_username="fresh_actor",
        content="Fresh communication referencing bc1qteststaleaddress1234567890abcdef1234",
        dedupe_hash="hash_delta_999",
    )
    db_session.add(new_post)
    db_session.flush()

    new_ind = ExtractedIndicator(
        post_id=new_post.id,
        indicator_type=IndicatorType.WALLET_BTC,
        raw_value="bc1qteststaleaddress1234567890abcdef1234",
        normalised_value="bc1qteststaleaddress1234567890abcdef1234",
        confidence="high",
        extraction_method=ExtractionMethod.REGEX,
        extractor_version="v1.0.0",
        is_valid_format=True,
    )
    db_session.add(new_ind)
    db_session.commit()

    detail_2 = get_pipeline_run_detail(db_session, inv.id, run.id, user)
    assert detail_2["is_stale"] is True


def test_unattached_datasets_excluded_from_matching(db_session):
    """Posts and indicators in datasets not attached to the investigation are never used."""
    user = _create_user(db_session, "scope_user@test.com", "scope_user")
    inv = _create_investigation(db_session, user, "Scoped Investigation")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")

    # Create unattached dataset with another post sharing a key
    mkt = db_session.execute(select(Marketplace)).scalars().first()
    actor_outside = ThreatActor(marketplace_id=mkt.id, username="outsider", normalised_username="outsider")
    db_session.add(actor_outside)
    db_session.flush()

    unattached_ds = Dataset(name="outside_scope", source_type=DatasetSourceType.MANUAL)
    db_session.add(unattached_ds)
    db_session.flush()

    unattached_post = Post(
        dataset_id=unattached_ds.id,
        marketplace_id=mkt.id,
        actor_id=actor_outside.id,
        author_username="outsider",
        content="Outsider post",
        dedupe_hash="outside_hash_1",
    )
    db_session.add(unattached_post)
    db_session.flush()

    db_session.add(
        ExtractedIndicator(
            post_id=unattached_post.id,
            indicator_type=IndicatorType.PGP_FINGERPRINT,
            raw_value="9B4C8A1D3F2E7A0B5C6D8E9F1A2B3C4D5E6F7A8B",
            normalised_value="9B4C8A1D3F2E7A0B5C6D8E9F1A2B3C4D5E6F7A8B",
            confidence="high",
            extraction_method=ExtractionMethod.REGEX,
            extractor_version="v1.0.0",
            is_valid_format=True,
        )
    )
    db_session.commit()

    run = create_pipeline_run(db_session, inv.id, user)
    run_pipeline_job(run.id)

    # Verify no evidence links to actor_outside
    outside_ev = db_session.execute(
        select(EvidenceRecord).where(
            EvidenceRecord.pipeline_run_id == run.id,
            (EvidenceRecord.actor_a_id == actor_outside.id) | (EvidenceRecord.actor_b_id == actor_outside.id),
        )
    ).scalars().all()
    assert len(outside_ev) == 0
