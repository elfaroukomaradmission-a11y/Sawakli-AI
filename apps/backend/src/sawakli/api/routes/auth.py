from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from sawakli.api.deps import AuthContext, get_auth_context
from sawakli.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    OrganizationPublic,
    RegisterRequest,
    RegisterResponse,
    UserPublic,
)
from sawakli.core.security import create_access_token, hash_password, verify_password
from sawakli.db.models.organization import Organization
from sawakli.db.models.organization_member import OrganizationMember
from sawakli.db.models.user import User
from sawakli.db.session import get_db

router = APIRouter()

_INVALID_CREDENTIALS = "Invalid email or password"
_DEFAULT_PLAN = "free"
_OWNER_ROLE = "owner"

DbSession = Annotated[Session, Depends(get_db)]
CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(payload: RegisterRequest, db: DbSession) -> RegisterResponse:
    existing = db.scalar(select(User.id).where(func.lower(User.email) == payload.email.lower()))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        name=payload.name,
    )
    organization = Organization(name=payload.organization_name, plan=_DEFAULT_PLAN)
    membership = OrganizationMember(
        user=user,
        organization=organization,
        role=_OWNER_ROLE,
    )

    db.add(user)
    db.add(organization)
    db.add(membership)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    db.refresh(user)
    db.refresh(organization)
    return RegisterResponse(
        user=UserPublic.model_validate(user),
        organization=OrganizationPublic.model_validate(organization),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS,
        )

    membership = db.scalar(select(OrganizationMember).where(OrganizationMember.user_id == user.id))
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS,
        )

    return LoginResponse(
        access_token=create_access_token(user.id, membership.organization_id),
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=MeResponse)
def read_me(
    auth: CurrentAuth,
    organization_id: Annotated[str | None, Query()] = None,
) -> MeResponse:
    """Return the authenticated user and org from the token, never from the query string."""
    _ = organization_id
    return MeResponse(
        user=UserPublic.model_validate(auth.user),
        organization=OrganizationPublic.model_validate(auth.organization),
    )
