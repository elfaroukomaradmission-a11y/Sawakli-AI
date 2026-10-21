"""Unit tests for the tenant-isolation helpers in api/deps.py. No database, no app."""

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sawakli.api.deps import apply_org_scope, require_org_match
from sawakli.db.models.campaign import Campaign
from sawakli.db.models.daily_metric import DailyMetric


class _OtherBase(DeclarativeBase):
    """Separate base so this throwaway model never touches the app's metadata."""


class _NoOrgModel(_OtherBase):
    __tablename__ = "no_org_model"

    id: Mapped[int] = mapped_column(primary_key=True)


def _fake_auth(org_id: object) -> Any:
    return SimpleNamespace(organization=SimpleNamespace(id=org_id))


@pytest.mark.parametrize("model", [Campaign, DailyMetric])
def test_apply_org_scope_adds_org_filter(model: type[Campaign] | type[DailyMetric]) -> None:
    org_id = uuid4()

    scoped = apply_org_scope(select(model), model, org_id)

    assert "organization_id" in str(scoped)
    assert org_id in scoped.compile().params.values()


def test_apply_org_scope_keeps_existing_filters() -> None:
    org_id = uuid4()
    campaign_id = uuid4()

    scoped = apply_org_scope(select(Campaign).where(Campaign.id == campaign_id), Campaign, org_id)

    params = scoped.compile().params.values()
    assert org_id in params
    assert campaign_id in params


def test_apply_org_scope_rejects_model_without_organization_id() -> None:
    with pytest.raises(TypeError):
        apply_org_scope(select(_NoOrgModel), _NoOrgModel, uuid4())


def test_require_org_match_returns_auth_when_orgs_match() -> None:
    org_id = uuid4()
    auth = _fake_auth(org_id)

    assert require_org_match(org_id, auth) is auth


def test_require_org_match_raises_404_when_orgs_differ() -> None:
    auth = _fake_auth(uuid4())

    with pytest.raises(HTTPException) as exc_info:
        require_org_match(uuid4(), auth)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Not found"
