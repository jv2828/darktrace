"""API endpoints for sample intelligence datasets and multi-channel ingestion."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.responses import success
from app.db.session import get_db
from app.models.user import User
from app.schemas.ingestion import ManualPostRequest
from app.services.ingestion_service import (
    commit_file_upload,
    commit_manual_post,
    list_available_samples,
    load_sample_to_investigation,
    parse_and_validate_upload_file,
    preview_file_upload,
    preview_manual_post,
)
from app.services.normalise import validate_post_row

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("/samples", status_code=status.HTTP_200_OK)
def get_sample_datasets_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all available synthetic benchmark sample datasets with DB load status."""
    samples = list_available_samples(db=db)
    return success(data=samples)


@router.post("/sample/{name}/load", status_code=status.HTTP_200_OK)
def load_sample_dataset_alias(
    name: str,
    investigation_id: int = Query(..., description="Target investigation ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load sample dataset (alpha or beta) into an investigation."""
    res = load_sample_to_investigation(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        sample_key=name,
    )
    return success(
        data={
            "dataset_id": res["dataset_id"],
            "dataset_name": res["dataset_name"],
            "posts_inserted": res["imported"],
            "duplicates_skipped": res["skipped_duplicates"],
            "marketplaces_created": res["new_marketplaces"],
            "actors_created": res["new_actors"],
            **res,
        }
    )


@router.post("/manual/preview", status_code=status.HTTP_200_OK)
def preview_manual_entry_alias(
    payload: ManualPostRequest,
    investigation_id: Optional[int] = Query(None, description="Optional target investigation ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview and validate a single manual post entry without saving."""
    payload_dict = payload.model_dump()
    if investigation_id is not None:
        data = preview_manual_post(
            db=db,
            user=current_user,
            investigation_id=investigation_id,
            payload=payload_dict,
        )
        # Add root status and dedupe_hash for convenience
        rows = data.get("rows", [])
        if rows:
            data["status"] = rows[0].get("status")
            data["dedupe_hash"] = rows[0].get("dedupe_hash")
        return success(data=data)

    val = validate_post_row(row=payload_dict, row_number=1)
    status_val = val["status"]
    summary = {
        "total": 1,
        "valid": 1 if status_val == "valid" else 0,
        "valid_with_warnings": 1 if status_val == "valid_with_warnings" else 0,
        "duplicates": 1 if status_val == "duplicate" else 0,
        "invalid": 1 if status_val == "invalid" else 0,
    }
    return success(
        data={
            "file_info": {"filename": "manual_entry", "size_bytes": len(str(payload_dict)), "format": "manual"},
            "summary": summary,
            "rows": [val],
            "status": status_val,
            "dedupe_hash": val.get("dedupe_hash"),
            "truncated": False,
        }
    )


@router.post("/manual", status_code=status.HTTP_201_CREATED)
def commit_manual_entry_alias(
    payload: ManualPostRequest,
    investigation_id: int = Query(..., description="Target investigation ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit a single validated manual post into an investigation."""
    data = commit_manual_post(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        payload=payload.model_dump(),
    )
    return success(data=data)


@router.post("/upload/preview", status_code=status.HTTP_200_OK)
async def preview_upload_alias(
    file: UploadFile = File(...),
    investigation_id: Optional[int] = Query(None, description="Optional target investigation ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate uploaded file in memory without saving."""
    if investigation_id is not None:
        data = await preview_file_upload(
            db=db,
            user=current_user,
            investigation_id=investigation_id,
            file=file,
        )
        return success(data=data)

    file_info, validated_rows, summary = await parse_and_validate_upload_file(
        file=file,
        existing_hashes_db=set(),
    )
    return success(
        data={
            "file_info": file_info,
            "summary": summary,
            "rows": validated_rows[:5],
            "truncated": len(validated_rows) > 5,
        }
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def commit_upload_alias(
    file: UploadFile = File(...),
    investigation_id: int = Query(..., description="Target investigation ID"),
    strategy: str = Query("skip_invalid", description="Ingestion error strategy: skip_invalid or reject_all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Commit uploaded CSV or JSON records into an investigation."""
    data = await commit_file_upload(
        db=db,
        user=current_user,
        investigation_id=investigation_id,
        file=file,
        on_error=strategy,
    )
    return success(data=data)
