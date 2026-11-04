"""Tests for synthetic benchmark sample listing, loading, linking, and dashboard metrics scoping."""

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token, hash_password
from app.models.dataset import Dataset, DatasetSourceType
from app.models.investigation import Investigation, InvestigationStatus
from app.models.post import Post
from app.models.user import User, UserRole


def _create_user(db_session, email="sample_user@example.com", username="sample_user", role=UserRole.INVESTIGATOR) -> User:
    user = User(
        email=email,
        username=username,
        full_name="Sample Tester",
        role=role,
        is_active=True,
        password_hash=hash_password("ValidPassword123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_investigation(db_session, user: User, title="Sample Benchmark Case") -> Investigation:
    inv = Investigation(
        title=title,
        description="Testing sample loading",
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def test_list_sample_datasets(client, db_session):
    """GET /api/v1/datasets/samples returns valid catalog metadata for alpha and beta."""
    user = _create_user(db_session, "lister@example.com", "lister_1")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/v1/datasets/samples", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]

    keys = {s["key"] for s in data}
    assert "alpha" in keys
    assert "beta" in keys

    alpha_entry = next(s for s in data if s["key"] == "alpha")
    assert alpha_entry["post_count"] == 180
    assert alpha_entry["marketplace_count"] == 4
    assert alpha_entry["persona_count"] == 10
    assert isinstance(alpha_entry["loaded"], bool)


def test_load_sample_idempotency_and_multi_investigation(client, db_session):
    """Loading sample twice into same investigation is idempotent; attaching to another investigation works."""
    user = _create_user(db_session, "loader@example.com", "loader_1")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    inv1 = _create_investigation(db_session, user, "Investigation 1")
    inv2 = _create_investigation(db_session, user, "Investigation 2")

    # 1. Load Alpha into inv1
    resp1 = client.post(f"/api/v1/investigations/{inv1.id}/datasets/samples/alpha", headers=headers)
    assert resp1.status_code == 200
    data1 = resp1.json()["data"]
    assert data1["imported"] == 180
    assert data1["new_marketplaces"] == 4
    assert data1["new_actors"] == 10

    # 2. Re-load Alpha into inv1 (Idempotent: no duplicate posts created)
    total_posts_before = db_session.execute(select(func.count(Post.id))).scalar()
    resp1_second = client.post(f"/api/v1/investigations/{inv1.id}/datasets/samples/alpha", headers=headers)
    assert resp1_second.status_code == 200
    total_posts_after = db_session.execute(select(func.count(Post.id))).scalar()
    assert total_posts_before == total_posts_after

    # 3. Attach same sample to inv2 (reuses existing dataset without re-creating posts)
    resp2 = client.post(f"/api/v1/investigations/{inv2.id}/datasets/samples/alpha", headers=headers)
    assert resp2.status_code == 200
    total_posts_after_inv2 = db_session.execute(select(func.count(Post.id))).scalar()
    assert total_posts_after_inv2 == total_posts_before


def test_dashboard_metrics_reflect_real_data_and_ownership(client, db_session):
    """Dashboard total posts and indicators update with real ingested rows and respect investigator scoping."""
    user_a = _create_user(db_session, "analyst_a@example.com", "analyst_a", role=UserRole.INVESTIGATOR)
    user_b = _create_user(db_session, "analyst_b@example.com", "analyst_b", role=UserRole.INVESTIGATOR)
    admin = _create_user(db_session, "admin_chief@example.com", "admin_chief", role=UserRole.ADMIN)

    token_a = create_access_token(user_a)
    token_b = create_access_token(user_b)
    token_admin = create_access_token(admin)

    inv_a = _create_investigation(db_session, user_a, "Analyst A Case")

    # Ingest Alpha into Case A (180 posts)
    client.post(
        f"/api/v1/investigations/{inv_a.id}/datasets/samples/alpha",
        headers={"Authorization": f"Bearer {token_a}"},
    )

    # 1. Check Analyst A dashboard: should see 180 posts
    resp_a = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    assert resp_a.json()["data"]["totals"]["posts"] == 180
    assert resp_a.json()["data"]["totals"]["investigations"] == 1

    # 2. Check Analyst B dashboard: owns 0 investigations and 0 posts
    resp_b = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    assert resp_b.json()["data"]["totals"]["posts"] == 0
    assert resp_b.json()["data"]["totals"]["investigations"] == 0

    # 3. Check Admin dashboard: sees all 180 posts across the system
    resp_admin = client.get("/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {token_admin}"})
    assert resp_admin.status_code == 200
    assert resp_admin.json()["data"]["totals"]["posts"] >= 180

