from __future__ import annotations

import io
import json
import logging
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sawakli.api.deps import AuthContext, get_auth_context
from sawakli.connectors.csv import RawResponse, parse_csv_upload
from sawakli.connectors.errors import ConnectorError
from sawakli.data.normalization.pipeline import normalize_and_upsert_batch
from sawakli.data.staging.adapters import staged_row_from_csv_dict
from sawakli.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


class ConnectorSetupResponse(BaseModel):
    data_source_id: UUID
    provider: str
    status: str
    sync_status: str | None
    last_synced_at: datetime | None


class CsvUploadResponse(BaseModel):
    data_source_id: UUID
    row_count: int
    parsed_rows: list[dict[str, Any]]
    parse_warnings: list[str]
    sync_status: str
    last_synced_at: datetime


def _owned_source(db: Session, source_id: UUID, organization_id: UUID) -> dict[str, Any] | None:
    row = (
        db.execute(
            text(
                "SELECT id, provider, status, sync_status, last_synced_at "
                "FROM data_sources WHERE id = :id AND organization_id = :organization_id"
            ),
            {"id": source_id, "organization_id": organization_id},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def _mark_failed(db: Session, source_id: UUID, organization_id: UUID, message: str) -> None:
    db.execute(
        text(
            "UPDATE data_sources SET sync_status = 'failed', last_error = :message "
            "WHERE id = :id AND organization_id = :organization_id"
        ),
        {"id": source_id, "organization_id": organization_id, "message": message},
    )
    db.commit()


@router.post("/setup", response_model=ConnectorSetupResponse, status_code=status.HTTP_201_CREATED)
def setup_csv_source(auth: CurrentAuth, db: DbSession) -> ConnectorSetupResponse:
    source_id = uuid4()
    db.execute(
        text(
            "INSERT INTO data_sources (id, organization_id, provider, status, sync_status) "
            "VALUES (:id, :organization_id, 'csv_demo', 'disconnected', 'pending')"
        ),
        {"id": source_id, "organization_id": auth.organization.id},
    )
    db.commit()
    return ConnectorSetupResponse(
        data_source_id=source_id,
        provider="csv_demo",
        status="disconnected",
        sync_status="pending",
        last_synced_at=None,
    )


@router.post("/csv/{data_source_id}/upload", response_model=CsvUploadResponse)
def upload_csv(
    data_source_id: UUID,
    file: UploadFile,
    auth: CurrentAuth,
    db: DbSession,
) -> CsvUploadResponse:
    source = _owned_source(db, data_source_id, auth.organization.id)
    if source is None or source["provider"] != "csv_demo":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found")

    upload_id = uuid4()
    content = file.file.read()
    result = parse_csv_upload(io.BytesIO(content), auth.organization.id, upload_id)

    if isinstance(result, ConnectorError):
        _mark_failed(db, data_source_id, auth.organization.id, result.user_message)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": result.kind,
                "message": result.user_message,
                "retryable": result.retryable,
            },
        )

    if not isinstance(result, RawResponse) or result.row_count == 0:
        _mark_failed(
            db, data_source_id, auth.organization.id, "No valid rows were found in this file."
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "no_valid_rows",
                "message": "No valid rows were found in this file.",
                "retryable": False,
            },
        )

    synced_at = datetime.now(UTC).replace(tzinfo=None)
    try:
        db.execute(
            text(
                "INSERT INTO raw_api_responses "
                "(id, data_source_id, provider, endpoint, payload, fetched_at) "
                "VALUES (:id, :source_id, 'csv_demo', :endpoint, "
                "CAST(:payload AS jsonb), :fetched_at)"
            ),
            {
                "id": upload_id,
                "source_id": data_source_id,
                "endpoint": f"csv://upload/{file.filename or 'upload.csv'}",
                "payload": json.dumps({"csv": content.decode("utf-8")}),
                "fetched_at": synced_at,
            },
        )
        staged_rows = [
            staged_row_from_csv_dict(auth.organization.id, data_source_id, row)
            for row in result.parsed_rows
        ]
        normalize_and_upsert_batch(db, staged_rows)
        db.execute(
            text(
                "UPDATE data_sources SET status = 'demo_data', sync_status = 'success', "
                "last_synced_at = :synced_at, last_error = NULL "
                "WHERE id = :id AND organization_id = :organization_id"
            ),
            {"id": data_source_id, "organization_id": auth.organization.id, "synced_at": synced_at},
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("CSV import failed for data source %s", data_source_id)
        _mark_failed(db, data_source_id, auth.organization.id, "Import failed. Please try again.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "import_failed",
                "message": "We couldn't import this file. Please try again.",
                "retryable": True,
            },
        ) from None

    return CsvUploadResponse(
        data_source_id=data_source_id,
        row_count=result.row_count,
        parsed_rows=result.parsed_rows,
        parse_warnings=result.parse_warnings,
        sync_status="success",
        last_synced_at=synced_at,
    )
