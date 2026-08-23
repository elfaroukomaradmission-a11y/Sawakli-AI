# Database Migration Conventions

## Purpose

This directory contains Alembic database migrations for Sawakli AI.

## Migration Naming

Migration files must use:

`<revision>_<short_description>.py`

Examples:

- `a1b2c3d4_core_identity.py`
- `b2c3d4e5_data_sources.py`
- `c3d4e5f6_campaign_metrics.py`
- `d4e5f6g7_jobs.py`
- `e5f6g7h8_ai_outputs.py`

The description should be short, lowercase, and use underscores.

## Migration Ordering

Migrations should be introduced in dependency order:

1. Core identity
2. Data sources
3. Campaign metrics
4. Jobs
5. AI outputs

When a new model depends on an existing domain, its migration should be placed after the migration that establishes that dependency.

## Rules

- Never edit an already-applied migration.
- Create a new migration for schema changes.
- Keep each migration focused on one logical schema change.
- Use Alembic's revision chain to preserve ordering.
- Migration files belong in `alembic/versions/`.