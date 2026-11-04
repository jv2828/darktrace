"""Tests for Phase 9 backend workspace endpoints: graph, chronology, infrastructure, actors, and dossier reports."""

import csv
import json
from pathlib import Path
import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token, hash_password
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_dataset import InvestigationDataset
from app.models.investigation_report import InvestigationReport
from app.models.post import Post
from app.models.user import User, UserRole
from app.services.ingestion_service import load_sample_to_investigation
from app.services.pipeline_service import create_pipeline_run, run_pipeline_job
from app.services.report_service import escape_csv_cell


def _create_user(db_session, email="ws_user@example.com", username="ws_user", role=UserRole.INVESTIGATOR) -> User:
    user = User(
        email=email,
        username=username,
        full_name="Workspace Tester",
        role=role,
        is_active=True,
        password_hash=hash_password("ValidPassword123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_investigation(db_session, user: User, title="Workspace Case") -> Investigation:
    inv = Investigation(
        title=title,
        description="Testing workspace endpoints",
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def test_graph_endpoint_shared_indicators_min_score_and_ownership(client, db_session):
    """Graph returns only non-common shared indicators (used by >=2 personas), respects min_score, and enforces 404 ownership."""
    alice = _create_user(db_session, "alice_graph@test.com", "alice_graph")
    bob = _create_user(db_session, "bob_graph@test.com", "bob_graph")

    alice_token = create_access_token(alice)
    bob_token = create_access_token(bob)
    headers = {"Authorization": f"Bearer {alice_token}"}

    inv = _create_investigation(db_session, alice, "Graph Case")
    load_sample_to_investigation(db_session, alice, inv.id, "alpha")
    run = create_pipeline_run(db_session, inv.id, alice)
    run_pipeline_job(run.id, db_session)

    # 1. Ownership check: Bob accessing Alice's graph -> 404
    resp_bob = client.get(
        f"/api/v1/investigations/{inv.id}/graph",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert resp_bob.status_code == 404

    # 2. Alice accessing graph
    resp = client.get(f"/api/v1/investigations/{inv.id}/graph?min_score=0.45", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    graph = body["data"]

    assert "nodes" in graph
    assert "edges" in graph
    assert "truncated" in graph
    assert graph["run_id"] == run.id

    # Check node types
    node_types = {n["data"]["type"] for n in graph["nodes"]}
    assert "persona" in node_types
    assert "marketplace" in node_types

    # Every indicator node must be used by >= 2 personas (shared)
    indicator_nodes = [n for n in graph["nodes"] if n["data"]["type"] in ("pgp", "wallet", "infrastructure")]
    for ind_n in indicator_nodes:
        assert ind_n["data"]["persona_count"] >= 2, f"Indicator {ind_n['data']['id']} has fewer than 2 personas"

    # Check correlated edges respect min_score >= 0.45
    corr_edges = [e for e in graph["edges"] if e["data"]["type"] == "correlated"]
    assert len(corr_edges) > 0
    for e in corr_edges:
        assert e["data"]["combined_score"] >= 0.45


def test_chronology_counts_match_posts(client, db_session):
    """Chronology post counts match actual posts in the investigation."""
    user = _create_user(db_session, "chrono_user@test.com", "chrono_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    inv = _create_investigation(db_session, user, "Chronology Case")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")
    run = create_pipeline_run(db_session, inv.id, user)
    run_pipeline_job(run.id, db_session)

    resp = client.get(f"/api/v1/investigations/{inv.id}/chronology", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]

    # Sum of posts_by_day counts must match total posts with actor and timestamp in investigation
    total_posts_in_chrono = sum(d["count"] for d in data["posts_by_day"])
    dataset_ids = db_session.scalars(
        select(InvestigationDataset.dataset_id).where(InvestigationDataset.investigation_id == inv.id)
    ).all()
    total_posts_in_db = db_session.scalar(
        select(func.count(Post.id)).where(
            Post.dataset_id.in_(dataset_ids),
            Post.posted_at.isnot(None),
            Post.actor_id.isnot(None),
        )
    )
    assert total_posts_in_chrono == total_posts_in_db
    assert total_posts_in_chrono > 0

    assert "indicator_first_seen" in data
    assert "runs" in data
    assert "evidence_events" in data
    assert len(data["runs"]) >= 1


def test_infrastructure_endpoint(client, db_session):
    """Infrastructure endpoint groups indicators and classifies shared, single, and common_suppressed."""
    user = _create_user(db_session, "infra_user@test.com", "infra_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    inv = _create_investigation(db_session, user, "Infra Case")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")
    run = create_pipeline_run(db_session, inv.id, user)
    run_pipeline_job(run.id, db_session)

    resp = client.get(f"/api/v1/investigations/{inv.id}/infrastructure", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert "indicators" in data
    assert "evidence_pairs" in data
    assert len(data["indicators"]) > 0

    statuses = {item["status"] for item in data["indicators"]}
    assert "shared" in statuses or "single" in statuses


def test_actor_profile_possible_related_personas_wording(client, db_session):
    """Actor profile strictly uses 'possible related personas' and never states personas are the same person."""
    user = _create_user(db_session, "actor_user@test.com", "actor_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    inv = _create_investigation(db_session, user, "Actor Profile Case")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")
    run = create_pipeline_run(db_session, inv.id, user)
    run_pipeline_job(run.id, db_session)

    # 1. List actors
    list_resp = client.get(f"/api/v1/investigations/{inv.id}/actors", headers=headers)
    assert list_resp.status_code == 200
    actors_list = list_resp.json()["data"]
    assert len(actors_list) == 10
    first_actor_id = actors_list[0]["id"]

    # 2. Get profile for first actor
    prof_resp = client.get(f"/api/v1/investigations/{inv.id}/actors/{first_actor_id}", headers=headers)
    assert prof_resp.status_code == 200
    prof = prof_resp.json()["data"]

    assert "primary_username" in prof
    assert "aliases" in prof
    assert "marketplaces" in prof
    assert "pgp_identifiers" in prof
    assert "wallet_identifiers" in prof
    assert "infrastructure_indicators" in prof
    assert "behaviour_summary" in prof
    assert "stylometry_summary" in prof
    assert "recent_posts" in prof

    # Verify key name and wording
    assert "possible_related_personas" in prof
    assert "same_person" not in prof
    assert "identified_as" not in prof

    for related in prof["possible_related_personas"]:
        assert "score" in related
        assert "level" in related
        assert "top_explanation" in related
        # Ensure disclaimer presence
        assert "disclaimer" in related


def test_dossier_report_generation_all_formats_and_security(client, db_session):
    """Reports in PDF, CSV, and JSON generate valid files and DB records; download enforces ownership."""
    alice = _create_user(db_session, "alice_rep@test.com", "alice_rep")
    bob = _create_user(db_session, "bob_rep@test.com", "bob_rep")

    alice_token = create_access_token(alice)
    bob_token = create_access_token(bob)
    headers = {"Authorization": f"Bearer {alice_token}"}

    inv = _create_investigation(db_session, alice, "Report Generation Case")
    load_sample_to_investigation(db_session, alice, inv.id, "alpha")
    run = create_pipeline_run(db_session, inv.id, alice)
    run_pipeline_job(run.id, db_session)

    # 1. Test CSV formula injection escape function
    assert escape_csv_cell("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"
    assert escape_csv_cell("+12345") == "'+12345"
    assert escape_csv_cell("-500") == "'-500"
    assert escape_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert escape_csv_cell("normal_text") == "normal_text"

    # 2. Generate JSON report
    resp_json = client.post(
        f"/api/v1/investigations/{inv.id}/reports",
        json={"format": "json"},
        headers=headers,
    )
    assert resp_json.status_code == 201
    rep_json_data = resp_json.json()["data"]
    rep_json_id = rep_json_data["id"]

    # Download JSON and verify content
    dl_json = client.get(f"/api/v1/investigations/{inv.id}/reports/{rep_json_id}/download", headers=headers)
    assert dl_json.status_code == 200
    json_content = json.loads(dl_json.content.decode("utf-8"))
    assert "limitations" in json_content
    assert len(json_content["limitations"]) >= 4
    assert "pipeline_run" in json_content
    assert "scoring_config" in json_content
    assert "version" in json_content["scoring_config"]

    # 3. Generate CSV report (pairs)
    resp_csv = client.post(
        f"/api/v1/investigations/{inv.id}/reports",
        json={"format": "csv", "csv_kind": "pairs"},
        headers=headers,
    )
    assert resp_csv.status_code == 201
    rep_csv_id = resp_csv.json()["data"]["id"]

    dl_csv = client.get(f"/api/v1/investigations/{inv.id}/reports/{rep_csv_id}/download", headers=headers)
    assert dl_csv.status_code == 200
    csv_text = dl_csv.content.decode("utf-8")
    assert "actor_a" in csv_text
    assert "combined_score" in csv_text

    # 4. Generate PDF report
    resp_pdf = client.post(
        f"/api/v1/investigations/{inv.id}/reports",
        json={"format": "pdf"},
        headers=headers,
    )
    assert resp_pdf.status_code == 201
    rep_pdf_id = resp_pdf.json()["data"]["id"]

    dl_pdf = client.get(f"/api/v1/investigations/{inv.id}/reports/{rep_pdf_id}/download", headers=headers)
    assert dl_pdf.status_code == 200
    pdf_bytes = dl_pdf.content
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 2000
    page_count = pdf_bytes.count(b"/Type /Page") + pdf_bytes.count(b"/Type/Page")
    assert page_count >= 1

    # 5. Unauthorized download by Bob -> 404
    bob_dl = client.get(
        f"/api/v1/investigations/{inv.id}/reports/{rep_pdf_id}/download",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert bob_dl.status_code == 404
