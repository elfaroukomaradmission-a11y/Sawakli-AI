/**
 * QA-01 Deliberate Mismatch Test (rewritten by QA-00)
 *
 * Proves every contract validator fails visibly on an injected mismatch instead of passing:
 * one case per validator (DB, UI, Backend, AI) on the contract, Python-side cases on copied
 * Backend/AI source, and allowlist cases (stale entry, unknown kind).
 * Tampering happens only on copies in the OS temp directory, passed via --contract / --deviations /
 * --source-root;
 * the real canonical.json and known-deviations.json are hashed before and after and must be
 * byte-identical.
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
const sha256 = (path) => createHash('sha256').update(readFileSync(path)).digest('hex')

const CASES = [
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
  {
    name: 'AI validator (Python side): field type changed',
    validator: 'validate-ai-schemas.mjs',
    source: { 'ai/forecasting/schemas.py': (t) => t.replace(/(class ForecastRecord[\s\S]*?metric_name: )str/, '$1int') },
    expect: ['type_mismatch', 'metric_name'],
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
    name: 'Known deviations: stale entry must fail',
    validator: 'validate-ai-schemas.mjs',
    deviations: (d) => {
      d.deviations.push({
        validator: 'ai', entity: 'forecasts', model: 'ForecastRecord', field: 'ghost_field', kind: 'missing_field',
        reason: 'deliberately stale', task: 'QA-00', owner: 'QA-00 negative test',
      })
    },
    expect: ['stale_deviation', 'ghost_field'],
  },
  {
    name: 'Known deviations: unknown kind must fail',
    validator: 'validate-db-schema.mjs',
    deviations: (d) => {
      d.deviations[0].kind = 'not-a-real-kind'
    },
    expect: ['invalid_deviation_entry', 'not-a-real-kind'],
  },
]

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
      cpSync(SOURCE, sourceRoot, { recursive: true, filter: (src) => !src.includes('__pycache__') })
      for (const [file, tamper] of Object.entries(testCase.source)) {
        const path = join(sourceRoot, file)
        const before = readFileSync(path, 'utf-8')
        const after = tamper(before)
        if (after === before) throw new Error(`case '${testCase.name}': tamper did not change ${file}`)
        writeFileSync(path, after)
      }
      args.push('--source-root', sourceRoot)
    }

    const run = spawnSync(process.execPath, [resolve(__dirname, testCase.validator), ...args], { encoding: 'utf-8' })
    const output = `${run.stdout}${run.stderr}`
    const missed = testCase.expect.filter((needle) => !output.includes(needle))
    const ok = run.status === 1 && missed.length === 0
    results.push({ ok, name: testCase.name, detail: ok ? `exit 1, named ${testCase.expect.join(', ')}` : `exit ${run.status}, not named: ${missed.join(', ') || '-'}`, output })
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
