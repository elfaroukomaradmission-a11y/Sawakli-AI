"""FastAPI dependencies for authentication and organization scoping."""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from sawakli.core.security import decode_access_token
from sawakli.db.models.organization import Organization
from sawakli.db.models.organization_member import OrganizationMember
from sawakli.db.models.user import User
from sawakli.db.session import get_db

_bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    organization: Organization


def apply_org_scope(statement: Select[Any], model: type[Any], organization_id: UUID) -> Select[Any]:
    """Restrict a query to rows that belong to the authenticated organization."""
    organization_id_column = getattr(model, "organization_id", None)
    if organization_id_column is None:
        raise TypeError(f"{model.__name__} has no organization_id column to scope on")
    return statement.where(organization_id_column == organization_id)


def get_auth_context(
    credentials: BearerCredentials,
    db: DbSession,
) -> AuthContext:
    """Resolve the current user and organization from a Bearer token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id, organization_id = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    organization = db.get(Organization, organization_id)
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    if user is None or organization is None or membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthContext(user=user, organization=organization)


def require_org_match(
    org: UUID,
    auth: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthContext:
    """The {org} in the URL must equal the token's org. It is checked, never trusted."""
    if org != auth.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return auth


OrgAuth = Annotated[AuthContext, Depends(require_org_match)]
