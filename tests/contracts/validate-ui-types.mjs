/**
 * QA-01 Contract Validator — UI TypeScript Types
 *
 * Parses the TypeScript type files in apps/web/src/types/ and checks
 * that every canonical entity's required fields and enum values are
 * present in the corresponding UI type.
 *
 * Usage: node tests/contracts/validate-ui-types.mjs
 * Exit 0 = all matched, Exit 1 = mismatches found.
 */

import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '../..')
const TYPES_DIR = resolve(ROOT, 'apps/web/src/types')

const canonical = JSON.parse(
  readFileSync(resolve(__dirname, 'canonical.json'), 'utf-8')
)

const errors = []

function extractTypeBody(source, typeName) {
  const pattern = new RegExp(
    `export\\s+type\\s+${typeName}\\s*=\\s*\\{([^}]+)\\}`,
    's'
  )
  const match = source.match(pattern)
  return match ? match[1] : null
}

function extractUnionValues(source, typeName) {
  const pattern = new RegExp(
    `export\\s+type\\s+${typeName}\\s*=[\\s\\S]*?(?=\\n\\nexport|\\n\\n\\S|$)`,
    ''
  )
  const match = source.match(pattern)
  if (!match) return null
  const raw = match[0]
  const values = []
  for (const m of raw.matchAll(/'([^']+)'/g)) {
    values.push(m[1])
  }
  return values.length > 0 ? values : null
}

function extractFieldNames(body) {
  const fields = []
  for (const line of body.split('\n')) {
    const m = line.match(/^\s*(\w+)\??:/)
    if (m) fields.push(m[1])
  }
  return fields
}

// --- Enum validations ---

const ENUM_TO_UI_TYPE = {
  platform_enum: { file: 'campaign.ts', type: 'CampaignPlatform' },
  campaign_status_enum: { file: 'campaign.ts', type: 'CampaignStatus' },
  job_status_enum: { file: 'job.ts', type: 'JobStatus' },
  job_priority_enum: { file: 'job.ts', type: 'JobPriority' },
  anomaly_severity_enum: { file: 'anomaly.ts', type: 'AnomalySeverity' },
  anomaly_direction_enum: { file: 'anomaly.ts', type: 'AnomalyDirection' },
  recommendation_status_enum: { file: 'recommendation.ts', type: 'RecommendationStatus' },
  risk_rating_enum: { file: 'recommendation.ts', type: 'RiskRating' },
  simulation_scenario_enum: { file: 'simulation.ts', type: 'SimulationScenario' },
}

for (const [enumName, mapping] of Object.entries(ENUM_TO_UI_TYPE)) {
  const canonicalValues = canonical.enums[enumName]
  const source = readFileSync(resolve(TYPES_DIR, mapping.file), 'utf-8')
  const uiValues = extractUnionValues(source, mapping.type)

  if (!uiValues) {
    errors.push(`ENUM ${enumName}: UI type '${mapping.type}' not found in ${mapping.file}`)
    continue
  }

  for (const val of canonicalValues) {
    if (!uiValues.includes(val)) {
      errors.push(`ENUM ${enumName}: missing value '${val}' in UI type '${mapping.type}'`)
    }
  }

  for (const val of uiValues) {
    if (!canonicalValues.includes(val)) {
      errors.push(`ENUM ${enumName}: extra value '${val}' in UI type '${mapping.type}' not in canonical`)
    }
  }
}

// --- Entity field validations ---

const ENTITY_TO_UI_TYPE = {
  organizations: { file: 'organization.ts', type: 'Organization' },
  users: { file: 'user.ts', type: 'User' },
  campaigns: { file: 'campaign.ts', type: 'Campaign' },
  jobs: { file: 'job.ts', type: 'Job' },
  forecasts: { file: 'forecast.ts', type: 'Forecast' },
  anomalies: { file: 'anomaly.ts', type: 'Anomaly' },
  recommendations: { file: 'recommendation.ts', type: 'Recommendation' },
  action_simulations: { file: 'simulation.ts', type: 'Simulation' },
}

for (const [entityName, mapping] of Object.entries(ENTITY_TO_UI_TYPE)) {
  const entity = canonical.entities[entityName]
  if (!entity) continue

  const source = readFileSync(resolve(TYPES_DIR, mapping.file), 'utf-8')
  const body = extractTypeBody(source, mapping.type)

  if (!body) {
    errors.push(`ENTITY ${entityName}: UI type '${mapping.type}' not found in ${mapping.file}`)
    continue
  }

  const uiFields = extractFieldNames(body)

  for (const [fieldName, fieldDef] of Object.entries(entity.fields)) {
    if (fieldDef.ui_excluded) continue
    if (!uiFields.includes(fieldName)) {
      errors.push(
        `ENTITY ${entityName}: field '${fieldName}' missing from UI type '${mapping.type}'`
      )
    }
  }
}

// --- Report ---

if (errors.length > 0) {
  console.error('\n=== QA-01 UI Contract Validation FAILED ===\n')
  for (const e of errors) {
    console.error(`  ✗ ${e}`)
  }
  console.error(`\n  ${errors.length} error(s) found.\n`)
  process.exit(1)
} else {
  console.log('\n=== QA-01 UI Contract Validation PASSED ===')
  console.log('  All UI types match the canonical contract.\n')
  process.exit(0)
}
