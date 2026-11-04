"""Integration tests for extraction API endpoints, ingestion atomicity, rerun conflict, and post detail."""

import pytest
from sqlalchemy import func, select

from app.analysis.extraction import EXTRACTOR_VERSION
from app.core.security import create_access_token, hash_password
from app.models.dataset import Dataset, DatasetSourceType
from app.models.evidence_record import EvidenceDimension, EvidenceDirection, EvidenceRecord
from app.models.evidence_source import EvidenceSource
from app.models.extracted_indicator import ExtractedIndicator, IndicatorType
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.pipeline_run import PipelineRun, PipelineRunStatus
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole


def _create_user(db_session, email="investigator1@example.com", username="inv1", role=UserRole.INVESTIGATOR) -> User:
    user = User(
        email=email,
        username=username,
        full_name="Investigator One",
        role=role,
        is_active=True,
        password_hash=hash_password("ValidPassword123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_investigation(db_session, user: User, title="Extraction Investigation") -> Investigation:
    inv = Investigation(
        title=title,
        description="Testing extraction workflows",
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def test_preview_endpoint_does_not_modify_database(client, db_session):
    """POST /api/v1/extraction/preview extracts indicators without saving any rows to the database."""
    user = _create_user(db_session, "preview_user@example.com", "preview_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    # Count DB rows before
    posts_before = db_session.scalar(select(func.count(Post.id)))
    inds_before = db_session.scalar(select(func.count(ExtractedIndicator.id)))

    payload = {
        "content": "Contact admin on 198.51.100.22 or PGP E4A1 8B9C 2D3E 4F5A 6B7C 8D9E 0F1A 2B3C 4D5E 6F7A.",
        "structured_indicators": {"wallet": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"},
    }

    resp = client.post("/api/v1/extraction/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]

    assert len(data["indicators"]) == 3
    assert data["text_stats"]["char_count"] > 0
    assert data["extractor_version"] == EXTRACTOR_VERSION

    # Count DB rows after - must be completely unchanged
    posts_after = db_session.scalar(select(func.count(Post.id)))
    inds_after = db_session.scalar(select(func.count(ExtractedIndicator.id)))

    assert posts_after == posts_before
    assert inds_after == inds_before


def test_ingestion_commits_indicators_atomically(client, db_session):
    """Manual post ingestion persists post and extracted indicators in the same atomic transaction."""
    user = _create_user(db_session, "ingest_actor@example.com", "ingest_actor")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Atomic Ingest Test")

    post_content = "Connect to our backup at https://mesh.secure.example:8443 or BTC 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa."
    payload = {
        "marketplace": "Greywharf",
        "username": "iron_trader",
        "timestamp": "2026-02-01T12:00:00Z",
        "content": post_content,
        "source_reference": "thread_888",
    }

    resp = client.post(f"/api/v1/investigations/{inv.id}/ingest/manual/commit", json=payload, headers=headers)
    assert resp.status_code == 201

    # Verify post has extractor fields populated
    post = db_session.scalar(select(Post).where(Post.content == post_content))
    assert post is not None
    assert post.extractor_version == EXTRACTOR_VERSION
    assert post.extracted_at is not None

    # Verify extracted indicators exist in database and match spans
    indicators = db_session.scalars(select(ExtractedIndicator).where(ExtractedIndicator.post_id == post.id)).all()
    assert len(indicators) >= 2

    for ind in indicators:
        if ind.span_start is not None and ind.span_end is not None:
            assert post.content[ind.span_start : ind.span_end] == ind.raw_value


def test_indicators_list_and_summary_endpoints(client, db_session):
    """Investigation indicators list and summary return correct counts and filter properly."""
    user = _create_user(db_session, "summary_user@example.com", "summary_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Summary Case")

    # Ingest two posts with various indicators
    client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/commit",
        json={
            "marketplace": "Tidepool",
            "username": "tide_operator",
            "timestamp": "2026-02-02T10:00:00Z",
            "content": "Server: Apache/2.4.41 (Ubuntu)\nPGP: E4A1 8B9C 2D3E 4F5A 6B7C  8D9E 0F1A 2B3C 4D5E 6F7A",
        },
        headers=headers,
    )
    client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/commit",
        json={
            "marketplace": "Tidepool",
            "username": "tide_operator",
            "timestamp": "2026-02-02T11:00:00Z",
            "content": "Secondary IP 198.51.100.99 and port 9000",
        },
        headers=headers,
    )

    # 1. Summary
    sum_resp = client.get(f"/api/v1/investigations/{inv.id}/indicators/summary", headers=headers)
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()["data"]
    assert sum_data["total"] >= 4
    by_type = sum_data["by_type"]
    assert by_type["pgp_fingerprint"]["total"] >= 1
    assert by_type["ip_address"]["total"] >= 1

    # 2. List with pagination
    list_resp = client.get(f"/api/v1/investigations/{inv.id}/indicators?page=1&page_size=2", headers=headers)
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert len(list_body["data"]) == 2
    assert list_body["meta"]["total"] >= 4

    # 3. List filtered by type
    pgp_resp = client.get(f"/api/v1/investigations/{inv.id}/indicators?indicator_type=pgp_fingerprint", headers=headers)
    assert pgp_resp.status_code == 200
    pgp_data = pgp_resp.json()["data"]
    assert len(pgp_data) == 1
    assert pgp_data[0]["indicator_type"] == "pgp_fingerprint"


def test_post_detail_endpoint_returns_exact_spans_and_ownership_404(client, db_session):
    """GET /investigations/{id}/posts/{post_id} returns exact slice match and enforces 404 for unowned."""
    user1 = _create_user(db_session, "owner@example.com", "owner")
    user2 = _create_user(db_session, "stranger@example.com", "stranger")
    token1 = create_access_token(user1)
    token2 = create_access_token(user2)
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    inv1 = _create_investigation(db_session, user1, "Owner's Case")
    post_text = "Operating onion service http://fictionalabcdefghijklmnopqrstuvwxyz234567abcdefghijklmno.onion:8080."
    ingest_resp = client.post(
        f"/api/v1/investigations/{inv1.id}/ingest/manual/commit",
        json={
            "marketplace": "Velvet",
            "username": "velvet_king",
            "timestamp": "2026-02-03T12:00:00Z",
            "content": post_text,
        },
        headers=headers1,
    )
    assert ingest_resp.status_code == 201
    post = db_session.scalar(select(Post).where(Post.content == post_text))
    post_id = post.id

    # Valid fetch by owner
    resp = client.get(f"/api/v1/investigations/{inv1.id}/posts/{post_id}", headers=headers1)
    assert resp.status_code == 200
    pdata = resp.json()["data"]
    assert pdata["id"] == post_id
    assert pdata["content"] == post_text
    assert len(pdata["indicators"]) >= 2

    # Check exact byte-level substring matching for all indicators with spans
    for ind in pdata["indicators"]:
        if ind["span_start"] is not None and ind["span_end"] is not None:
            s = ind["span_start"]
            e = ind["span_end"]
            assert post_text[s:e] == ind["raw_value"]

    # Stranger gets 404 NOT_FOUND
    stranger_resp = client.get(f"/api/v1/investigations/{inv1.id}/posts/{post_id}", headers=headers2)
    assert stranger_resp.status_code == 404


def test_rerun_extraction_and_conflict_when_evidence_exists(client, db_session):
    """POST /investigations/{id}/extraction/rerun re-extracts indicators or returns 409 if evidence exists."""
    user = _create_user(db_session, "rerun_user@example.com", "rerun_user")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Rerun Case")

    # Ingest a post
    post_text = "Relay server 198.51.100.77:8000"
    ingest_resp = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/commit",
        json={
            "marketplace": "Velvet",
            "username": "velvet_king",
            "timestamp": "2026-02-03T14:00:00Z",
            "content": post_text,
        },
        headers=headers,
    )
    assert ingest_resp.status_code == 201
    post = db_session.scalar(select(Post).where(Post.content == post_text))
    post_id = post.id

    # 1. Successful rerun without evidence (force=True re-extracts already processed posts)
    rerun_resp = client.post(f"/api/v1/investigations/{inv.id}/extraction/rerun", json={"force": True}, headers=headers)
    assert rerun_resp.status_code == 200
    rdata = rerun_resp.json()["data"]
    assert rdata["posts_processed"] == 1
    assert rdata["indicators_created"] >= 1

    # 2. Attach an EvidenceSource row referencing an extracted indicator
    ind = db_session.scalar(select(ExtractedIndicator).where(ExtractedIndicator.post_id == post_id))
    actor1 = db_session.scalar(select(ThreatActor).limit(1))
    actor2 = ThreatActor(marketplace_id=actor1.marketplace_id, username="second_actor", normalised_username="second_actor")
    db_session.add(actor2)
    db_session.commit()
    db_session.refresh(actor2)

    run = PipelineRun(
        investigation_id=inv.id,
        status=PipelineRunStatus.COMPLETED,
        triggered_by=user.id,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    ev_rec = EvidenceRecord(
        pipeline_run_id=run.id,
        actor_a_id=min(actor1.id, actor2.id),
        actor_b_id=max(actor1.id, actor2.id),
        dimension=EvidenceDimension.INFRASTRUCTURE,
        evidence_type="shared_indicator",
        direction=EvidenceDirection.SUPPORTING,
        strength=0.95,
        explanation="Shared indicator correlation",
    )
    db_session.add(ev_rec)
    db_session.commit()
    db_session.refresh(ev_rec)

    ev_src = EvidenceSource(
        evidence_id=ev_rec.id,
        post_id=post_id,
        indicator_id=ind.id,
    )
    db_session.add(ev_src)
    db_session.commit()

    # Rerun must now fail with 409 EVIDENCE_EXISTS
    rerun_fail = client.post(f"/api/v1/investigations/{inv.id}/extraction/rerun", json={"force": True}, headers=headers)
    assert rerun_fail.status_code == 409
    err = rerun_fail.json()["error"]
    assert err["code"] == "EVIDENCE_EXISTS"
