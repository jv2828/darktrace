"""Tests for investigations management, ownership scoping, and dashboard metrics."""

from decimal import Decimal
import pytest

from app.core.security import create_access_token, hash_password
from app.models.correlation_result import CorrelationResult
from app.models.dataset import Dataset, DatasetSourceType
from app.models.extracted_indicator import ExtractedIndicator, ExtractionMethod, IndicatorType
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.post import Post
from app.models.scoring_config import ScoringConfig
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole


def _create_user(
    db_session,
    email="inv_user@example.com",
    username="inv_user",
    role=UserRole.INVESTIGATOR,
) -> User:
    """Helper to persist a test user."""
    user = User(
        email=email,
        username=username,
        full_name="Investigator Test",
        role=role,
        is_active=True,
        password_hash=hash_password("ValidPassword123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# =====================================================================
# 1. Validation & Unauthenticated Access Tests
# =====================================================================

def test_unauthenticated_requests_rejected(client):
    """Requests without a valid Bearer token receive 401 NOT_AUTHENTICATED."""
    assert client.get("/api/v1/investigations").status_code == 401
    assert client.post("/api/v1/investigations", json={"title": "Unauthorized"}).status_code == 401
    assert client.get("/api/v1/investigations/1").status_code == 401
    assert client.get("/api/v1/dashboard/summary").status_code == 401


def test_create_investigation_validation(client, db_session):
    """Title must be between 3 and 200 characters after trimming."""
    user = _create_user(db_session, email="creator@example.com", username="creator_1")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    # Too short (< 3 characters)
    resp_short = client.post("/api/v1/investigations", headers=headers, json={"title": "ab"})
    assert resp_short.status_code == 422

    # Whitespace only (< 3 characters trimmed)
    resp_spaces = client.post("/api/v1/investigations", headers=headers, json={"title": "   "})
    assert resp_spaces.status_code == 422

    # Valid creation
    resp_valid = client.post(
        "/api/v1/investigations",
        headers=headers,
        json={"title": " Operation Nightshade ", "description": "Initial dark web surveillance."},
    )
    assert resp_valid.status_code == 201
    body = resp_valid.json()
    assert body["success"] is True
    data = body["data"]
    assert data["title"] == "Operation Nightshade"
    assert data["status"] == "draft"
    assert data["created_by"]["id"] == user.id
    assert data["created_by"]["username"] == user.username
    assert data["counts"] == {"posts": 0, "indicators": 0}


# =====================================================================
# 2. Ownership Scoping Tests
# =====================================================================

def test_ownership_scoping_investigator_isolation(client, db_session):
    """Investigator A cannot fetch or see Investigator B's investigation (returns 404)."""
    user_a = _create_user(db_session, email="investigator_a@example.com", username="user_a")
    user_b = _create_user(db_session, email="investigator_b@example.com", username="user_b")
    admin = _create_user(db_session, email="admin_chief@example.com", username="chief_admin", role=UserRole.ADMIN)

    token_a = create_access_token(user_a)
    token_b = create_access_token(user_b)
    token_admin = create_access_token(admin)

    # User B creates an investigation
    resp_b = client.post(
        "/api/v1/investigations",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Case B Confidential"},
    )
    assert resp_b.status_code == 201
    inv_b_id = resp_b.json()["data"]["id"]

    # User A creates an investigation
    resp_a = client.post(
        "/api/v1/investigations",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"title": "Case A Open"},
    )
    assert resp_a.status_code == 201
    inv_a_id = resp_a.json()["data"]["id"]

    # 1. User A attempts to GET User B's investigation -> must return 404 NOT_FOUND (anti-enumeration)
    resp_a_fetch_b = client.get(
        f"/api/v1/investigations/{inv_b_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a_fetch_b.status_code == 404
    assert resp_a_fetch_b.json()["error"]["code"] == "NOT_FOUND"

    # 2. User A list only includes User A's case
    resp_a_list = client.get(
        "/api/v1/investigations",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a_list.status_code == 200
    items_a = resp_a_list.json()["data"]
    ids_a = [item["id"] for item in items_a]
    assert inv_a_id in ids_a
    assert inv_b_id not in ids_a

    # 3. Admin can fetch User B's investigation and sees both in listing
    resp_admin_fetch_b = client.get(
        f"/api/v1/investigations/{inv_b_id}",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp_admin_fetch_b.status_code == 200
    assert resp_admin_fetch_b.json()["data"]["id"] == inv_b_id

    resp_admin_list = client.get(
        "/api/v1/investigations",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert resp_admin_list.status_code == 200
    ids_admin = [item["id"] for item in resp_admin_list.json()["data"]]
    assert inv_a_id in ids_admin
    assert inv_b_id in ids_admin


# =====================================================================
# 3. Pagination, Search, and Filtering Tests
# =====================================================================

def test_pagination_and_search_filtering(client, db_session):
    """Investigations list supports ?q= search, ?status= filter, and pagination."""
    admin = _create_user(db_session, email="search_admin@example.com", username="search_admin", role=UserRole.ADMIN)
    token = create_access_token(admin)
    headers = {"Authorization": f"Bearer {token}"}

    # Create several investigations
    for title in ["Alpha Market Probe", "Beta Syndicate", "Gamma Ransomware", "Delta Ransomware", "Epsilon Market"]:
        client.post("/api/v1/investigations", headers=headers, json={"title": title})

    # Search keyword
    resp_search = client.get("/api/v1/investigations?q=Ransomware", headers=headers)
    assert resp_search.status_code == 200
    results = resp_search.json()["data"]
    assert len(results) == 2
    for r in results:
        assert "ransomware" in r["title"].lower()

    # Pagination: page_size = 2
    resp_page1 = client.get("/api/v1/investigations?page=1&page_size=2", headers=headers)
    assert resp_page1.status_code == 200
    meta1 = resp_page1.json()["meta"]
    assert meta1["page"] == 1
    assert meta1["page_size"] == 2
    assert len(resp_page1.json()["data"]) == 2
    assert meta1["total"] >= 5

    # Filter status: draft
    resp_draft = client.get("/api/v1/investigations?status=draft", headers=headers)
    assert resp_draft.status_code == 200
    for r in resp_draft.json()["data"]:
        assert r["status"] == "draft"


# =====================================================================
# 4. Real Data Counts & Dashboard Metrics Tests
# =====================================================================

def test_dashboard_and_investigation_counts_with_real_rows(client, db_session):
    """Counts and dashboard metrics reflect real inserted posts, indicators, and linkages."""
    investigator = _create_user(db_session, email="analyst_data@example.com", username="analyst_data")
    other_user = _create_user(db_session, email="other_data@example.com", username="other_data")
    admin = _create_user(db_session, email="admin_data@example.com", username="admin_data", role=UserRole.ADMIN)

    # 1. Create Marketplace & Dataset
    mkt = Marketplace(name="DarkNet Alpha", description="Test Market", is_fictional=True)
    dataset = Dataset(name="Sample Dump 2026", source_type=DatasetSourceType.SAMPLE, is_fictional=True)
    db_session.add_all([mkt, dataset])
    db_session.commit()

    # 2. Create Threat Actor & Posts in Dataset
    actor1 = ThreatActor(marketplace_id=mkt.id, username="DarkVendor", normalised_username="darkvendor")
    actor2 = ThreatActor(marketplace_id=mkt.id, username="SilkBroker", normalised_username="silkbroker")
    db_session.add_all([actor1, actor2])
    db_session.commit()

    post1 = Post(
        dataset_id=dataset.id,
        marketplace_id=mkt.id,
        actor_id=actor1.id,
        author_username="DarkVendor",
        content="Offering BTC escrow service bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
        dedupe_hash="1" * 64,
    )
    post2 = Post(
        dataset_id=dataset.id,
        marketplace_id=mkt.id,
        actor_id=actor2.id,
        author_username="SilkBroker",
        content="Contact silk@jabber.onion for bulk discounts",
        dedupe_hash="2" * 64,
    )
    db_session.add_all([post1, post2])
    db_session.commit()

    # 3. Create Extracted Indicators linked to Posts
    ind1 = ExtractedIndicator(
        post_id=post1.id,
        indicator_type=IndicatorType.WALLET_BTC,
        raw_value="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
        normalised_value="bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
        extraction_method=ExtractionMethod.REGEX,
        extractor_version="1.0.0",
        is_valid_format=True,
    )
    ind2 = ExtractedIndicator(
        post_id=post2.id,
        indicator_type=IndicatorType.DOMAIN,
        raw_value="silk.onion",
        normalised_value="silk.onion",
        extraction_method=ExtractionMethod.REGEX,
        extractor_version="1.0.0",
        is_valid_format=True,
    )
    db_session.add_all([ind1, ind2])
    db_session.commit()

    # 4. Create Investigation for Investigator and link the Dataset
    inv = Investigation(
        title="Operation Hydra Track",
        description="Tracking illicit crypto flow",
        status=InvestigationStatus.PROCESSING,
        created_by=investigator.id,
    )
    db_session.add(inv)
    db_session.commit()

    link = InvestigationDataset(investigation_id=inv.id, dataset_id=dataset.id)
    db_session.add(link)
    db_session.commit()

    # 5. Create Scoring Config, Pipeline Run, and Correlation Result
    config = ScoringConfig(
        name="Test Scoring V1",
        version=1,
        weights={"crypto": 0.5, "infra": 0.3, "style": 0.2},
        thresholds={"min_score": 0.6},
        is_active=False,
    )
    db_session.add(config)
    db_session.commit()

    run = PipelineRun(
        investigation_id=inv.id,
        scoring_config_id=config.id,
        status=PipelineRunStatus.COMPLETED,
        triggered_by=investigator.id,
    )
    db_session.add(run)
    db_session.commit()

    low_id, high_id = min(actor1.id, actor2.id), max(actor1.id, actor2.id)
    correlation = CorrelationResult(
        pipeline_run_id=run.id,
        actor_a_id=low_id,
        actor_b_id=high_id,
        combined_score=Decimal("0.8500"),
        dimension_scores={"crypto": 0.85},
        contributions={"crypto": 1.0},
        missing_dimensions=[],
        contradictions=[],
        scoring_config_id=config.id,
    )
    db_session.add(correlation)
    db_session.commit()

    # --- Verification 1: Investigation Detail Counts ---
    resp_detail = client.get(
        f"/api/v1/investigations/{inv.id}",
        headers={"Authorization": f"Bearer {create_access_token(investigator)}"},
    )
    assert resp_detail.status_code == 200
    counts = resp_detail.json()["data"]["counts"]
    assert counts["posts"] == 2
    assert counts["indicators"] == 2

    # --- Verification 2: Investigator Dashboard Summary ---
    resp_dash_inv = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {create_access_token(investigator)}"},
    )
    assert resp_dash_inv.status_code == 200
    dash_data = resp_dash_inv.json()["data"]
    totals = dash_data["totals"]
    assert totals["investigations"] >= 1
    assert totals["posts"] == 2
    assert totals["indicators"] == 2
    assert totals["potential_linkages"] == 1

    # Recent correlation activity contains the run
    assert len(dash_data["recent_correlation_activity"]) >= 1
    first_activity = dash_data["recent_correlation_activity"][0]
    assert first_activity["investigation_id"] == inv.id
    assert first_activity["status"] == "completed"

    # --- Verification 3: Other Investigator (Zero Linked Data) ---
    resp_dash_other = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {create_access_token(other_user)}"},
    )
    assert resp_dash_other.status_code == 200
    other_totals = resp_dash_other.json()["data"]["totals"]
    # Other investigator has no investigations, thus 0 posts, indicators, and linkages
    assert other_totals["investigations"] == 0
    assert other_totals["posts"] == 0
    assert other_totals["indicators"] == 0
    assert other_totals["potential_linkages"] == 0
    assert len(resp_dash_other.json()["data"]["recent_investigations"]) == 0
    assert len(resp_dash_other.json()["data"]["recent_correlation_activity"]) == 0

    # --- Verification 4: Admin Dashboard Summary (Global Scope) ---
    resp_dash_admin = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {create_access_token(admin)}"},
    )
    assert resp_dash_admin.status_code == 200
    admin_totals = resp_dash_admin.json()["data"]["totals"]
    assert admin_totals["posts"] >= 2
    assert admin_totals["indicators"] >= 2
    assert admin_totals["potential_linkages"] >= 1
