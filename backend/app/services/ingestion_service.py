"""Ingestion service for DARKTRACE.

Handles:
  - Sample dataset catalog and loading
  - Manual post entry preview & commit
  - CSV and JSON file upload parsing, preview & atomic commit
  - Scoped query endpoints for investigation posts and attached datasets
"""

import codecs
import csv
from datetime import datetime, timezone
import io
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import UploadFile
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import ROOT_DIR
from app.core.exceptions import APIException
from app.models.dataset import Dataset, DatasetSourceType
from app.models.investigation import Investigation
from app.models.investigation_dataset import InvestigationDataset
from app.models.marketplace import Marketplace
from app.models.post import Post
from app.models.threat_actor import ThreatActor
from app.models.user import User, UserRole
from app.services.normalise import (
    compute_dedupe_hash,
    normalise_marketplace,
    normalise_username,
    truncate_echo,
    validate_post_row,
)

# Limits
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ROW_COUNT = 5000
MAX_PREVIEW_ROWS = 200

# Set maximum field size for CSV parsing in memory
csv.field_size_limit(min(sys.maxsize, 2 * 1024 * 1024))

DATASETS_DIR = ROOT_DIR / "backend" / "datasets"
SAMPLES_DIR = DATASETS_DIR / "sample"


def get_investigation_or_404(db: Session, user: User, investigation_id: int) -> Investigation:
    """Retrieve investigation and enforce ownership scoping (404 for unowned)."""
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise APIException(status_code=404, code="NOT_FOUND", message="Investigation not found.")

    if user.role != UserRole.ADMIN and investigation.created_by != user.id:
        raise APIException(status_code=404, code="NOT_FOUND", message="Investigation not found.")

    return investigation


def get_existing_hashes_for_investigation(db: Session, investigation_id: int) -> Set[str]:
    """Retrieve all dedupe hashes currently present in datasets linked to this investigation."""
    stmt = (
        select(Post.dedupe_hash)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .where(InvestigationDataset.investigation_id == investigation_id)
    )
    return set(db.execute(stmt).scalars().all())


def generate_unique_dataset_name(db: Session, base_name: str) -> str:
    """Ensure dataset name is globally unique by appending counter if collision occurs."""
    candidate = base_name
    counter = 1
    while db.execute(select(Dataset.id).where(Dataset.name == candidate)).scalar_one_or_none():
        candidate = f"{base_name} ({counter})"
        counter += 1
    return candidate


# ---------------------------------------------------------------------------
# 1. Samples Catalog & Ingestion
# ---------------------------------------------------------------------------

def list_available_samples(db: Session) -> List[Dict[str, Any]]:
    """Scan sample dataset JSON files and return metadata with database load status."""
    samples: List[Dict[str, Any]] = []

    if not SAMPLES_DIR.exists():
        return samples

    # Fetch loaded sample datasets from DB
    loaded_datasets_stmt = select(Dataset).where(Dataset.source_type == DatasetSourceType.SAMPLE)
    loaded_datasets = db.execute(loaded_datasets_stmt).scalars().all()
    loaded_map = {ds.name: ds.id for ds in loaded_datasets}

    sample_files = sorted(SAMPLES_DIR.glob("*.json"))
    for file_path in sample_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            key = data.get("key", file_path.stem)
            name = data.get("name", file_path.stem.title())
            description = data.get("description", "")
            version = data.get("version", 1)
            posts = data.get("posts", [])

            post_count = len(posts)
            marketplaces = {p.get("marketplace") for p in posts if p.get("marketplace")}
            personas = {
                (p.get("marketplace"), p.get("username"))
                for p in posts
                if p.get("marketplace") and p.get("username")
            }

            expected_dataset_name = f"Sample: {name} (v{version})"
            loaded_id = loaded_map.get(expected_dataset_name)

            samples.append({
                "key": key,
                "name": name,
                "description": description,
                "version": version,
                "post_count": post_count,
                "marketplace_count": len(marketplaces),
                "persona_count": len(personas),
                "loaded": loaded_id is not None,
                "loaded_dataset_id": loaded_id,
            })
        except Exception:
            continue

    return samples


def load_sample_to_investigation(
    db: Session,
    user: User,
    investigation_id: int,
    sample_key: str,
) -> Dict[str, Any]:
    """Load a sample dataset into the database (if not present) and link to investigation."""
    investigation = get_investigation_or_404(db, user, investigation_id)

    sample_file = SAMPLES_DIR / f"{sample_key}.json"
    if not sample_file.exists():
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message=f"Sample dataset with key '{sample_key}' not found.",
        )

    with open(sample_file, "r", encoding="utf-8") as f:
        sample_data = json.load(f)

    name = sample_data.get("name", sample_key.title())
    version = sample_data.get("version", 1)
    dataset_name = f"Sample: {name} (v{version})"

    # Check if dataset already exists in DB
    existing_dataset_stmt = select(Dataset).where(Dataset.name == dataset_name)
    dataset = db.execute(existing_dataset_stmt).scalar_one_or_none()

    if dataset:
        # Check if already attached to this investigation
        link_stmt = select(InvestigationDataset).where(
            InvestigationDataset.investigation_id == investigation.id,
            InvestigationDataset.dataset_id == dataset.id,
        )
        existing_link = db.execute(link_stmt).scalar_one_or_none()
        if not existing_link:
            db.add(InvestigationDataset(investigation_id=investigation.id, dataset_id=dataset.id))
            db.commit()

        # Count existing posts in dataset
        post_count = db.execute(
            select(func.count(Post.id)).where(Post.dataset_id == dataset.id)
        ).scalar() or 0

        return {
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
            "imported": post_count,
            "skipped_duplicates": 0,
            "skipped_invalid": 0,
            "new_actors": 0,
            "new_marketplaces": 0,
            "already_loaded": True,
        }

    # Dataset does not exist yet: parse and ingest all rows atomically
    raw_posts = sample_data.get("posts", [])
    valid_rows = []
    for idx, p in enumerate(raw_posts, start=1):
        validated = validate_post_row(p, row_number=idx)
        if validated["status"] in {"valid", "valid_with_warnings"}:
            valid_rows.append(validated)

    # Ingest in one transaction
    new_dataset = Dataset(
        name=dataset_name,
        description=sample_data.get("description", "Synthetic intelligence benchmark dataset"),
        source_type=DatasetSourceType.SAMPLE,
        is_fictional=True,
        created_by=user.id,
    )
    db.add(new_dataset)
    db.flush()

    # Link to investigation
    db.add(InvestigationDataset(investigation_id=investigation.id, dataset_id=new_dataset.id))

    imported_count, new_actors, new_mkts = _persist_posts_batch(
        db=db,
        dataset=new_dataset,
        user=user,
        validated_rows=valid_rows,
    )

    db.commit()

    return {
        "dataset_id": new_dataset.id,
        "dataset_name": new_dataset.name,
        "imported": imported_count,
        "skipped_duplicates": len(raw_posts) - len(valid_rows),
        "skipped_invalid": 0,
        "new_actors": new_actors,
        "new_marketplaces": new_mkts,
        "already_loaded": False,
    }


# ---------------------------------------------------------------------------
# 2. Manual Ingestion Preview & Commit
# ---------------------------------------------------------------------------

def preview_manual_post(
    db: Session,
    user: User,
    investigation_id: int,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate a single manual entry against rules and existing duplicates without writing."""
    get_investigation_or_404(db, user, investigation_id)
    existing_hashes = get_existing_hashes_for_investigation(db, investigation_id)

    validated = validate_post_row(
        row=payload,
        row_number=1,
        existing_hashes_in_db=existing_hashes,
    )

    status = validated["status"]
    summary = {
        "total": 1,
        "valid": 1 if status == "valid" else 0,
        "valid_with_warnings": 1 if status == "valid_with_warnings" else 0,
        "duplicates": 1 if status == "duplicate" else 0,
        "invalid": 1 if status == "invalid" else 0,
    }

    return {
        "file_info": {"filename": "manual_entry", "size_bytes": len(str(payload)), "format": "manual"},
        "summary": summary,
        "rows": [validated],
        "truncated": False,
    }


def commit_manual_post(
    db: Session,
    user: User,
    investigation_id: int,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Commit a single validated manual entry into a newly created manual dataset."""
    investigation = get_investigation_or_404(db, user, investigation_id)
    existing_hashes = get_existing_hashes_for_investigation(db, investigation_id)

    validated = validate_post_row(
        row=payload,
        row_number=1,
        existing_hashes_in_db=existing_hashes,
    )

    if validated["status"] == "invalid":
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Manual post validation failed.",
            details=validated["errors"],
        )

    if validated["status"] == "duplicate":
        raise APIException(
            status_code=422,
            code="NOTHING_TO_IMPORT",
            message="Duplicate post already exists in this investigation.",
        )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"
    base_name = f"Manual entry ({now_str})"
    dataset_name = generate_unique_dataset_name(db, base_name)

    # Atomic creation
    dataset = Dataset(
        name=dataset_name,
        description="Manual intelligence record entry",
        source_type=DatasetSourceType.MANUAL,
        is_fictional=True,
        created_by=user.id,
    )
    db.add(dataset)
    db.flush()

    db.add(InvestigationDataset(investigation_id=investigation.id, dataset_id=dataset.id))

    imported_count, new_actors, new_mkts = _persist_posts_batch(
        db=db,
        dataset=dataset,
        user=user,
        validated_rows=[validated],
    )
    db.commit()

    created_post = None
    if imported_count > 0:
        p_stmt = select(Post).where(Post.dataset_id == dataset.id).limit(1)
        p_obj = db.execute(p_stmt).scalar_one_or_none()
        if p_obj:
            created_post = {
                "id": p_obj.id,
                "dedupe_hash": p_obj.dedupe_hash,
                "marketplace": validated["marketplace"],
                "author_username": p_obj.author_username,
                "posted_at": p_obj.posted_at.isoformat() if p_obj.posted_at else None,
                "content": p_obj.content,
            }

    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "imported": imported_count,
        "skipped_duplicates": 0,
        "skipped_invalid": 0,
        "new_actors": new_actors,
        "new_marketplaces": new_mkts,
        "post": created_post,
    }


# ---------------------------------------------------------------------------
# 3. File Upload Preview & Commit (CSV / JSON)
# ---------------------------------------------------------------------------

async def parse_and_validate_upload_file(
    file: UploadFile,
    existing_hashes_db: Set[str],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, int]]:
    """Parse uploaded file in memory, enforcing size and row limits, and validate all rows."""
    content_bytes = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(content_bytes) > MAX_FILE_SIZE_BYTES:
        raise APIException(
            status_code=413,
            code="FILE_TOO_LARGE",
            message=f"Uploaded file exceeds maximum allowed size of 5 MB ({MAX_FILE_SIZE_BYTES} bytes).",
        )

    filename = file.filename or "upload"
    size_bytes = len(content_bytes)

    # Attempt to decode as UTF-8 (supporting with or without BOM)
    try:
        decoded_text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise APIException(
            status_code=422,
            code="UNSUPPORTED_FILE",
            message=f"File encoding error: {e}. File must be valid UTF-8 text.",
        )

    raw_rows: List[Dict[str, Any]] = []
    file_format = "unknown"

    # Try JSON first
    trimmed = decoded_text.strip()
    if trimmed.startswith(("{", "[")):
        try:
            parsed_json = json.loads(trimmed)
            file_format = "json"
            if isinstance(parsed_json, list):
                raw_rows = parsed_json
            elif isinstance(parsed_json, dict):
                if "posts" in parsed_json and isinstance(parsed_json["posts"], list):
                    raw_rows = parsed_json["posts"]
                else:
                    raw_rows = [parsed_json]
        except json.JSONDecodeError:
            pass

    # Try CSV if not parsed as JSON
    if file_format == "unknown":
        try:
            csv_reader = csv.DictReader(io.StringIO(decoded_text))
            if csv_reader.fieldnames:
                # Normalise headers: strip and lowercase
                fieldnames = [c.strip().lower() for c in csv_reader.fieldnames if c]
                has_user = any(k in fieldnames for k in ("username", "author_username", "author"))
                if has_user and {"marketplace", "content"}.issubset(set(fieldnames)):
                    file_format = "csv"
                    for row_dict in csv_reader:
                        # Map normalised header keys
                        clean_row = {}
                        for orig_k, v in row_dict.items():
                            if orig_k:
                                clean_row[orig_k.strip().lower()] = v
                        if "author_username" in clean_row and "username" not in clean_row:
                            clean_row["username"] = clean_row["author_username"]
                        elif "author" in clean_row and "username" not in clean_row:
                            clean_row["username"] = clean_row["author"]
                        if "posted_at" in clean_row and "timestamp" not in clean_row:
                            clean_row["timestamp"] = clean_row["posted_at"]
                        if "thread_id" in clean_row and "source_reference" not in clean_row:
                            clean_row["source_reference"] = clean_row["thread_id"]
                        raw_rows.append(clean_row)
        except Exception:
            pass

    if file_format == "unknown" or not raw_rows:
        raise APIException(
            status_code=422,
            code="UNSUPPORTED_FILE",
            message="Unsupported file format. Please upload a valid CSV (with marketplace, username, content headers) or JSON array of posts.",
        )

    if len(raw_rows) > MAX_ROW_COUNT:
        raise APIException(
            status_code=422,
            code="ROW_LIMIT_EXCEEDED",
            message=f"File contains {len(raw_rows)} rows, which exceeds the limit of {MAX_ROW_COUNT} rows per upload.",
        )

    # Validate each row
    seen_hashes_batch: Set[str] = set()
    validated_rows: List[Dict[str, Any]] = []
    summary = {
        "total": len(raw_rows),
        "valid": 0,
        "valid_with_warnings": 0,
        "duplicates": 0,
        "invalid": 0,
    }

    for idx, row in enumerate(raw_rows, start=1):
        val = validate_post_row(
            row=row,
            row_number=idx,
            existing_hashes_in_batch=seen_hashes_batch,
            existing_hashes_in_db=existing_hashes_db,
        )
        validated_rows.append(val)

        status = val["status"]
        if status == "valid":
            summary["valid"] += 1
            if val["dedupe_hash"]:
                seen_hashes_batch.add(val["dedupe_hash"])
        elif status == "valid_with_warnings":
            summary["valid_with_warnings"] += 1
            if val["dedupe_hash"]:
                seen_hashes_batch.add(val["dedupe_hash"])
        elif status == "duplicate":
            summary["duplicates"] += 1
        elif status == "invalid":
            summary["invalid"] += 1

    file_info = {
        "filename": filename,
        "size_bytes": size_bytes,
        "format": file_format,
    }

    return file_info, validated_rows, summary


async def preview_file_upload(
    db: Session,
    user: User,
    investigation_id: int,
    file: UploadFile,
) -> Dict[str, Any]:
    """Validate uploaded file in memory without writing anything to the database."""
    get_investigation_or_404(db, user, investigation_id)
    existing_hashes = get_existing_hashes_for_investigation(db, investigation_id)

    file_info, validated_rows, summary = await parse_and_validate_upload_file(
        file=file,
        existing_hashes_db=existing_hashes,
    )

    preview_rows = validated_rows[:MAX_PREVIEW_ROWS]
    truncated = len(validated_rows) > MAX_PREVIEW_ROWS

    return {
        "file_info": file_info,
        "summary": summary,
        "rows": preview_rows,
        "truncated": truncated,
    }


async def commit_file_upload(
    db: Session,
    user: User,
    investigation_id: int,
    file: UploadFile,
    on_error: str = "skip_invalid",
) -> Dict[str, Any]:
    """Commit validated file rows atomically to a newly created dataset."""
    investigation = get_investigation_or_404(db, user, investigation_id)
    existing_hashes = get_existing_hashes_for_investigation(db, investigation_id)

    file_info, validated_rows, summary = await parse_and_validate_upload_file(
        file=file,
        existing_hashes_db=existing_hashes,
    )

    # If reject_all and any invalid rows exist
    if on_error == "reject_all" and summary["invalid"] > 0:
        invalid_details = [
            f"Row {r['row_number']}: {'; '.join(r['errors'])}"
            for r in validated_rows
            if r["status"] == "invalid"
        ]
        raise APIException(
            status_code=422,
            code="VALIDATION_ERROR",
            message=f"File contains {summary['invalid']} invalid row(s). Ingestion rejected.",
            details=invalid_details[:50],
        )

    # Filter rows to import
    rows_to_import = [
        r for r in validated_rows if r["status"] in {"valid", "valid_with_warnings"}
    ]

    if not rows_to_import:
        raise APIException(
            status_code=422,
            code="NOTHING_TO_IMPORT",
            message="No importable rows found in upload; all rows were invalid or duplicates.",
        )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"
    source_type_enum = (
        DatasetSourceType.CSV if file_info["format"] == "csv" else DatasetSourceType.JSON
    )
    base_name = f"{file_info['format'].upper()} upload: {file_info['filename']} ({now_str})"
    dataset_name = generate_unique_dataset_name(db, base_name)

    # Atomic transaction
    dataset = Dataset(
        name=dataset_name,
        description=f"Ingested from {file_info['filename']} ({file_info['format'].upper()})",
        source_type=source_type_enum,
        is_fictional=True,
        created_by=user.id,
    )
    db.add(dataset)
    db.flush()

    db.add(InvestigationDataset(investigation_id=investigation.id, dataset_id=dataset.id))

    imported_count, new_actors, new_mkts = _persist_posts_batch(
        db=db,
        dataset=dataset,
        user=user,
        validated_rows=rows_to_import,
    )
    db.commit()

    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "imported": imported_count,
        "skipped_duplicates": summary["duplicates"],
        "skipped_invalid": summary["invalid"],
        "new_actors": new_actors,
        "new_marketplaces": new_mkts,
    }


# ---------------------------------------------------------------------------
# 4. Helper: Persist Posts Batch
# ---------------------------------------------------------------------------

def _persist_posts_batch(
    db: Session,
    dataset: Dataset,
    user: User,
    validated_rows: List[Dict[str, Any]],
) -> Tuple[int, int, int]:
    """Persist a batch of validated rows, creating marketplaces, actors, and posts.

    Returns:
        (imported_count, new_actors_count, new_marketplaces_count)
    """
    if not validated_rows:
        return 0, 0, 0

    new_marketplaces_count = 0
    new_actors_count = 0

    # Cache marketplaces by normalised name
    existing_mkts = db.execute(select(Marketplace)).scalars().all()
    mkt_cache: Dict[str, Marketplace] = {
        normalise_marketplace(m.name): m for m in existing_mkts
    }

    # Cache threat actors by (marketplace_id, normalised_username)
    existing_actors = db.execute(select(ThreatActor)).scalars().all()
    actor_cache: Dict[Tuple[int, str], ThreatActor] = {
        (a.marketplace_id, a.normalised_username): a for a in existing_actors
    }

    posts_to_add: List[Post] = []

    for row in validated_rows:
        raw_mkt = row["marketplace"]
        norm_mkt = normalise_marketplace(raw_mkt)

        # Get or create Marketplace
        mkt_obj = mkt_cache.get(norm_mkt)
        if not mkt_obj:
            mkt_obj = Marketplace(
                name=raw_mkt,
                description=f"Darknet platform {raw_mkt}",
                is_fictional=True,
            )
            db.add(mkt_obj)
            db.flush()
            mkt_cache[norm_mkt] = mkt_obj
            new_marketplaces_count += 1

        # Get or create ThreatActor
        raw_user = row["username"]
        norm_user = normalise_username(raw_user)
        actor_key = (mkt_obj.id, norm_user)

        actor_obj = actor_cache.get(actor_key)
        posted_at = row["datetime_utc"]

        if not actor_obj:
            actor_obj = ThreatActor(
                marketplace_id=mkt_obj.id,
                username=raw_user,
                normalised_username=norm_user,
                first_seen_at=posted_at,
                last_seen_at=posted_at,
            )
            db.add(actor_obj)
            db.flush()
            actor_cache[actor_key] = actor_obj
            new_actors_count += 1
        else:
            # Update first_seen / last_seen timestamps
            if posted_at:
                if actor_obj.first_seen_at is None or posted_at < actor_obj.first_seen_at:
                    actor_obj.first_seen_at = posted_at
                if actor_obj.last_seen_at is None or posted_at > actor_obj.last_seen_at:
                    actor_obj.last_seen_at = posted_at

        # Construct raw_metadata
        raw_meta = {}
        if row.get("structured_indicators"):
            raw_meta["structured_indicators"] = row["structured_indicators"]
        if row.get("structured_indicators_unparsed"):
            raw_meta["structured_indicators_unparsed"] = row["structured_indicators_unparsed"]

        post = Post(
            dataset_id=dataset.id,
            marketplace_id=mkt_obj.id,
            actor_id=actor_obj.id,
            author_username=raw_user,
            content=row["content"],  # ORIGINAL text byte-exact
            dedupe_hash=row["dedupe_hash"],
            posted_at=posted_at,
            source_reference=row.get("source_reference"),
            raw_metadata=raw_meta,
            ingested_by=user.id,
        )
        posts_to_add.append(post)

    db.add_all(posts_to_add)
    db.flush()

    return len(posts_to_add), new_actors_count, new_marketplaces_count


# ---------------------------------------------------------------------------
# 5. Queries: Investigation Posts & Datasets
# ---------------------------------------------------------------------------

def list_investigation_posts(
    db: Session,
    user: User,
    investigation_id: int,
    page: int = 1,
    page_size: int = 25,
    marketplace: Optional[str] = None,
    username: Optional[str] = None,
    q: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """List paginated posts belonging to an investigation with filter capabilities."""
    get_investigation_or_404(db, user, investigation_id)

    # Base join on InvestigationDataset
    base_conditions = [InvestigationDataset.investigation_id == investigation_id]

    if marketplace and marketplace.strip():
        norm_filter = marketplace.strip().lower()
        base_conditions.append(func.lower(Marketplace.name) == norm_filter)

    if username and username.strip():
        base_conditions.append(Post.author_username.ilike(f"%{username.strip()}%"))

    if q and q.strip():
        base_conditions.append(Post.content.ilike(f"%{q.strip()}%"))

    if start_date:
        base_conditions.append(Post.posted_at >= start_date)

    if end_date:
        base_conditions.append(Post.posted_at <= end_date)

    # Total matching posts
    count_stmt = (
        select(func.count(distinct(Post.id)))
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .join(Marketplace, Post.marketplace_id == Marketplace.id)
        .where(*base_conditions)
    )
    total = db.execute(count_stmt).scalar() or 0

    total_pages = math.ceil(total / page_size) if page_size > 0 else 0
    offset = (page - 1) * page_size

    # Fetch items
    stmt = (
        select(Post)
        .join(InvestigationDataset, Post.dataset_id == InvestigationDataset.dataset_id)
        .join(Marketplace, Post.marketplace_id == Marketplace.id)
        .join(Dataset, Post.dataset_id == Dataset.id)
        .options(joinedload(Post.marketplace), joinedload(Post.dataset))
        .where(*base_conditions)
        .order_by(Post.posted_at.desc().nulls_last(), Post.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    posts = db.execute(stmt).scalars().all()

    items = []
    for p in posts:
        content_excerpt = p.content[:120].strip() if p.content else ""
        if p.content and len(p.content) > 120:
            content_excerpt += "..."

        structured = p.raw_metadata.get("structured_indicators", {})
        has_indicators = bool(structured)

        items.append({
            "id": p.id,
            "marketplace": p.marketplace.name if p.marketplace else "Unknown",
            "author_username": p.author_username,
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
            "content_excerpt": content_excerpt,
            "dataset_name": p.dataset.name if p.dataset else "Unknown",
            "has_structured_indicators": has_indicators,
        })

    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    return items, meta


def list_investigation_datasets(
    db: Session,
    user: User,
    investigation_id: int,
) -> List[Dict[str, Any]]:
    """List datasets attached to an investigation with post counts."""
    get_investigation_or_404(db, user, investigation_id)

    stmt = (
        select(
            Dataset.id,
            Dataset.name,
            Dataset.source_type,
            InvestigationDataset.added_at,
            func.count(Post.id).label("post_count"),
        )
        .join(InvestigationDataset, Dataset.id == InvestigationDataset.dataset_id)
        .outerjoin(Post, Post.dataset_id == Dataset.id)
        .where(InvestigationDataset.investigation_id == investigation_id)
        .group_by(Dataset.id, InvestigationDataset.added_at)
        .order_by(InvestigationDataset.added_at.desc())
    )
    rows = db.execute(stmt).all()

    return [
        {
            "id": r[0],
            "name": r[1],
            "source": r[2].value if hasattr(r[2], "value") else str(r[2]),
            "source_type": r[2].value if hasattr(r[2], "value") else str(r[2]),
            "added_at": r[3].isoformat() if r[3] else None,
            "post_count": r[4],
        }
        for r in rows
    ]
