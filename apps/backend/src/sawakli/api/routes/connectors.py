from __future__ import annotations

from datetime import datetime
from typing import Annotated, TypedDict, cast
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from sawakli.api.deps import AuthContext, get_auth_context
from sawakli.connectors.csv.parser import RawResponse, parse_csv_upload
from sawakli.connectors.errors import ConnectorError
from sawakli.connectors.oauth import (
    ConnectionStatus,
    PostgresTokenRepository,
    Provider,
    TokenExchanger,
    check_connection_status,
    load_encryption_key,
    store_oauth_token,
)
from sawakli.connectors.oauth.models import ExchangedToken
from sawakli.db.session import get_db

router = APIRouter()

DbSession = Annotated[Session, Depends(get_db)]
CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


class DataSourceRow(TypedDict):
    id: UUID
    provider: str
    last_synced_at: datetime | None


class ConnectorSetupResponse(BaseModel):
    data_source_id: UUID
    provider: str
    status: str


class CsvUploadResponse(BaseModel):
    data_source_id: UUID
    provider: str
    row_count: int
    parsed_rows: list[dict[str, object]]
    parse_warnings: list[str]


class OAuthCallbackRequest(BaseModel):
    provider: Provider
    code: str


class OAuthCallbackResponse(BaseModel):
    data_source_id: UUID
    provider: Provider
    status: str


class ConnectionStatusResponse(BaseModel):
    data_source_id: UUID
    connected: bool
    token_valid: bool
    last_successful_call_at: datetime | None


class UnconfiguredTokenExchanger:
    """Temporary API dependency until a real provider exchanger is available.

    CONN-02 defines the TokenExchanger contract but does not provide a real
    provider HTTP implementation. API-03 therefore exposes the handoff
    boundary and allows the real exchanger to be injected later.
    """

    def exchange_auth_code(
        self,
        provider: Provider,
        auth_code: str,
    ) -> ExchangedToken:
        raise RuntimeError("OAuth provider integration is not configured")

    def exchange_refresh_token(
        self,
        provider: Provider,
        refresh_token: str,
    ) -> ExchangedToken:
        raise RuntimeError("OAuth provider integration is not configured")


def get_token_exchanger() -> TokenExchanger:
    """Provide the Connector OAuth exchanger to API routes."""

    return UnconfiguredTokenExchanger()


TokenExchangerDependency = Annotated[
    TokenExchanger,
    Depends(get_token_exchanger),
]


def _get_owned_data_source(
    db: Session,
    *,
    data_source_id: UUID,
    organization_id: UUID,
) -> DataSourceRow | None:
    """Return a data source only when it belongs to the authenticated org."""

    row = (
        db.execute(
            text(
                """
            SELECT id, provider, last_synced_at
            FROM data_sources
            WHERE id = :data_source_id
              AND organization_id = :organization_id
            """
            ),
            {
                "data_source_id": data_source_id,
                "organization_id": organization_id,
            },
        )
        .mappings()
        .one_or_none()
    )

    return cast(DataSourceRow, dict(row)) if row is not None else None


@router.post(
    "/setup",
    response_model=ConnectorSetupResponse,
    status_code=status.HTTP_201_CREATED,
)
def setup_connector(
    auth: CurrentAuth,
    db: DbSession,
) -> ConnectorSetupResponse:
    """Create an organization-owned CSV/demo connector."""

    data_source_id = uuid4()

    row = (
        db.execute(
            text(
                """
            INSERT INTO data_sources (
                id,
                organization_id,
                provider,
                status
            )
            VALUES (
                :id,
                :organization_id,
                'csv_demo',
                'disconnected'
            )
            RETURNING id, provider, status
            """
            ),
            {
                "id": data_source_id,
                "organization_id": auth.organization.id,
            },
        )
        .mappings()
        .one()
    )

    db.commit()

    return ConnectorSetupResponse(
        data_source_id=row["id"],
        provider=str(row["provider"]),
        status=str(row["status"]),
    )


@router.post(
    "/csv/{data_source_id}/upload",
    response_model=CsvUploadResponse,
)
def upload_csv(
    data_source_id: UUID,
    file: Annotated[UploadFile, File(...)],
    auth: CurrentAuth,
    db: DbSession,
) -> CsvUploadResponse:
    """Parse an uploaded CSV belonging to the authenticated organization."""

    data_source = _get_owned_data_source(
        db,
        data_source_id=data_source_id,
        organization_id=auth.organization.id,
    )

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    if str(data_source["provider"]) != Provider.CSV_DEMO.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connector does not accept CSV uploads",
        )

    upload_id = uuid4()

    result = parse_csv_upload(
        file.file,
        auth.organization.id,
        upload_id,
    )

    if isinstance(result, ConnectorError):
        # Never expose ConnectorError.message to the UI.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": str(result.kind),
                "message": result.user_message,
                "retryable": result.retryable,
            },
        )

    assert isinstance(result, RawResponse)

    db.execute(
        text(
            """
            UPDATE data_sources
            SET status = 'demo_data'
            WHERE id = :data_source_id
              AND organization_id = :organization_id
            """
        ),
        {
            "data_source_id": data_source_id,
            "organization_id": auth.organization.id,
        },
    )
    db.commit()

    return CsvUploadResponse(
        data_source_id=data_source_id,
        provider=Provider.CSV_DEMO.value,
        row_count=result.row_count,
        parsed_rows=result.parsed_rows,
        parse_warnings=result.parse_warnings,
    )


@router.post(
    "/{data_source_id}/oauth/callback",
    response_model=OAuthCallbackResponse,
)
def oauth_callback(
    data_source_id: UUID,
    payload: OAuthCallbackRequest,
    auth: CurrentAuth,
    db: DbSession,
    exchanger: TokenExchangerDependency,
) -> OAuthCallbackResponse:
    """Hand an OAuth authorization code to Connector without exposing tokens."""

    data_source = _get_owned_data_source(
        db,
        data_source_id=data_source_id,
        organization_id=auth.organization.id,
    )

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    stored_provider = str(data_source["provider"])

    if stored_provider != payload.provider.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider does not match connector",
        )

    try:
        encryption_key = load_encryption_key()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connector security configuration is unavailable",
        ) from exc

    repo = PostgresTokenRepository(
        db.connection(),
        encryption_key,
    )

    try:
        result = store_oauth_token(
            data_source_id,
            payload.provider,
            payload.code,
            repo=repo,
            exchanger=exchanger,
        )
    except RuntimeError as exc:
        # CONN-02 currently has no concrete provider exchanger.
        # Do not leak implementation details or OAuth values.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth provider integration is unavailable",
        ) from exc

    if isinstance(result, ConnectorError):
        db.rollback()

        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY if result.retryable else status.HTTP_400_BAD_REQUEST
            ),
            detail={
                "code": str(result.kind),
                "message": result.user_message,
                "retryable": result.retryable,
            },
        )

    db.commit()

    return OAuthCallbackResponse(
        data_source_id=data_source_id,
        provider=payload.provider,
        status="connected",
    )


@router.get(
    "/{data_source_id}/status",
    response_model=ConnectionStatusResponse,
)
def get_connector_status(
    data_source_id: UUID,
    auth: CurrentAuth,
    db: DbSession,
) -> ConnectionStatusResponse:
    """Return safe connection health for an organization-owned connector."""

    data_source = _get_owned_data_source(
        db,
        data_source_id=data_source_id,
        organization_id=auth.organization.id,
    )

    if data_source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )

    try:
        encryption_key = load_encryption_key()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connector security configuration is unavailable",
        ) from exc

    repo = PostgresTokenRepository(
        db.connection(),
        encryption_key,
    )

    connector_status: ConnectionStatus = check_connection_status(
        data_source_id,
        repo=repo,
        last_synced_at=data_source["last_synced_at"],
    )

    return ConnectionStatusResponse(
        data_source_id=data_source_id,
        connected=connector_status.connected,
        token_valid=connector_status.token_valid,
        last_successful_call_at=connector_status.last_successful_call_at,
    )
