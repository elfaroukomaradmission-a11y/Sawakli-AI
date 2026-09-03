"""Organization-scoped database and local CSV loaders for AI-01."""

from __future__ import annotations

import csv
from collections.abc import Collection, Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol, cast
from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from sqlalchemy.orm import Session

from sawakli.db.tables import campaigns_table, daily_metrics_table

from .schemas import FeatureDataError, MetricRecord

REQUIRED_CSV_COLUMNS = frozenset(
    {
        "date",
        "campaign_name",
        "platform",
        "spend",
        "impressions",
        "clicks",
        "conversions",
        "revenue",
    }
)
OPTIONAL_CSV_COLUMNS = frozenset({"sessions", "bounces"})
SUPPORTED_PLATFORMS = frozenset({"meta", "google"})

CampaignKey = tuple[str, str]


class DataLoader(Protocol):
    """Common typed contract implemented by both AI-01 loading modes."""

    def load_metrics(
        self,
        organization_id: UUID,
        campaign_ids: Collection[UUID] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[MetricRecord, ...]: ...


class DatabaseDataLoader:
    """Read canonical facts using the repository's synchronous SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def load_metrics(
        self,
        organization_id: UUID,
        campaign_ids: Collection[UUID] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[MetricRecord, ...]:
        _validate_date_range(date_from, date_to)
        normalized_campaign_ids = tuple(
            sorted(set(campaign_ids or ()), key=lambda value: value.int)
        )
        if campaign_ids is not None and not normalized_campaign_ids:
            return ()

        metrics = daily_metrics_table
        campaigns = campaigns_table
        organization_match = sa.and_(
            metrics.c.campaign_id == campaigns.c.id,
            metrics.c.organization_id == campaigns.c.organization_id,
        )
        statement = (
            sa.select(
                metrics.c.organization_id,
                metrics.c.campaign_id,
                campaigns.c.name.label("campaign_name"),
                campaigns.c.platform,
                metrics.c.date,
                metrics.c.spend,
                metrics.c.impressions,
                metrics.c.clicks,
                metrics.c.conversions,
                metrics.c.revenue,
            )
            .select_from(metrics.join(campaigns, organization_match))
            # Both sides are scoped explicitly. This also rejects inconsistent
            # rows where a metric and its campaign claim different tenants.
            .where(
                metrics.c.organization_id == organization_id,
                campaigns.c.organization_id == organization_id,
            )
        )
        if normalized_campaign_ids:
            statement = statement.where(metrics.c.campaign_id.in_(normalized_campaign_ids))
        if date_from is not None:
            statement = statement.where(metrics.c.date >= date_from)
        if date_to is not None:
            statement = statement.where(metrics.c.date <= date_to)
        statement = statement.order_by(metrics.c.campaign_id.asc(), metrics.c.date.asc())

        records = tuple(
            MetricRecord(
                organization_id=cast(UUID, row.organization_id),
                campaign_id=cast(UUID, row.campaign_id),
                campaign_name=cast(str, row.campaign_name),
                platform=str(row.platform),
                date=cast(date, row.date),
                spend=_database_decimal(row.spend, "spend"),
                impressions=_database_int(row.impressions, "impressions"),
                clicks=_database_int(row.clicks, "clicks"),
                conversions=_database_int(row.conversions, "conversions"),
                revenue=_database_decimal(row.revenue, "revenue"),
            )
            for row in self._session.execute(statement)
        )
        _validate_records(records, expected_organization_id=organization_id)
        return records


class CsvDataLoader:
    """Load DATA-02-shaped CSV data without relying on a global artifact."""

    def __init__(
        self,
        path: str | Path,
        *,
        campaign_id_map: Mapping[CampaignKey, UUID] | None = None,
    ) -> None:
        self._path = Path(path)
        self._campaign_id_map = _normalize_campaign_id_map(campaign_id_map or {})

    def load_metrics(
        self,
        organization_id: UUID,
        campaign_ids: Collection[UUID] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> tuple[MetricRecord, ...]:
        _validate_date_range(date_from, date_to)
        requested_campaign_ids = set(campaign_ids) if campaign_ids is not None else None
        records = self._read_records(organization_id)
        filtered = tuple(
            record
            for record in records
            if (requested_campaign_ids is None or record.campaign_id in requested_campaign_ids)
            and (date_from is None or record.date >= date_from)
            and (date_to is None or record.date <= date_to)
        )
        return tuple(sorted(filtered, key=lambda record: (record.campaign_id.int, record.date)))

    def _read_records(self, organization_id: UUID) -> tuple[MetricRecord, ...]:
        try:
            csv_file = self._path.open(encoding="utf-8", newline="")
        except (OSError, UnicodeError) as exc:
            raise FeatureDataError(f"could not read CSV {self._path}: {exc}") from exc

        with csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise FeatureDataError("CSV is empty or has no header row")
            fieldnames = tuple(name.strip() for name in reader.fieldnames)
            if len(fieldnames) != len(set(fieldnames)):
                raise FeatureDataError("CSV header contains duplicate column names")
            reader.fieldnames = list(fieldnames)
            missing = sorted(REQUIRED_CSV_COLUMNS.difference(fieldnames))
            if missing:
                raise FeatureDataError(f"CSV is missing required columns: {', '.join(missing)}")

            records = tuple(
                self._parse_row(organization_id, row_number, row)
                for row_number, row in enumerate(reader, start=2)
            )

        if not records:
            raise FeatureDataError("CSV contains no data rows")
        _validate_records(records, expected_organization_id=organization_id)
        return records

    def _parse_row(
        self,
        organization_id: UUID,
        row_number: int,
        row: Mapping[str | None, str | None],
    ) -> MetricRecord:
        if None in row:
            raise FeatureDataError(f"row {row_number}: contains more values than the header")
        campaign_name = _required_text(row, "campaign_name", row_number)
        platform = _required_text(row, "platform", row_number).lower()
        if platform not in SUPPORTED_PLATFORMS:
            raise FeatureDataError(
                f"row {row_number}: unsupported platform {platform!r}; expected meta or google"
            )
        campaign_key = (campaign_name, platform)
        campaign_id = self._campaign_id_map.get(
            campaign_key,
            local_campaign_id(organization_id, campaign_name, platform),
        )

        sessions = _optional_nonnegative_int(row, "sessions", row_number)
        bounces = _optional_nonnegative_int(row, "bounces", row_number)
        if sessions is not None and bounces is not None and bounces > sessions:
            raise FeatureDataError(
                f"row {row_number}: bounces ({bounces}) cannot exceed sessions ({sessions})"
            )

        return MetricRecord(
            organization_id=organization_id,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            platform=platform,
            date=_required_date(row, "date", row_number),
            spend=_required_nonnegative_decimal(row, "spend", row_number),
            impressions=_required_nonnegative_int(row, "impressions", row_number),
            clicks=_required_nonnegative_int(row, "clicks", row_number),
            conversions=_required_nonnegative_int(row, "conversions", row_number),
            revenue=_required_nonnegative_decimal(row, "revenue", row_number),
            sessions=sessions,
            bounces=bounces,
        )


def local_campaign_id(organization_id: UUID, campaign_name: str, platform: str) -> UUID:
    """Return the stable UUID used for an unmapped local campaign."""

    identity = (
        f"sawakli-ai-local:{organization_id}:{platform.strip().lower()}:{campaign_name.strip()}"
    )
    return uuid5(NAMESPACE_URL, identity)


def _normalize_campaign_id_map(
    campaign_id_map: Mapping[CampaignKey, UUID],
) -> dict[CampaignKey, UUID]:
    normalized: dict[CampaignKey, UUID] = {}
    for (campaign_name, platform), campaign_id in campaign_id_map.items():
        key = (campaign_name.strip(), platform.strip().lower())
        existing = normalized.get(key)
        if existing is not None and existing != campaign_id:
            raise FeatureDataError(f"conflicting campaign IDs supplied for {key!r}")
        normalized[key] = campaign_id
    return normalized


def _required_text(row: Mapping[str | None, str | None], field: str, row_number: int) -> str:
    value = row.get(field)
    if value is None or not value.strip():
        raise FeatureDataError(f"row {row_number}: {field} is required")
    return value.strip()


def _required_date(row: Mapping[str | None, str | None], field: str, row_number: int) -> date:
    value = _required_text(row, field, row_number)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise FeatureDataError(
            f"row {row_number}: {field} must be a valid ISO date (YYYY-MM-DD)"
        ) from exc


def _required_nonnegative_decimal(
    row: Mapping[str | None, str | None], field: str, row_number: int
) -> Decimal:
    value = _required_text(row, field, row_number)
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise FeatureDataError(f"row {row_number}: {field} must be numeric") from exc
    if not parsed.is_finite():
        raise FeatureDataError(f"row {row_number}: {field} must be finite")
    if parsed < 0:
        raise FeatureDataError(f"row {row_number}: {field} must be non-negative")
    return parsed


def _required_nonnegative_int(
    row: Mapping[str | None, str | None], field: str, row_number: int
) -> int:
    parsed = _required_nonnegative_decimal(row, field, row_number)
    if parsed != parsed.to_integral_value():
        raise FeatureDataError(f"row {row_number}: {field} must be an integer")
    return int(parsed)


def _optional_nonnegative_int(
    row: Mapping[str | None, str | None], field: str, row_number: int
) -> int | None:
    value = row.get(field)
    if value is None or not value.strip():
        return None
    return _required_nonnegative_int(row, field, row_number)


def _database_decimal(value: object, field: str) -> Decimal:
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as exc:
        raise FeatureDataError(f"database field {field} is not numeric") from exc
    if not parsed.is_finite():
        raise FeatureDataError(f"database field {field} must be finite")
    return parsed


def _database_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise FeatureDataError(f"database field {field} must be an integer")
    parsed = _database_decimal(value, field)
    if parsed != parsed.to_integral_value():
        raise FeatureDataError(f"database field {field} must be an integer")
    return int(parsed)


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise FeatureDataError("date_from cannot be later than date_to")


def _validate_records(
    records: Sequence[MetricRecord], *, expected_organization_id: UUID | None = None
) -> None:
    seen: set[tuple[UUID, date]] = set()
    for record in records:
        if (
            expected_organization_id is not None
            and record.organization_id != expected_organization_id
        ):
            raise FeatureDataError("source returned a record outside the requested organization")
        if not record.campaign_name.strip():
            raise FeatureDataError("campaign_name cannot be empty")
        if record.platform not in SUPPORTED_PLATFORMS:
            raise FeatureDataError(f"unsupported platform: {record.platform!r}")
        if not isinstance(record.spend, Decimal) or not isinstance(record.revenue, Decimal):
            raise FeatureDataError("spend and revenue must use Decimal")
        for field, value in (
            ("impressions", record.impressions),
            ("clicks", record.clicks),
            ("conversions", record.conversions),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise FeatureDataError(f"{field} must be an integer")
        for raw_field, raw_value in (
            ("spend", record.spend),
            ("impressions", record.impressions),
            ("clicks", record.clicks),
            ("conversions", record.conversions),
            ("revenue", record.revenue),
        ):
            if isinstance(raw_value, Decimal) and not raw_value.is_finite():
                raise FeatureDataError(f"{raw_field} must be finite")
            if raw_value < 0:
                raise FeatureDataError(f"{raw_field} must be non-negative")
        for optional_field, optional_value in (
            ("sessions", record.sessions),
            ("bounces", record.bounces),
        ):
            if optional_value is not None and (
                isinstance(optional_value, bool) or not isinstance(optional_value, int)
            ):
                raise FeatureDataError(f"{optional_field} must be an integer")
            if optional_value is not None and optional_value < 0:
                raise FeatureDataError(f"{optional_field} must be non-negative")
        if record.session_duration is not None:
            if not isinstance(record.session_duration, Decimal):
                raise FeatureDataError("session_duration must use Decimal")
            if not record.session_duration.is_finite():
                raise FeatureDataError("session_duration must be finite")
        if (
            record.sessions is not None
            and record.bounces is not None
            and record.bounces > record.sessions
        ):
            raise FeatureDataError("bounces cannot exceed sessions")
        key = (record.campaign_id, record.date)
        if key in seen:
            raise FeatureDataError(
                f"duplicate campaign/date record: {record.campaign_id} on {record.date.isoformat()}"
            )
        seen.add(key)
