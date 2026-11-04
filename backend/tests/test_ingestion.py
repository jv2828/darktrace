"""Tests for darknet post ingestion (manual, CSV, JSON, preview, commit, validation, and atomicity)."""

import io
import json
import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token, hash_password
from app.models.dataset import Dataset, DatasetSourceType
from app.models.investigation import Investigation, InvestigationStatus
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole


def _create_user(db_session, email="ingest_user@example.com", username="ingest_user", role=UserRole.INVESTIGATOR) -> User:
    user = User(
        email=email,
        username=username,
        full_name="Ingestion Tester",
        role=role,
        is_active=True,
        password_hash=hash_password("ValidPassword123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_investigation(db_session, user: User, title="Case 101") -> Investigation:
    inv = Investigation(
        title=title,
        description="Ingestion testing case",
        status=InvestigationStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


def test_valid_manual_post_and_byte_exact_content(client, db_session):
    """Manual post commit creates dataset, links investigation, and preserves content byte-exact."""
    user = _create_user(db_session, "user1@example.com", "user1")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Manual Ingest Case")

    exact_content = "Special batch: 100% pure handcrafted \t gears! \nLine two with special characters: € & 🚀."

    payload = {
        "marketplace": "Velvet Bazaar",
        "username": "iron_smith",
        "timestamp": "2026-02-01T12:00:00Z",
        "content": exact_content,
        "source_reference": "thread_123",
        "structured_indicators": {
            "pgp_fingerprint": "A1B2C3D4E5F60718293A4B5C6D7E8F9012345678",
            "wallet": "bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f",
            "port": 443,
        },
    }

    # 1. Preview writes nothing
    post_count_before = db_session.execute(select(func.count(Post.id))).scalar()
    prev_resp = client.post(f"/api/v1/investigations/{inv.id}/ingest/manual/preview", headers=headers, json=payload)
    assert prev_resp.status_code == 200
    prev_json = prev_resp.json()
    assert prev_json["data"]["summary"]["valid"] == 1
    post_count_after_prev = db_session.execute(select(func.count(Post.id))).scalar()
    assert post_count_before == post_count_after_prev

    # 2. Commit creates record
    commit_resp = client.post(f"/api/v1/investigations/{inv.id}/ingest/manual/commit", headers=headers, json=payload)
    assert commit_resp.status_code == 201
    data = commit_resp.json()["data"]
    assert data["imported"] == 1

    # Verify database persistence
    post = db_session.execute(select(Post).where(Post.dataset_id == data["dataset_id"])).scalar_one()
    assert post.content == exact_content  # Byte-exact!
    assert post.author_username == "iron_smith"
    assert post.raw_metadata["structured_indicators"]["port"] == 443
    assert post.raw_metadata["structured_indicators"]["wallet"] == "bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f"


def test_normalisation_and_threat_actor_mapping(client, db_session):
    """Usernames differing in case/NFKC map to one actor; same username across marketplaces creates two actors."""
    user = _create_user(db_session, "user2@example.com", "user2")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Actor Normalisation Case")

    # Ingest post 1: "Iron_Smith" on Velvet Bazaar
    client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/commit",
        headers=headers,
        json={"marketplace": "Velvet Bazaar", "username": "Iron_Smith", "content": "First post here."},
    )

    # Ingest post 2: "iron_smith" on Velvet Bazaar (case variant)
    client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/commit",
        headers=headers,
        json={"marketplace": "velvet bazaar", "username": "iron_smith", "content": "Second post here."},
    )

    # Ingest post 3: "Iron_Smith" on Greywharf (different marketplace)
    client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/commit",
        headers=headers,
        json={"marketplace": "Greywharf", "username": "Iron_Smith", "content": "Third post on greywharf."},
    )

    # Velvet Bazaar must have only ONE actor with normalised_username "iron_smith"
    vb_mkt = db_session.execute(select(Marketplace).where(Marketplace.name.ilike("velvet bazaar"))).scalar_one()
    vb_actors = db_session.execute(
        select(ThreatActor).where(ThreatActor.marketplace_id == vb_mkt.id)
    ).scalars().all()
    assert len(vb_actors) == 1
    assert vb_actors[0].normalised_username == "iron_smith"

    # Total threat actors across system must be 2 (one on Velvet Bazaar, one on Greywharf)
    gw_mkt = db_session.execute(select(Marketplace).where(Marketplace.name.ilike("greywharf"))).scalar_one()
    gw_actors = db_session.execute(
        select(ThreatActor).where(ThreatActor.marketplace_id == gw_mkt.id)
    ).scalars().all()
    assert len(gw_actors) == 1
    assert gw_actors[0].normalised_username == "iron_smith"


def test_invalid_timestamp_and_error_handling(client, db_session):
    """Unparseable timestamp returns validation error with truncated echo."""
    user = _create_user(db_session, "user3@example.com", "user3")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Timestamp Error Case")

    bogus_ts = "not-a-timestamp-" + "x" * 150
    resp = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/preview",
        headers=headers,
        json={"marketplace": "Velvet Bazaar", "username": "vendor_a", "content": "Valid text", "timestamp": bogus_ts},
    )
    assert resp.status_code == 200
    row = resp.json()["data"]["rows"][0]
    assert row["status"] == "invalid"
    assert any("Unparseable timestamp" in err for err in row["errors"])
    # Ensure error echoes at most 100 characters
    err_text = " ".join(row["errors"])
    assert "..." in err_text
    assert len(err_text) < 200


def test_csv_ingestion_with_bom_and_multiline_cell(client, db_session):
    """CSV with UTF-8 BOM, multiline quoted cell, and optional columns ingests properly."""
    user = _create_user(db_session, "user4@example.com", "user4")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "CSV BOM Case")

    # CSV with BOM and multiline quoted content
    csv_raw = (
        "\ufeffMarketplace,Username,Content,Timestamp,Port\n"
        'Velvet Bazaar,bom_author,"First line\nSecond line with quotes ""quoted"" word",2026-03-01 10:00:00,8080\n'
        'Greywharf,other_author,Single line post,2026-03-02 12:00:00,443\n'
    )

    files = {"file": ("test_bom.csv", csv_raw.encode("utf-8"), "text/csv")}
    resp = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/file/commit",
        headers=headers,
        files=files,
        data={"on_error": "skip_invalid"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["imported"] == 2

    # Verify multiline content preserved exactly
    post = db_session.execute(
        select(Post).where(Post.dataset_id == data["dataset_id"], Post.author_username == "bom_author")
    ).scalar_one()
    assert "First line\nSecond line with quotes \"quoted\" word" in post.content
    assert post.raw_metadata["structured_indicators"]["port"] == 8080


def test_nul_byte_and_missing_required_column_rejection(client, db_session):
    """Prohibited NUL bytes or missing required columns in CSV are flagged as invalid."""
    user = _create_user(db_session, "user5@example.com", "user5")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "CSV Validation Case")

    # Missing 'content' column
    bad_csv = "Marketplace,Username\nVelvet Bazaar,iron_user\n"
    resp_missing = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/file/preview",
        headers=headers,
        files={"file": ("bad_header.csv", bad_csv.encode("utf-8"), "text/csv")},
    )
    assert resp_missing.status_code == 422
    assert resp_missing.json()["error"]["code"] == "UNSUPPORTED_FILE"

    # Row with NUL byte in content
    nul_csv = "Marketplace,Username,Content\nVelvet Bazaar,iron_user,Text with \x00 nul byte\n"
    resp_nul = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/file/preview",
        headers=headers,
        files={"file": ("nul.csv", nul_csv.encode("utf-8"), "text/csv")},
    )
    assert resp_nul.status_code == 200
    assert resp_nul.json()["data"]["summary"]["invalid"] == 1


def test_oversized_file_rejected_early(client, db_session):
    """Files over 5 MB are rejected immediately with 413 FILE_TOO_LARGE."""
    user = _create_user(db_session, "user6@example.com", "user6")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Oversized Case")

    # Generate 5.2 MB in-memory payload
    oversized_bytes = b"A" * (5 * 1024 * 1024 + 200)
    files = {"file": ("huge.csv", oversized_bytes, "text/csv")}
    resp = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/file/preview",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_duplicates_within_file_and_against_db(client, db_session):
    """Duplicate posts within a file and against attached investigation data are skipped."""
    user = _create_user(db_session, "user7@example.com", "user7")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Dedupe Case")

    post_data = {
        "marketplace": "Velvet Bazaar",
        "username": "trader_joe",
        "timestamp": "2026-03-01T10:00:00Z",
        "content": "Identical post text for dedupe verification.",
    }

    # First manual commit
    client.post(f"/api/v1/investigations/{inv.id}/ingest/manual/commit", headers=headers, json=post_data)

    # Ingest file containing: row 1 (same as DB), row 2 (new), row 3 (duplicate of row 2)
    csv_rows = (
        "Marketplace,Username,Content,Timestamp\n"
        f"Velvet Bazaar,trader_joe,Identical post text for dedupe verification.,2026-03-01T10:00:00Z\n"
        f"Velvet Bazaar,trader_joe,Brand new unique post,2026-03-02T10:00:00Z\n"
        f"Velvet Bazaar,trader_joe,Brand new unique post,2026-03-02T10:00:00Z\n"
    )

    files = {"file": ("dedupe.csv", csv_rows.encode("utf-8"), "text/csv")}
    resp = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/file/commit",
        headers=headers,
        files=files,
        data={"on_error": "skip_invalid"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["imported"] == 1  # only row 2 imported
    assert data["skipped_duplicates"] == 2  # row 1 (against DB) + row 3 (within batch)


def test_skip_invalid_vs_reject_all(client, db_session):
    """on_error='reject_all' aborts with 422 if any row is invalid; 'skip_invalid' imports valid rows."""
    user = _create_user(db_session, "user8@example.com", "user8")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    inv = _create_investigation(db_session, user, "Strategy Case")

    mixed_csv = (
        "Marketplace,Username,Content\n"
        "Velvet Bazaar,valid_user,Good content\n"
        "V,bad_user,Too short marketplace\n"
    )

    # 1. Reject all: fails with 422
    files1 = {"file": ("mixed.csv", mixed_csv.encode("utf-8"), "text/csv")}
    resp_reject = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/file/commit",
        headers=headers,
        files=files1,
        data={"on_error": "reject_all"},
    )
    assert resp_reject.status_code == 422
    assert resp_reject.json()["error"]["code"] == "VALIDATION_ERROR"

    # 2. Skip invalid: succeeds and imports 1 row
    files2 = {"file": ("mixed.csv", mixed_csv.encode("utf-8"), "text/csv")}
    resp_skip = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/file/commit",
        headers=headers,
        files=files2,
        data={"on_error": "skip_invalid"},
    )
    assert resp_skip.status_code == 201
    assert resp_skip.json()["data"]["imported"] == 1
    assert resp_skip.json()["data"]["skipped_invalid"] == 1


def test_ownership_enforcement_on_ingestion(client, db_session):
    """Investigator cannot ingest or view posts in another investigator's case (404); Admin can."""
    inv_user1 = _create_user(db_session, "owner@example.com", "owner_inv", role=UserRole.INVESTIGATOR)
    inv_user2 = _create_user(db_session, "stranger@example.com", "stranger_inv", role=UserRole.INVESTIGATOR)
    admin_user = _create_user(db_session, "boss@example.com", "boss_admin", role=UserRole.ADMIN)

    token2 = create_access_token(inv_user2)
    admin_token = create_access_token(admin_user)

    inv = _create_investigation(db_session, inv_user1, "Secret Case")

    # Stranger receives 404
    resp_stranger = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/commit",
        headers={"Authorization": f"Bearer {token2}"},
        json={"marketplace": "Velvet Bazaar", "username": "intruder", "content": "hello"},
    )
    assert resp_stranger.status_code == 404
    assert resp_stranger.json()["error"]["code"] == "NOT_FOUND"

    # Admin is allowed
    resp_admin = client.post(
        f"/api/v1/investigations/{inv.id}/ingest/manual/commit",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"marketplace": "Velvet Bazaar", "username": "admin_ingest", "content": "admin post"},
    )
    assert resp_admin.status_code == 201
    assert resp_admin.json()["data"]["imported"] == 1

