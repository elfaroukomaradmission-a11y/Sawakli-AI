from typing import Any
from uuid import UUID

from .models import StagedCampaignRow, StagedDailyMetricRow, StagedGAEventRow


def staged_row_from_csv_dict(
    organization_id: UUID,
    data_source_id: UUID,
    parsed_row: dict[str, Any],
) -> StagedCampaignRow:
    return StagedCampaignRow(
        organization_id=organization_id,
        data_source_id=data_source_id,
        provider="csv_demo",
        external_id=None,
        campaign_name=parsed_row["campaign_name"],
        platform_raw=parsed_row["platform"],
        objective=None,
        status_raw=None,
        budget=None,
        start_date_raw=parsed_row["date"],
        end_date_raw=None,
        ad_group=None,
        daily_metric=StagedDailyMetricRow(
            date=parsed_row["date"],
            spend=str(parsed_row["spend"]),
            impressions=str(parsed_row["impressions"]),
            clicks=str(parsed_row["clicks"]),
            conversions=str(parsed_row["conversions"]),
            revenue=str(parsed_row["revenue"]),
        ),
        ga_event=StagedGAEventRow(
            date=parsed_row["date"],
            sessions=str(parsed_row.get("sessions", 0)),
            bounces=str(parsed_row.get("bounces", 0)),
        ),
    )
