/**
 * QA-01 Contract Validator — DB SQL Migrations
 *
 * Parses the Alembic migration files in apps/backend/alembic/versions/
 * and checks that every canonical enum value and table column is present
 * in the SQL CREATE statements.
 *
 * Usage: node tests/contracts/validate-db-schema.mjs
 * Exit 0 = all matched, Exit 1 = mismatches found.
 */

import { readFileSync, readdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '../..')
const MIGRATIONS_DIR = resolve(ROOT, 'apps/backend/alembic/versions')

const canonical = JSON.parse(
  readFileSync(resolve(__dirname, 'canonical.json'), 'utf-8')
)

const errors = []

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
    errors.push(`ENUM ${enumName}: not found in any migration file`)
    continue
  }

  const sqlValues = []
  for (const m of match[1].matchAll(/'([^']+)'/g)) {
    sqlValues.push(m[1])
  }

  for (const val of canonicalValues) {
    if (!sqlValues.includes(val)) {
      errors.push(`ENUM ${enumName}: missing value '${val}' in SQL`)
    }
  }

  for (const val of sqlValues) {
    if (!canonicalValues.includes(val)) {
      errors.push(`ENUM ${enumName}: extra value '${val}' in SQL not in canonical`)
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
    errors.push(`TABLE ${entityName}: CREATE TABLE not found in any migration`)
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
        errors.push(
          `TABLE ${entityName}: column '${fieldName}' (${fieldDef.type}) not found in SQL`
        )
      }
    }
  }
}

// --- Report ---

if (errors.length > 0) {
  console.error('\n=== QA-01 DB Contract Validation FAILED ===\n')
  for (const e of errors) {
    console.error(`  ✗ ${e}`)
  }
  console.error(`\n  ${errors.length} error(s) found.\n`)
  process.exit(1)
} else {
  console.log('\n=== QA-01 DB Contract Validation PASSED ===')
  console.log('  All DB tables match the canonical contract.\n')
  process.exit(0)
}
