/**
 * QA-01 Contract Validator — DB SQL Migrations (extended by QA-00)
 *
 * Parses the Alembic migration files in apps/backend/alembic/versions/
 * and checks that every canonical enum value and table column is present
 * in the SQL CREATE statements. Enum values added later with
 * `ALTER TYPE ... ADD VALUE` count too (QA-00). Mismatches listed in
 * known-deviations.json (validator "db") are accepted; stale entries fail.
 *
 * Usage: node tests/contracts/validate-db-schema.mjs [--contract <path>] [--deviations <path>]
 * Exit 0 = all matched, Exit 1 = mismatches found.
 */

import { readFileSync, readdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { CONTRACT_PATH, applyDeviations, kindCounts } from './contract-lib.mjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '../..')
const MIGRATIONS_DIR = resolve(ROOT, 'apps/backend/alembic/versions')

const canonical = JSON.parse(readFileSync(CONTRACT_PATH, 'utf-8'))

// Every finding carries its own exact key so one allowlist entry can accept only that finding.
const errors = []
const issue = (entity, field, kind, value, detail) => ({ validator: 'db', entity, model: 'migrations', field, kind, value, detail })

function getAllMigrationSQL() {
  const files = readdirSync(MIGRATIONS_DIR).filter((f) => f.endsWith('.py'))
  let combined = ''
  for (const f of files) {
    combined += readFileSync(resolve(MIGRATIONS_DIR, f), 'utf-8') + '\n'
  }
  return combined
}

const allSQL = getAllMigrationSQL()

// --- Enum validations ---

for (const [enumName, canonicalValues] of Object.entries(canonical.enums)) {
  const pattern = new RegExp(
    `CREATE\\s+TYPE\\s+${enumName}\\s+AS\\s+ENUM\\s*\\(([^)]+)\\)`,
    'si'
  )
  const match = allSQL.match(pattern)

  if (!match) {
    errors.push(issue(`enum:${enumName}`, '*', 'enum_not_found', null, `ENUM ${enumName}: not found in any migration file`))
    continue
  }

  const sqlValues = []
  for (const m of match[1].matchAll(/'([^']+)'/g)) {
    sqlValues.push(m[1])
  }
  const addValuePattern = new RegExp(
    `ALTER\\s+TYPE\\s+${enumName}\\s+ADD\\s+VALUE\\s+(?:IF\\s+NOT\\s+EXISTS\\s+)?'([^']+)'`,
    'gi'
  )
  for (const m of allSQL.matchAll(addValuePattern)) {
    if (!sqlValues.includes(m[1])) sqlValues.push(m[1])
  }

  for (const val of canonicalValues) {
    if (!sqlValues.includes(val)) {
      errors.push(issue(`enum:${enumName}`, '*', 'enum_value_missing', val, `ENUM ${enumName}: missing value '${val}' in SQL`))
    }
  }

  for (const val of sqlValues) {
    if (!canonicalValues.includes(val)) {
      errors.push(issue(`enum:${enumName}`, '*', 'enum_value_extra', val, `ENUM ${enumName}: extra value '${val}' in SQL not in canonical`))
    }
  }
}

// --- Entity/table column validations ---

for (const [entityName, entity] of Object.entries(canonical.entities)) {
  const pattern = new RegExp(
    `CREATE\\s+TABLE\\s+${entityName}\\s*\\(([\\s\\S]*?)\\);`,
    'i'
  )
  const match = allSQL.match(pattern)

  if (!match) {
    errors.push(issue(entityName, '*', 'table_not_found', null, `TABLE ${entityName}: CREATE TABLE not found in any migration`))
    continue
  }

  const tableBody = match[1]
  const sqlColumns = []
  for (const line of tableBody.split('\n')) {
    const colMatch = line.match(/^\s+(\w+)\s+/)
    if (
      colMatch &&
      !line.trim().startsWith('CONSTRAINT') &&
      !line.trim().startsWith('PRIMARY KEY') &&
      !line.trim().startsWith('--') &&
      !line.trim().startsWith('COMMENT')
    ) {
      sqlColumns.push(colMatch[1])
    }
  }

  for (const [fieldName, fieldDef] of Object.entries(entity.fields)) {
    if (!sqlColumns.includes(fieldName)) {
      const addColumnPattern = new RegExp(
        `add_column\\s*\\(\\s*["']${entityName}["']\\s*,\\s*sa\\.Column\\s*\\(\\s*["']${fieldName}["']`,
        'i'
      )
      if (!allSQL.match(addColumnPattern)) {
        errors.push(issue(entityName, fieldName, 'missing_column', null, `TABLE ${entityName}: column '${fieldName}' (${fieldDef.type}) not found in SQL`))
      }
    }
  }
}

// --- Report ---

const { accepted, failures } = applyDeviations('db', errors)

if (accepted.length) console.log(`\n  Accepted known deviations (${accepted.length}): ${kindCounts(accepted)}`)
for (const { issue, entry } of accepted) {
  console.log(`  ~ (${entry.kind}) ${issue.detail} [${entry.task}, ${entry.owner}]`)
}

if (failures.length > 0) {
  console.error('\n=== QA-01 DB Contract Validation FAILED ===\n')
  for (const e of failures) {
    console.error(`  ✗ [${e.kind}] ${e.detail}`)
  }
  console.error(`\n  ${failures.length} error(s) found.\n`)
  process.exit(1)
} else {
  console.log('\n=== QA-01 DB Contract Validation PASSED ===')
  console.log('  All DB tables match the canonical contract.\n')
  process.exit(0)
}
