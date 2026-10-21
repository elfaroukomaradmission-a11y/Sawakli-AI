/**
 * QA-00 Contract Validator — Backend Pydantic Models
 *
 * Statically reads the Backend API response models and StrEnums (no app import) and compares them
 * with canonical.json: field presence, type compatibility, nullability and enum values in both
 * directions. API renames and intentionally unexposed columns are declared per model below with a
 * reason; genuine mismatches must be listed in known-deviations.json. Anything else fails.
 *
 * Request models and wrapper responses (RegisterResponse, LoginResponse, MeResponse) are not
 * entity projections; their nested UserPublic / OrganizationPublic are checked directly.
 *
 * Usage: node tests/contracts/validate-backend-models.mjs [--contract <path>] [--deviations <path>]
 *        [--source-root <dir>]
 * Exit 0 = all matched, Exit 1 = mismatches found.
 */

import { runValidator } from './contract-lib.mjs'

const FILES = [
  'api/schemas/auth.py',
  'api/schemas/jobs.py',
  'api/routes/jobs.py',
  'api/routes/connectors.py',
  'shared/enums.py',
  'connectors/oauth/models.py',
]

const NOT_EXPOSED = 'not exposed by this API response'
const JOB_ID = { job_id: 'id' }

const MODELS = [
  {
    entity: 'users',
    model: 'UserPublic',
    file: 'api/schemas/auth.py',
    omitted: { hashed_password: 'never leaves Backend (ui_excluded)', created_at: `${NOT_EXPOSED} (ui_excluded)` },
  },
  {
    entity: 'organizations',
    model: 'OrganizationPublic',
    file: 'api/schemas/auth.py',
    omitted: { plan: NOT_EXPOSED, created_at: NOT_EXPOSED },
  },
  {
    entity: 'jobs',
    model: 'JobStatusResponse',
    file: 'api/schemas/jobs.py',
    renames: JOB_ID,
    omitted: Object.fromEntries(
      ['organization_id', 'triggered_by_user_id', 'priority', 'model_run_id', 'claimed_at'].map((f) => [f, NOT_EXPOSED])
    ),
  },
  {
    entity: 'jobs',
    model: 'AnalysisRefreshResponse',
    file: 'api/schemas/jobs.py',
    renames: JOB_ID,
    omitted: Object.fromEntries(
      ['organization_id', 'campaign_ids', 'triggered_by_user_id', 'priority', 'created_at', 'model_run_id', 'claimed_at'].map(
        (f) => [f, NOT_EXPOSED]
      )
    ),
  },
  {
    entity: 'jobs',
    model: 'JobPublic',
    file: 'api/routes/jobs.py',
    omitted: Object.fromEntries(
      ['campaign_ids', 'triggered_by_user_id', 'status', 'priority', 'created_at', 'model_run_id', 'claimed_at'].map((f) => [
        f,
        NOT_EXPOSED,
      ])
    ),
  },
  {
    entity: 'data_sources',
    model: 'ConnectorSetupResponse',
    file: 'api/routes/connectors.py',
    renames: { data_source_id: 'id' },
    omitted: { organization_id: NOT_EXPOSED, last_error: NOT_EXPOSED },
  },
  {
    entity: 'data_sources',
    model: 'CsvUploadResponse',
    file: 'api/routes/connectors.py',
    renames: { data_source_id: 'id' },
    omitted: { organization_id: NOT_EXPOSED, provider: NOT_EXPOSED, status: NOT_EXPOSED, last_error: NOT_EXPOSED },
    extras: {
      row_count: 'upload result, not a data_sources column',
      parsed_rows: 'upload result, not a data_sources column',
      parse_warnings: 'upload result, not a data_sources column',
    },
  },
]

const ENUMS = [
  { enumName: 'job_status_enum', pyName: 'JobStatus' },
  { enumName: 'provider_enum', pyName: 'Provider' },
]

runValidator('QA-00 Backend Contract Validation', 'backend', FILES, MODELS, ENUMS)
