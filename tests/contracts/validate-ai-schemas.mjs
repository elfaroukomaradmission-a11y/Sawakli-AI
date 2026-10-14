/**
 * QA-00 Contract Validator — AI Layer Output Schemas
 *
 * Usage: node tests/contracts/validate-ai-schemas.mjs [--contract <path>] [--deviations <path>]
 * Exit 0 = all matched, Exit 1 = mismatches found.
 */

import { runValidator } from './contract-lib.mjs'

const FILES = ['ai/forecasting/schemas.py', 'ai/recommendations/schemas.py']

const MODELS = [
  { entity: 'forecasts', model: 'ForecastRecord', file: 'ai/forecasting/schemas.py' },
  { entity: 'recommendations', model: 'Recommendation', file: 'ai/recommendations/schemas.py' },
  { entity: 'anomalies', model: 'AnomalySignal', file: 'ai/recommendations/schemas.py' },
]

const ENUMS = []

runValidator('QA-00 AI Contract Validation', 'ai', FILES, MODELS, ENUMS)
