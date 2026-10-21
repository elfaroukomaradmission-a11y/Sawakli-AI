"""Integration tests: campaigns list, one campaign, campaign daily metrics.

Uses the shared `client` and `db_session` fixtures from tests/conftest.py. Those run against
the real test database (migrated to head) and wipe users and orgs after every test, so each
test gets a fresh world: org A and org B, each with its own user, token and data.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from sawakli.db.models.campaign import Campaign, CampaignStatus, Platform
from sawakli.db.models.daily_metric import DailyMetric
from tests.conftest import auth_header, login_user, register_user

# (date, spend, revenue, clicks, impressions, conversions)
_ORG_A_METRICS: list[tuple[dt.date, str, str, int, int, int]] = [
    (dt.date(2026, 1, 1), "100.00", "400.00", 50, 1000, 5),
    (dt.date(2026, 1, 2), "150.00", "300.00", 100, 2000, 10),
    (dt.date(2026, 1, 3), "30.00", "0.00", 10, 500, 0),  # no conversions -> cpa null
    (dt.date(2026, 1, 4), "0.00", "0.00", 0, 0, 0),  # all zero -> every ratio null
]

_FULL_RANGE = {"from": "2026-01-01", "to": "2026-01-04"}


@dataclass(frozen=True)
class World:
    token_a: str
    org_a: UUID
    token_b: str
    org_b: UUID
    alpha: UUID  # org A, has 4 days of metrics
    beta: UUID  # org A, no metrics
    gamma: UUID  # org B, has metrics


def _register_and_login(
    client: TestClient, *, name: str, email: str, password: str, organization_name: str
) -> tuple[str, UUID]:
    registered = register_user(
        client,
        name=name,
        email=email,
        password=password,
        organization_name=organization_name,
    )
    organization = registered["organization"]
    assert isinstance(organization, dict)
    organization_id = UUID(str(organization["id"]))
    token = login_user(client, email=email, password=password)["access_token"]
    assert isinstance(token, str)
    return token, organization_id


def _insert_data_source(db: Session, organization_id: UUID) -> UUID:
    data_source_id = uuid4()
    db.execute(
        text(
            "INSERT INTO data_sources (id, organization_id, provider) "
            "VALUES (:id, :organization_id, 'csv_demo')"
        ),
        {"id": data_source_id, "organization_id": organization_id},
    )
    db.commit()
    return data_source_id


def _insert_campaign(
    db: Session,
    organization_id: UUID,
    data_source_id: UUID,
    *,
    name: str,
    platform: Platform,
    status: CampaignStatus | None,
    objective: str | None = None,
    budget: Decimal | None = None,
    start_date: dt.date | None = None,
) -> UUID:
    campaign_id = uuid4()
    db.add(
        Campaign(
            id=campaign_id,
            organization_id=organization_id,
            data_source_id=data_source_id,
            name=name,
            platform=platform,
            status=status,
            objective=objective,
            budget=budget,
            start_date=start_date,
        )
    )
    db.commit()
    return campaign_id


@pytest.fixture()
def world(client: TestClient, db_session: Session) -> World:
    token_a, org_a = _register_and_login(
        client,
        name="User A",
        email="a@example.com",
        password="password-a",
        organization_name="Org A",
    )
    token_b, org_b = _register_and_login(
        client,
        name="User B",
        email="b@example.com",
        password="password-b",
        organization_name="Org B",
    )
    source_a = _insert_data_source(db_session, org_a)
    source_b = _insert_data_source(db_session, org_b)

    alpha = _insert_campaign(
        db_session,
        org_a,
        source_a,
        name="Alpha Campaign",
        platform=Platform.meta,
        status=CampaignStatus.active,
        objective="conversions",
        budget=Decimal("5000.00"),
        start_date=dt.date(2026, 6, 1),
    )
    beta = _insert_campaign(
        db_session,
        org_a,
        source_a,
        name="Beta Campaign",
        platform=Platform.google,
        status=CampaignStatus.paused,
    )
    gamma = _insert_campaign(
        db_session,
        org_b,
        source_b,
        name="Gamma Campaign",
        platform=Platform.google,
        status=CampaignStatus.active,
    )

    db_session.add_all(
        DailyMetric(
            campaign_id=alpha,
            organization_id=org_a,
            date=day,
            spend=Decimal(spend),
            revenue=Decimal(revenue),
            clicks=clicks,
            impressions=impressions,
            conversions=conversions,
        )
        for day, spend, revenue, clicks, impressions, conversions in _ORG_A_METRICS
    )
    db_session.add(
        DailyMetric(
            campaign_id=gamma,
            organization_id=org_b,
            date=dt.date(2026, 1, 1),
            spend=Decimal("999.00"),
            revenue=Decimal("999.00"),
            clicks=999,
            impressions=9999,
            conversions=99,
        )
    )
    db_session.commit()

    return World(
        token_a=token_a,
        org_a=org_a,
        token_b=token_b,
        org_b=org_b,
        alpha=alpha,
        beta=beta,
        gamma=gamma,
    )


def _list_url(org: UUID) -> str:
    return f"/api/orgs/{org}/campaigns"


def _one_url(org: UUID, campaign_id: UUID | str) -> str:
    return f"/api/orgs/{org}/campaigns/{campaign_id}"


def _metrics_url(org: UUID, campaign_id: UUID) -> str:
    return f"/api/orgs/{org}/campaigns/{campaign_id}/metrics"


# --------------------------------------------------------------------------------------
# GET /api/orgs/{org}/campaigns
# --------------------------------------------------------------------------------------


def test_list_campaigns_requires_token(client: TestClient) -> None:
    response = client.get(_list_url(uuid4()))
    assert response.status_code == 401


def test_list_campaigns_returns_only_own_campaigns_sorted_by_name(
    client: TestClient, world: World
) -> None:
    response = client.get(_list_url(world.org_a), headers=auth_header(world.token_a))

    assert response.status_code == 200
    body = response.json()
    # Exactly org A's two campaigns, sorted by name. Org B's "Gamma Campaign" is absent.
    assert [item["name"] for item in body] == ["Alpha Campaign", "Beta Campaign"]
    assert str(world.gamma) not in {item["id"] for item in body}

    alpha = body[0]
    assert alpha["id"] == str(world.alpha)
    assert alpha["platform"] == "meta"
    assert alpha["status"] == "active"
    assert alpha["objective"] == "conversions"
    assert alpha["budget"] == 5000.0
    assert alpha["start_date"] == "2026-06-01"
    assert alpha["end_date"] is None

    for item in body:
        assert "organization_id" not in item
        assert "data_source_id" not in item


def test_list_campaigns_other_orgs_url_returns_404(client: TestClient, world: World) -> None:
    response = client.get(_list_url(world.org_b), headers=auth_header(world.token_a))
    assert response.status_code == 404


# --------------------------------------------------------------------------------------
# GET /api/orgs/{org}/campaigns/{id}
# --------------------------------------------------------------------------------------


def test_get_campaign_requires_token(client: TestClient) -> None:
    response = client.get(_one_url(uuid4(), uuid4()))
    assert response.status_code == 401


def test_get_campaign_returns_own_campaign(client: TestClient, world: World) -> None:
    response = client.get(_one_url(world.org_a, world.alpha), headers=auth_header(world.token_a))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(world.alpha)
    assert body["name"] == "Alpha Campaign"
    assert "organization_id" not in body
    assert "data_source_id" not in body


def test_get_campaign_of_another_org_returns_404(client: TestClient, world: World) -> None:
    headers = auth_header(world.token_a)

    # Own org in the URL, but the campaign belongs to org B: the org scope hides it.
    own_url = client.get(_one_url(world.org_a, world.gamma), headers=headers)
    assert own_url.status_code == 404

    # Org B in the URL and org B's campaign, but org A's token: the URL org check rejects it.
    foreign_url = client.get(_one_url(world.org_b, world.gamma), headers=headers)
    assert foreign_url.status_code == 404


def test_get_campaign_unknown_or_malformed_id(client: TestClient, world: World) -> None:
    headers = auth_header(world.token_a)

    unknown = client.get(_one_url(world.org_a, uuid4()), headers=headers)
    assert unknown.status_code == 404

    malformed = client.get(_one_url(world.org_a, "abc"), headers=headers)
    assert malformed.status_code == 422


# --------------------------------------------------------------------------------------
# GET /api/orgs/{org}/campaigns/{id}/metrics
# --------------------------------------------------------------------------------------


def test_metrics_requires_token(client: TestClient) -> None:
    response = client.get(_metrics_url(uuid4(), uuid4()), params=_FULL_RANGE)
    assert response.status_code == 401


def test_metrics_returns_ordered_rows_with_computed_ratios(
    client: TestClient, world: World
) -> None:
    response = client.get(
        _metrics_url(world.org_a, world.alpha),
        headers=auth_header(world.token_a),
        params=_FULL_RANGE,
    )

    assert response.status_code == 200
    rows = response.json()
    assert [row["date"] for row in rows] == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-03",
        "2026-01-04",
    ]
    for row in rows:
        assert "organization_id" not in row
        assert "campaign_id" not in row

    day1, day2, day3, day4 = rows
    assert day1["spend"] == pytest.approx(100.0)
    assert day1["revenue"] == pytest.approx(400.0)
    assert day1["clicks"] == 50
    assert day1["impressions"] == 1000
    assert day1["conversions"] == 5
    assert day1["ctr"] == pytest.approx(0.05)
    assert day1["cpc"] == pytest.approx(2.0)
    assert day1["cpa"] == pytest.approx(20.0)
    assert day1["roas"] == pytest.approx(4.0)

    assert day2["ctr"] == pytest.approx(0.05)
    assert day2["cpc"] == pytest.approx(1.5)
    assert day2["cpa"] == pytest.approx(15.0)
    assert day2["roas"] == pytest.approx(2.0)

    # No conversions: cpa is null, but roas is 0 (spend > 0), not null.
    assert day3["cpa"] is None
    assert day3["roas"] == pytest.approx(0.0)
    assert day3["ctr"] == pytest.approx(0.02)

    # Division by zero must give null, never a 500.
    assert day4["ctr"] is None
    assert day4["cpc"] is None
    assert day4["cpa"] is None
    assert day4["roas"] is None


def test_metrics_date_range_is_inclusive(client: TestClient, world: World) -> None:
    response = client.get(
        _metrics_url(world.org_a, world.alpha),
        headers=auth_header(world.token_a),
        params={"from": "2026-01-02", "to": "2026-01-03"},
    )

    assert response.status_code == 200
    assert [row["date"] for row in response.json()] == ["2026-01-02", "2026-01-03"]


def test_metrics_empty_results_return_200_and_empty_list(client: TestClient, world: World) -> None:
    headers = auth_header(world.token_a)

    outside_range = client.get(
        _metrics_url(world.org_a, world.alpha),
        headers=headers,
        params={"from": "2020-01-01", "to": "2020-01-31"},
    )
    assert outside_range.status_code == 200
    assert outside_range.json() == []

    campaign_without_data = client.get(
        _metrics_url(world.org_a, world.beta), headers=headers, params=_FULL_RANGE
    )
    assert campaign_without_data.status_code == 200
    assert campaign_without_data.json() == []


def test_metrics_rejects_missing_or_invalid_params(client: TestClient, world: World) -> None:
    url = _metrics_url(world.org_a, world.alpha)
    headers = auth_header(world.token_a)
    bad_params: list[dict[str, str]] = [
        {},
        {"from": "2026-01-01"},
        {"to": "2026-01-04"},
        {"from": "2026-01-04", "to": "2026-01-01"},
        {"from": "not-a-date", "to": "2026-01-04"},
    ]

    for params in bad_params:
        response = client.get(url, headers=headers, params=params)
        assert response.status_code == 422, params


def test_metrics_of_another_orgs_campaign_returns_404(client: TestClient, world: World) -> None:
    headers = auth_header(world.token_a)

    # Own org in the URL, org B's campaign: 404, not an empty list and not org B's numbers.
    own_url = client.get(
        _metrics_url(world.org_a, world.gamma), headers=headers, params=_FULL_RANGE
    )
    assert own_url.status_code == 404

    # Org B in the URL with org A's token: rejected by the URL org check.
    foreign_url = client.get(
        _metrics_url(world.org_b, world.gamma), headers=headers, params=_FULL_RANGE
    )
    assert foreign_url.status_code == 404

    # Unknown campaign id looks identical to "not yours".
    unknown = client.get(_metrics_url(world.org_a, uuid4()), headers=headers, params=_FULL_RANGE)
    assert unknown.status_code == 404
