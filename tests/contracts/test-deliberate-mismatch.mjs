/**
 * QA-01 Deliberate Mismatch Test (rewritten by QA-00)
 *
 * Proves every contract validator fails visibly on an injected mismatch instead of passing:
 * contract-side cases for every validator (DB, UI, Backend, AI), Python-side cases on copied
 * Backend/AI source, a migration-side case on copied migrations, fail-closed cases, and allowlist
 * cases. Each case must exit 1, name every `expect` string and name no `forbid` string.
 * Tampering happens only on copies in the OS temp directory, passed via --contract / --deviations /
 * --source-root / --migrations-dir; the real canonical.json and known-deviations.json are hashed
 * before and after and must be byte-identical.
 *
 * Usage: node tests/contracts/test-deliberate-mismatch.mjs
 * Exit 0 = every validator caught its injected mismatch.
 * Exit 1 = a validator missed a mismatch, or a real contract file changed.
 */

import { readFileSync, writeFileSync, mkdtempSync, rmSync, cpSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { tmpdir } from 'node:os'
import { join, resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
const CANONICAL = resolve(__dirname, 'canonical.json')
const DEVIATIONS = resolve(__dirname, 'known-deviations.json')
const SOURCE = resolve(__dirname, '../../apps/backend/src/sawakli')
const MIGRATIONS = resolve(__dirname, '../../apps/backend/alembic/versions')
const sha256 = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')

const entry = (fields) => ({ reason: 'QA-00 negative test', task: 'QA-00', owner: 'QA-00 negative test', ...fields })
const inUserPublic = (replace) => (t) => t.replace(/(class UserPublic\(BaseModel\):\r?\n)/, `$1${replace}`)

const CASES = [
  // --- Contract side: one per validator ---
  {
    name: 'DB validator: fake column + fake enum value',
    validator: 'validate-db-schema.mjs',
    contract: (c) => {
      c.entities.anomalies.fields.fake_nonexistent_field = { type: 'varchar', nullable: false }
      c.enums.platform_enum.push('tiktok')
    },
    expect: ['fake_nonexistent_field', 'tiktok'],
  },
  {
    name: 'UI validator: fake field + fake enum value',
    validator: 'validate-ui-types.mjs',
    contract: (c) => {
      c.entities.anomalies.fields.fake_nonexistent_field = { type: 'varchar', nullable: false }
      c.enums.platform_enum.push('tiktok')
    },
    expect: ['fake_nonexistent_field', 'tiktok'],
  },
  {
    name: 'Backend validator: fake users field + fake job status',
    validator: 'validate-backend-models.mjs',
    contract: (c) => {
      c.entities.users.fields.fake_backend_field = { type: 'varchar', nullable: false }
      c.enums.job_status_enum.push('QUEUED')
    },
    expect: ['fake_backend_field', 'QUEUED'],
  },
  {
    name: 'AI validator: fake forecasts field + fake severity',
    validator: 'validate-ai-schemas.mjs',
    contract: (c) => {
      c.entities.forecasts.fields.fake_ai_field = { type: 'numeric', nullable: false }
      c.enums.anomaly_severity_enum.push('critical')
    },
    expect: ['fake_ai_field', 'critical'],
  },

  // --- Migration side ---
  {
    name: 'DB validator (migrations): quoted and schema-qualified ALTER TYPE ... ADD VALUE',
    validator: 'validate-db-schema.mjs',
    migrations: {
      'zz_qa00_tamper.py': `SQL = """\nALTER TYPE "job_status_enum" ADD VALUE 'QUEUED';\nALTER TYPE public.job_status_enum ADD VALUE IF NOT EXISTS 'ARCHIVED';\n"""\n`,
    },
    expect: ['QUEUED', 'ARCHIVED'],
  },

  // --- Python side ---
  {
    name: 'AI validator (Python side): field type changed',
    validator: 'validate-ai-schemas.mjs',
    source: { 'ai/forecasting/schemas.py': (t) => t.replace(/(class ForecastRecord[\s\S]*?metric_name: )str/, '$1int') },
    expect: ['type_mismatch', 'metric_name'],
  },
  {
    name: 'AI validator (Python side): undeclared extra field',
    validator: 'validate-ai-schemas.mjs',
    source: { 'ai/forecasting/schemas.py': (t) => t.replace(/(    generated_from_date: date\r?\n)/, '$1    debug_note: str\n') },
    expect: ['extra_field', 'debug_note'],
  },
  {
    name: 'AI validator (Python side): declaration left stale by a rename',
    validator: 'validate-ai-schemas.mjs',
    source: { 'ai/recommendations/schemas.py': (t) => t.replace('    rule_id: str', '    rule_key: str') },
    expect: ['stale_declaration', 'rule_id'],
  },
  {
    name: 'Backend validator (Python side): mapped class renamed away',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/auth.py': (t) => t.replace('class OrganizationPublic(BaseModel):', 'class OrganizationView(BaseModel):') },
    expect: ['model_not_found', 'OrganizationPublic'],
  },
  {
    name: 'Backend validator (Python side): inherited base class',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/auth.py': (t) => t.replace('class UserPublic(BaseModel):', 'class UserPublic(_Leaky, BaseModel):') },
    expect: ['unsupported_model_feature', 'base class _Leaky'],
  },
  {
    name: 'Backend validator (Python side): renamed field shadows a second field',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/jobs.py': (t) => t.replace(/(class JobStatusResponse\(BaseModel\):\r?\n)/, '$1    id: str\n') },
    expect: ['duplicate_mapping', "both map to 'id'"],
  },
  {
    name: 'Backend validator (Python side): Field(serialization_alias=...)',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/auth.py': (t) => t.replace(/(class UserPublic[\s\S]*?    id: UUID)/, '$1 = Field(serialization_alias="userId")') },
    expect: ['unsupported_model_feature', 'serialization_alias='],
  },
  {
    name: 'Backend validator (Python side): Field(exclude=True)',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/jobs.py': (t) => t.replace('    created_at: datetime', '    created_at: datetime = Field(exclude=True)') },
    expect: ['unsupported_model_feature', 'exclude='],
  },
  {
    name: 'Backend validator (Python side): dict-form model_config',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/auth.py': (t) => t.replace('model_config = ConfigDict(from_attributes=True)', 'model_config = {"from_attributes": True, "alias_generator": to_camel}') },
    expect: ['unsupported_model_feature', 'model_config'],
  },
  {
    name: 'Backend validator (Python side): nested class Config',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/auth.py': inUserPublic('    class Config:\n        alias_generator = to_camel\n\n') },
    expect: ['unsupported_model_feature', 'class Config'],
  },
  {
    name: 'Backend validator (Python side): @field_serializer',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/auth.py': inUserPublic('    @field_serializer("email")\n    def hide(self, value: str) -> str:\n        return ""\n\n') },
    expect: ['unsupported_model_feature', 'field_serializer'],
  },

  // --- Fail closed ---
  {
    name: 'AI validator: Python interpreter missing fails closed',
    validator: 'validate-ai-schemas.mjs',
    env: { PYTHON: 'qa00-no-such-python' },
    expect: ['Python extractor failed'],
  },

  // --- Allowlist ---
  {
    name: 'Known deviations: stale entry must fail',
    validator: 'validate-ai-schemas.mjs',
    deviations: (d) => {
      d.deviations.push(entry({ validator: 'ai', entity: 'forecasts', model: 'ForecastRecord', field: 'ghost_field', kind: 'breaking-mismatch', mismatch: 'missing_field' }))
    },
    expect: ['stale_deviation', 'ghost_field'],
    forbid: ['invalid_deviation_entry'],
  },
  {
    name: 'Known deviations: unknown kind must fail',
    validator: 'validate-db-schema.mjs',
    deviations: (d) => {
      d.deviations[0].kind = 'not-a-real-kind'
    },
    expect: ['invalid_deviation_entry', 'not-a-real-kind'],
  },
  {
    name: 'Known deviations: empty owner must fail',
    validator: 'validate-db-schema.mjs',
    deviations: (d) => {
      d.deviations[0].owner = ''
    },
    expect: ['invalid_deviation_entry', "'owner' is missing or empty"],
  },
  {
    name: 'Known deviations: duplicate entry must fail',
    validator: 'validate-ai-schemas.mjs',
    deviations: (d) => {
      d.deviations.push({ ...d.deviations[0] })
    },
    expect: ['invalid_deviation_entry', 'duplicates entry'],
  },
  {
    name: 'Known deviations: a fail-closed finding cannot be allowlisted',
    validator: 'validate-backend-models.mjs',
    source: { 'api/schemas/auth.py': (t) => t.replace('class OrganizationPublic(BaseModel):', 'class OrganizationView(BaseModel):') },
    deviations: (d) => {
      d.deviations.push(entry({ validator: 'backend', entity: 'organizations', model: 'OrganizationPublic', field: '*', kind: 'loose-typing', mismatch: 'model_not_found' }))
    },
    expect: ['invalid_deviation_entry', "mismatch 'model_not_found' cannot be allowlisted"],
  },
  {
    name: 'Known deviations: one entry matching two findings must fail',
    validator: 'validate-ai-schemas.mjs',
    source: { 'ai/recommendations/schemas.py': (t) => t.replace('RiskRating = Literal["low", "medium", "high"]', 'RiskRating = Literal["low", "medium", "high", "extreme", "extreme"]') },
    deviations: (d) => {
      d.deviations.push(entry({ validator: 'ai', entity: 'enum:risk_rating_enum', model: 'RiskRating', field: '*', kind: 'loose-typing', mismatch: 'enum_value_extra', value: 'extreme' }))
    },
    expect: ['ambiguous_deviation', 'matches 2 findings'],
  },
]

function copyAndTamper(from, to, tampers) {
  cpSync(from, to, { recursive: true, filter: (src) => !src.includes('__pycache__') })
  for (const [file, tamper] of Object.entries(tampers)) {
    const path = join(to, file)
    if (typeof tamper === 'string') {
      writeFileSync(path, tamper)
      continue
    }
    const original = readFileSync(path, 'utf-8')
    const changed = tamper(original)
    if (changed === original) throw new Error(`tamper did not change ${file}`)
    writeFileSync(path, changed)
  }
}

const before = { canonical: sha256(CANONICAL), deviations: sha256(DEVIATIONS) }
const workDir = mkdtempSync(join(tmpdir(), 'sawakli-contract-mismatch-'))
const results = []

try {
  CASES.forEach((testCase, i) => {
    const contract = JSON.parse(readFileSync(CANONICAL, 'utf-8'))
    const deviations = JSON.parse(readFileSync(DEVIATIONS, 'utf-8'))
    testCase.contract?.(contract)
    testCase.deviations?.(deviations)
    const contractPath = join(workDir, `contract-${i}.json`)
    const deviationsPath = join(workDir, `deviations-${i}.json`)
    writeFileSync(contractPath, JSON.stringify(contract, null, 2))
    writeFileSync(deviationsPath, JSON.stringify(deviations, null, 2))
    const args = ['--contract', contractPath, '--deviations', deviationsPath]
    if (testCase.source) {
      const sourceRoot = join(workDir, `source-${i}`)
      copyAndTamper(SOURCE, sourceRoot, testCase.source)
      args.push('--source-root', sourceRoot)
    }
    if (testCase.migrations) {
      const migrationsDir = join(workDir, `migrations-${i}`)
      copyAndTamper(MIGRATIONS, migrationsDir, testCase.migrations)
      args.push('--migrations-dir', migrationsDir)
    }

    const run = spawnSync(process.execPath, [resolve(__dirname, testCase.validator), ...args], {
      encoding: 'utf-8',
      env: { ...process.env, ...testCase.env },
    })
    const output = `${run.stdout}${run.stderr}`
    const missed = testCase.expect.filter((needle) => !output.includes(needle))
    const forbidden = (testCase.forbid ?? []).filter((needle) => output.includes(needle))
    const ok = run.status === 1 && missed.length === 0 && forbidden.length === 0
    const detail = ok
      ? `exit 1, named ${testCase.expect.join(', ')}`
      : `exit ${run.status}, not named: ${missed.join(', ') || '-'}, unexpected: ${forbidden.join(', ') || '-'}`
    results.push({ ok, name: testCase.name, detail, output })
  })
} finally {
  rmSync(workDir, { recursive: true, force: true })
}

const after = { canonical: sha256(CANONICAL), deviations: sha256(DEVIATIONS) }
const unchanged = before.canonical === after.canonical && before.deviations === after.deviations
const allOk = results.every((r) => r.ok) && unchanged

console.log(`\n=== QA-00 Deliberate Mismatch Test ${allOk ? 'PASSED' : 'FAILED'} ===`)
for (const r of results) {
  console.log(`  ${r.ok ? 'PASS' : 'FAIL'}  ${r.name} (${r.detail})`)
  if (!r.ok) console.log(r.output.replace(/^/gm, '        | '))
}
console.log(`  ${unchanged ? 'PASS' : 'FAIL'}  real files unchanged: canonical.json sha256 ${before.canonical} -> ${after.canonical}`)
console.log(`                       known-deviations.json sha256 ${before.deviations} -> ${after.deviations}\n`)
process.exit(allOk ? 0 : 1)
