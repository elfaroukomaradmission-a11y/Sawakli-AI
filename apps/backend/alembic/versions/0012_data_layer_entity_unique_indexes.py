"""Add DATA-04 entity uniqueness indexes."""

from collections.abc import Sequence

from sawakli.db.migration_utils import execute_sql_script

revision: str = "0012_entity_unique_indexes"
down_revision: str | Sequence[str] | None = "9a94fe7a02ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add uniqueness rules for normalized entities."""

    execute_sql_script(
        """
        -- Campaign CSV fallback: data source + name + platform.
        DROP INDEX IF EXISTS idx_campaigns_unique_name_csv;

        CREATE UNIQUE INDEX idx_campaigns_unique_name_csv
        ON campaigns (data_source_id, name, platform)
        WHERE external_id IS NULL;

        -- Ad group external ID within a campaign.
        CREATE UNIQUE INDEX idx_ad_groups_unique_external
        ON ad_groups (campaign_id, external_id)
        WHERE external_id IS NOT NULL;

        -- CSV ad group fallback: name within a campaign.
        CREATE UNIQUE INDEX idx_ad_groups_unique_name
        ON ad_groups (campaign_id, name)
        WHERE external_id IS NULL;

        -- Ad external ID within an ad group.
        CREATE UNIQUE INDEX idx_ads_unique_external
        ON ads (ad_group_id, external_id)
        WHERE external_id IS NOT NULL;

        -- CSV ad fallback: name within an ad group.
        CREATE UNIQUE INDEX idx_ads_unique_name
        ON ads (ad_group_id, name)
        WHERE external_id IS NULL;

        -- Provider-owned creative identifier.
        ALTER TABLE creatives
        ADD COLUMN external_id TEXT;

        -- Creative external ID within an ad.
        CREATE UNIQUE INDEX idx_creatives_unique_external
        ON creatives (ad_id, external_id)
        WHERE external_id IS NOT NULL;

        -- CSV creative fallback: headline within an ad.
        CREATE UNIQUE INDEX idx_creatives_unique_headline
        ON creatives (ad_id, headline)
        WHERE external_id IS NULL;
        """
    )


def downgrade() -> None:
    """Remove DATA-04 uniqueness rules."""

    execute_sql_script(
        """
        -- Remove creative constraints and column.
        DROP INDEX IF EXISTS idx_creatives_unique_headline;
        DROP INDEX IF EXISTS idx_creatives_unique_external;

        ALTER TABLE creatives
        DROP COLUMN IF EXISTS external_id;

        -- Remove ad and ad group constraints.
        DROP INDEX IF EXISTS idx_ads_unique_name;
        DROP INDEX IF EXISTS idx_ads_unique_external;
        DROP INDEX IF EXISTS idx_ad_groups_unique_name;
        DROP INDEX IF EXISTS idx_ad_groups_unique_external;

        -- Restore the original campaign fallback index.
        DROP INDEX IF EXISTS idx_campaigns_unique_name_csv;

        CREATE UNIQUE INDEX idx_campaigns_unique_name_csv
        ON campaigns (data_source_id, name)
        WHERE external_id IS NULL;
        """
    )
