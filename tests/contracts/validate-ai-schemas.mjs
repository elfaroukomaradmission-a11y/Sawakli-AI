/**
 * QA-00 Contract Validator — AI Layer Output Schemas
 *
 * Statically reads the AI output dataclasses, StrEnums and Literal aliases (no app import) and
 * compares them with canonical.json: field presence, type compatibility, nullability and enum values
 * in both directions. Intentional differences are declared per model below with a reason; genuine
 * mismatches must be listed in known-deviations.json. Anything else fails.
 *
 * Usage: node tests/contracts/validate-ai-schemas.mjs [--contract <path>] [--deviations <path>]
 *        [--source-root <dir>]
 * Exit 0 = all matched, Exit 1 = mismatches found.
 */

import { runValidator } from './contract-lib.mjs'

const FILES = ['ai/forecasting/schemas.py', 'ai/recommendations/schemas.py']

const PERSISTENCE_ONLY = 'minted when AI-06 persists the row; never present in memory'

const MODELS = [
  {
    entity: 'forecasts',
    model: 'ForecastRecord',
    file: 'ai/forecasting/schemas.py',
    omitted: { id: PERSISTENCE_ONLY, model_run_id: PERSISTENCE_ONLY, created_at: PERSISTENCE_ONLY },
    extras: {
      horizon_days: 'in-memory forecast metadata (AI-03), not a table column',
      generated_from_date: 'in-memory forecast metadata (AI-03), not a table column',
    },
  },
  {
    entity: 'recommendations',
    model: 'Recommendation',
    file: 'ai/recommendations/schemas.py',
    omitted: {
      id: PERSISTENCE_ONLY,
      model_run_id: PERSISTENCE_ONLY,
      status: 'defaulted by AI-06 on persistence (dataclass docstring)',
      created_at: PERSISTENCE_ONLY,
    },
    extras: { rule_id: 'traceability only; persister drops it or folds it into evidence (dataclass docstring)' },
  },
  {
    entity: 'anomalies',
    model: 'AnomalySignal',
    file: 'ai/recommendations/schemas.py',
    omitted: {
      model_run_id: 'narrow read-only view: AI-04 reads only the columns it needs',
      detected_at: 'narrow read-only view: AI-04 reads only the columns it needs',
      detectors_triggered: 'narrow read-only view: AI-04 reads only the columns it needs',
      created_at: 'narrow read-only view: AI-04 reads only the columns it needs',
    },
    optional: { id: 'read-only view, never written; optional so fixtures can omit it' },
  },
]

const ENUMS = [
  { enumName: 'anomaly_direction_enum', pyName: 'AnomalyDirection' },
  { enumName: 'anomaly_severity_enum', pyName: 'AnomalySeverity' },
  { enumName: 'risk_rating_enum', pyName: 'RiskRating' },
]

runValidator('QA-00 AI Contract Validation', 'ai', FILES, MODELS, ENUMS)
