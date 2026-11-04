"""Integration tests for Phase 8 stylometry, behaviour, scoring, and correlation endpoints."""

from decimal import Decimal
import pytest
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.models.correlation_result import CorrelationResult
from app.models.investigation import Investigation, InvestigationStatus
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.pipeline_stage_run import PipelineStageRun, PipelineStageStatus
from app.models.user import User, UserRole
from app.services.ingestion_service import load_sample_to_investigation
from app.services.pipeline_service import create_pipeline_run, run_pipeline_job


def _create_user(db_session, email="integ_user@example.com", username="integ_user", role=UserRole.INVESTIGATOR) -> User:
    user = User(
        email=email,
        username=username,
        full_name="Integration Tester",
        role=role,
        is_active=True,
        password_hash=hash_password("ValidPassword123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_investigation(db_session, user: User, title="Integration Case") -> Investigation:
    inv = Investigation(
        title=title,
        description="Testing full analysis pipeline",
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def test_full_pipeline_alpha_stores_correlations(client, db_session):
    """Full pipeline run on Alpha sample completes all 5 stages and stores correlation_results."""
    user = _create_user(db_session, "alpha_run@test.com", "alpha_runner")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Alpha Analysis Case")

    # Ingest Alpha benchmark
    load_sample_to_investigation(db_session, user, inv.id, "alpha")

    # Trigger pipeline
    resp = client.post(f"/api/v1/investigations/{inv.id}/pipeline/runs", headers=headers)
    assert resp.status_code == 202
    run_id = resp.json()["data"]["id"]

    # Verify run completed
    resp2 = client.get(f"/api/v1/investigations/{inv.id}/pipeline/runs/{run_id}", headers=headers)
    assert resp2.status_code == 200
    run_data = resp2.json()["data"]
    assert run_data["status"] == "completed"

    stages = run_data["stages"]
    assert len(stages) == 5
    stage_names = [s["stage"] for s in stages]
    assert stage_names == [
        "crypto_matching",
        "infrastructure_matching",
        "stylometric_analysis",
        "behavioural_analysis",
        "scoring",
    ]
    for s in stages:
        assert s["status"] == "completed"

    # Verify correlations endpoint returns stored correlations
    corr_resp = client.get(f"/api/v1/investigations/{inv.id}/correlations?run_id={run_id}", headers=headers)
    assert corr_resp.status_code == 200
    corr_body = corr_resp.json()
    assert corr_body["success"] is True
    corrs = corr_body["data"]
    assert len(corrs) > 0

    first = corrs[0]
    assert "combined_score" in first
    assert "level" in first
    assert "coverage" in first
    assert "dimension_scores" in first
    assert "actors" in first
    assert "actor_a" in first["actors"]
    assert "actor_b" in first["actors"]
    assert first["actors"]["actor_a"]["id"] < first["actors"]["actor_b"]["id"]

    # Check detail endpoint for top pair
    aid_a = first["actors"]["actor_a"]["id"]
    aid_b = first["actors"]["actor_b"]["id"]
    detail_resp = client.get(
        f"/api/v1/investigations/{inv.id}/correlations/{aid_a}/{aid_b}?run_id={run_id}",
        headers=headers,
    )
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()["data"]
    assert "contributions" in detail_data
    assert "missing_dimensions" in detail_data
    assert "contradictions" in detail_data
    assert "evidence" in detail_data

    # Check actor analysis endpoint for charts
    analysis_resp = client.get(f"/api/v1/investigations/{inv.id}/analysis/actors?run_id={run_id}", headers=headers)
    assert analysis_resp.status_code == 200
    analysis_data = analysis_resp.json()["data"]
    assert len(analysis_data) > 0
    first_actor_analysis = analysis_data[0]
    assert "stylometry" in first_actor_analysis
    assert "features" in first_actor_analysis["stylometry"]
    assert "behaviour" in first_actor_analysis


def test_put_scoring_config_admin_only_and_versioning(client, db_session):
    """PUT /api/v1/scoring-configs/active updates configuration atomically creating a new version."""
    admin = _create_user(db_session, "admin_cfg@test.com", "admin_cfg", role=UserRole.ADMIN)
    investigator = _create_user(db_session, "inv_cfg@test.com", "inv_cfg", role=UserRole.INVESTIGATOR)

    inv_token = create_access_token(investigator)
    admin_token = create_access_token(admin)

    payload = {
        "weights": {
            "cryptographic": 0.30,
            "infrastructure": 0.20,
            "stylometric": 0.30,
            "behavioural": 0.20,
        },
        "thresholds": {
            "scoring": {
                "potential_link": 0.50,
            }
        },
    }

    # 1. Investigator is rejected (403 Forbidden)
    resp_inv = client.put(
        "/api/v1/scoring-configs/active",
        json=payload,
        headers={"Authorization": f"Bearer {inv_token}"},
    )
    assert resp_inv.status_code == 403

    # 2. Invalid weights not summing to 1.0 rejected (422)
    bad_payload = {
        "weights": {
            "cryptographic": 0.50,
            "infrastructure": 0.50,
            "stylometric": 0.50,
            "behavioural": 0.50,
        }
    }
    resp_bad = client.put(
        "/api/v1/scoring-configs/active",
        json=bad_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_bad.status_code == 422

    # 3. Valid update creates a new version
    resp_ok = client.put(
        "/api/v1/scoring-configs/active",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_ok.status_code == 200
    data = resp_ok.json()["data"]
    assert data["is_active"] is True
    assert data["weights"]["cryptographic"] == 0.30
    assert data["weights"]["stylometric"] == 0.30
    new_version = data["version"]

    # Verify GET returns active config
    resp_get = client.get(
        "/api/v1/scoring-configs/active",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["version"] == new_version


def test_stateless_stylometry_compare(client, db_session):
    """POST /api/v1/stylometry/compare returns features, similarities, and required caveats."""
    user = _create_user(db_session, "style_comp@test.com", "style_comp")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    sample_a = (
        "Hello everyone, this is the first dark market vendor post offering secure pgp communications "
        "and clean escrow services. We operate daily from 08:00 to 22:00. Fast dispatch and discrete vacuum pack."
    )
    sample_b = (
        "Greetings buyers, this is another vendor shop with professional pgp encryption protocols "
        "and escrow guarantees. Always verify our signature before releasing payment coins."
    )

    payload = {
        "samples": [
            {"label": "vendor_alpha", "text": sample_a},
            {"label": "vendor_beta", "text": sample_b},
        ]
    }

    resp = client.post("/api/v1/stylometry/compare", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]

    assert "samples" in data
    assert len(data["samples"]) == 2
    assert "pairwise_similarities" in data
    assert len(data["pairwise_similarities"]) == 1
    assert "caveats" in data
    assert len(data["caveats"]) >= 2

    # Caveats must mention TF-IDF fitting on submitted samples only and short text unreliability
    caveats_text = " ".join(data["caveats"]).lower()
    assert "submitted sample set" in caveats_text or "submitted samples only" in caveats_text
    assert "unreliable" in caveats_text

    pair = data["pairwise_similarities"][0]
    assert 0.0 <= pair["overall"] <= 1.0
    assert "char_ngram" in pair
    assert "word_ngram" in pair
    assert "function_words" in pair
    assert "feature_vector" in pair


def test_ownership_enforcement_on_correlation_routes(client, db_session):
    """Correlation endpoints return 404 NOT_FOUND for another user's investigation."""
    alice = _create_user(db_session, "alice_corr@test.com", "alice_corr", role=UserRole.INVESTIGATOR)
    bob = _create_user(db_session, "bob_corr@test.com", "bob_corr", role=UserRole.INVESTIGATOR)

    alice_token = create_access_token(alice)
    bob_token = create_access_token(bob)

    inv_alice = _create_investigation(db_session, alice, "Alice Confidential Case")

    # Bob tries to access Alice's correlations -> 404 NOT FOUND
    resp = client.get(
        f"/api/v1/investigations/{inv_alice.id}/correlations",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

    resp_detail = client.get(
        f"/api/v1/investigations/{inv_alice.id}/correlations/1/2",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert resp_detail.status_code == 404

    resp_analysis = client.get(
        f"/api/v1/investigations/{inv_alice.id}/analysis/actors",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert resp_analysis.status_code == 404


def test_dashboard_potential_linkages_count(client, db_session):
    """Dashboard potential_linkages matches count of correlation_results >= potential_link in latest completed runs."""
    user = _create_user(db_session, "dash_corr@test.com", "dash_corr", role=UserRole.INVESTIGATOR)
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    inv = _create_investigation(db_session, user, "Dashboard Case")
    load_sample_to_investigation(db_session, user, inv.id, "alpha")

    # Run pipeline
    resp = client.post(f"/api/v1/investigations/{inv.id}/pipeline/runs", headers=headers)
    assert resp.status_code == 202
    run_id = resp.json()["data"]["id"]

    # Count correlation_results with combined_score >= 0.45 for this run
    corrs = db_session.scalars(
        select(CorrelationResult).where(
            CorrelationResult.pipeline_run_id == run_id,
            CorrelationResult.combined_score >= Decimal("0.45"),
        )
    ).all()
    expected_count = len(corrs)
    assert expected_count > 0

    # Fetch dashboard metrics
    dash_resp = client.get("/api/v1/dashboard/summary", headers=headers)
    assert dash_resp.status_code == 200
    totals = dash_resp.json()["data"]["totals"]
    assert totals["potential_linkages"] == expected_count
