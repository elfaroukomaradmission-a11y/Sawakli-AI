/** ARCH-03 illustrative fixtures: canonical shapes, cross-layer links and negative cases. */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const canonical = JSON.parse(readFileSync(resolve(ROOT, 'tests/contracts/canonical.json'), 'utf8'))
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const decimal = /^-?\d+(?:\.\d+)?$/
const scenarios = canonical.enums.simulation_scenario_enum
const tables = ['forecasts', 'anomalies', 'recommendations', 'action_simulations']
const allowedStatuses = ['SUCCESS', 'FAILED', 'CANCELLED']

function numeric(value) {
  return (typeof value === 'number' || (typeof value === 'string' && decimal.test(value))) &&
    Number.isFinite(Number(value))
}

function validateRow(table, row) {
  const fields = canonical.entities[table].fields
  assert(Object.keys(row).every(key => key in fields), `${table}: unknown column`)
  for (const [key, field] of Object.entries(fields)) {
    const value = row[key]
    if (value === undefined || value === null) {
      assert(field.nullable, `${table}.${key}: missing/null required value`)
      continue
    }
    const type = field.type
    if (canonical.enums[type]) assert(canonical.enums[type].includes(value), `${table}.${key}: enum`)
    else if (type === 'uuid') assert(typeof value === 'string' && uuid.test(value), `${table}.${key}: UUID`)
    else if (type === 'numeric' || type === 'integer') {
      assert(numeric(value), `${table}.${key}: finite number`)
      if (type === 'integer') assert(Number.isInteger(value), `${table}.${key}: integer`)
      if (field.constraints?.min !== undefined) assert(Number(value) >= field.constraints.min)
      if (field.constraints?.max !== undefined) assert(Number(value) <= field.constraints.max)
    } else if (type === 'date') {
      assert(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) &&
        Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value)
    } else if (type === 'timestamp') {
      assert(typeof value === 'string' && Number.isFinite(Date.parse(value)), `${table}.${key}: timestamp`)
    } else if (type === 'varchar' || type === 'text') assert(typeof value === 'string')
    else if (type === 'jsonb') assert(typeof value === 'object', `${table}.${key}: JSON`)
    else assert.fail(`unhandled canonical type: ${type}`)
  }
}

function validate(manifest) {
  assert.equal(manifest.contract_version, 'ai-pipeline-v1')
  assert(Array.isArray(manifest.cases) && manifest.cases.length >= 6)
  assert.equal(new Set(manifest.cases.map(c => c.name)).size, manifest.cases.length)
  const allIds = new Set()
  for (const example of manifest.cases) {
    const req = example.request, out = example.outcome, rows = example.persisted_rows
    assert.equal(req.contract_version, manifest.contract_version)
    for (const field of ['organization_id', 'job_id', 'model_run_id']) {
      assert(uuid.test(req[field]))
      assert.equal(out[field], req[field], `${example.name}: outcome identity mismatch`)
    }
    assert(/^\d{4}-\d{2}-\d{2}$/.test(req.as_of) && Number.isFinite(Date.parse(req.as_of)))
    assert(req.campaign_ids === null || (Array.isArray(req.campaign_ids) && req.campaign_ids.length &&
      req.campaign_ids.every(c => uuid.test(c)) && new Set(req.campaign_ids).size === req.campaign_ids.length))
    assert(allowedStatuses.includes(out.status))
    assert.equal(new Set(out.campaigns_analyzed).size, out.campaigns_analyzed.length)
    assert(out.campaigns_analyzed.every(c => uuid.test(c) &&
      (req.campaign_ids === null || req.campaign_ids.includes(c))))
    if (out.status === 'SUCCESS') assert(out.error_code === null && out.retryable === false)
    else {
      assert.equal(out.campaigns_analyzed.length, 0)
      if (out.status === 'CANCELLED') assert(out.error_code === 'cancelled' && !out.retryable)
      else assert(['invalid_input', 'computation_failed', 'storage_failed'].includes(out.error_code))
    }
    for (const table of tables) {
      assert(Array.isArray(rows[table]))
      for (const row of rows[table]) {
        validateRow(table, row)
        assert(!allIds.has(row.id), 'duplicate example row UUID')
        allIds.add(row.id)
        if (table !== 'action_simulations') {
          assert.equal(row.organization_id, req.organization_id, 'cross-tenant row')
          assert.equal(row.model_run_id, req.model_run_id, 'cross-run row')
          assert(req.campaign_ids === null || req.campaign_ids.includes(row.campaign_id))
          assert(out.campaigns_analyzed.includes(row.campaign_id))
        }
      }
    }
    if (out.status !== 'SUCCESS') assert(tables.every(table => rows[table].length === 0))
    const anomalies = new Map(rows.anomalies.map(row => [row.id, row]))
    const recommendations = new Map(rows.recommendations.map(row => [row.id, row]))
    for (const row of rows.recommendations) {
      if (row.source_anomaly_id !== null) {
        const parent = anomalies.get(row.source_anomaly_id)
        assert(parent && parent.campaign_id === row.campaign_id && parent.model_run_id === row.model_run_id)
      }
      assert(Array.isArray(row.evidence))
    }
    for (const row of rows.action_simulations) assert(recommendations.has(row.recommendation_id), 'orphan simulation')
    for (const row of rows.recommendations) {
      const sims = rows.action_simulations.filter(s => s.recommendation_id === row.id)
      assert.equal(sims.length, 3)
      assert.deepEqual([...new Set(sims.map(s => s.scenario_type))].sort(), [...scenarios].sort())
    }
    if (example.metric_evidence) {
      const m = example.metric_evidence
      assert.equal(m.organization_id, req.organization_id)
      assert(req.campaign_ids === null || req.campaign_ids.includes(m.campaign_id))
      assert(m.observed_on <= req.as_of && m.historical_count >= 5)
      assert(['spend', 'ctr', 'cpc', 'cpa', 'roas'].includes(m.metric_name))
      for (const key of ['current_value', 'baseline_median', 'z_contribution', 'iqr_contribution']) {
        assert(numeric(m[key]) && Number(m[key]) >= 0)
      }
      assert(Number(m.z_contribution) <= 1 && Number(m.iqr_contribution) <= 1)
      assert(Number(m.z_contribution) + Number(m.iqr_contribution) > 0)
      for (const row of rows.anomalies) {
        assert.equal(row.metric_name, m.metric_name)
        assert.equal(row.campaign_id, m.campaign_id)
        assert.equal(row.severity, 'high')
        assert(Number(row.anomaly_score) >= .8)
        assert.equal(row.direction, Number(m.current_value) > Number(m.baseline_median) ? 'above' : 'below')
        assert.notEqual(Number(m.current_value), Number(m.baseline_median))
        assert.equal(row.detected_at.slice(0, 10), m.observed_on)
        assert.equal(row.detectors_triggered.score_scope, 'campaign_day')
      }
    }
    if (example.simulation_batch) {
      const b = example.simulation_batch
      assert.equal(b.organization_id, req.organization_id)
      assert.equal(b.horizon_days, 7)
      assert(b.rule_id && b.assumptions.length && b.assumptions.every(a => typeof a === 'string' && a.trim()))
      assert.equal(b.projections.length, 3)
      const rec = rows.recommendations.find(r => r.campaign_id === b.campaign_id && r.evidence.includes(`rule_id:${b.rule_id}`))
      assert(rec)
      for (const p of b.projections) {
        const stored = rows.action_simulations.find(s => s.recommendation_id === rec.id && s.scenario_type === p.scenario_type)
        assert(stored)
        for (const key of ['projected_spend', 'projected_conversions', 'projected_cpa', 'projected_roas']) assert.equal(p[key], stored[key])
        assert.equal(p.undefined_ratios.includes('cpa'), Number(p.projected_conversions) === 0)
        assert.equal(p.undefined_ratios.includes('roas'), Number(p.projected_spend) === 0)
        for (const metric of p.undefined_ratios) assert.equal(Number(p[`projected_${metric}`]), 0)
        if (p.scenario_type === 'pause') {
          assert.equal(Number(p.projected_spend), 0)
          assert.equal(Number(p.projected_conversions), 0)
          assert(rec.evidence.includes('undefined_ratios:pause:cpa,roas'))
        }
      }
    }
  }
  const e = manifest.evaluation
  assert.equal(e.benchmark, 'ai02-reference-v1')
  assert.equal(e.threshold, '0.80')
  assert.deepEqual(e.seeds, [20261015, 20261016])
  assert.equal(e.rows_per_seed, e.anomaly_days_per_seed + e.clean_days_per_seed)
  assert.equal(e.rows_per_seed, 5400)
  assert.equal(e.events_per_seed, 30)
  assert.equal(e.clean_campaigns_per_seed, 30)
  assert.equal(e.development_digest, '4533a170f07e361b9e9fc77528aa56822fb07fae58a00e1aa1cd7828ee00ad62')
  assert.equal(e.validation_digest, '414d813add890129a32d26af6ffe5ee444288eed261cc985de88dbd55ca66aee')
}

try {
  const args = process.argv.slice(2)
  assert(args.length === 0 || (args.length === 2 && args[0] === '--fixture'), 'usage: --fixture PATH')
  const manifest = JSON.parse(readFileSync(args[1] ?? resolve(ROOT, 'tests/contracts/ai-pipeline-v1.json'), 'utf8'))
  validate(manifest)
  const mutations = [
    ['tenant leak', m => { m.cases[0].persisted_rows.forecasts[0].organization_id = '00000000-0000-0000-0000-000000000002' }],
    ['cross-run row', m => { m.cases[0].persisted_rows.anomalies[0].model_run_id = '00000000-0000-0000-0000-000000000999' }],
    ['orphan FK', m => { m.cases[0].persisted_rows.action_simulations[0].recommendation_id = '00000000-0000-0000-0000-000000000999' }],
    ['missing scenario', m => { m.cases[0].persisted_rows.action_simulations.pop() }],
    ['nullable forecast', m => { m.cases[0].persisted_rows.forecasts[0].value = null }],
    ['invalid severity', m => { m.cases[0].persisted_rows.anomalies[0].severity = 'critical' }],
    ['foreign outcome', m => { m.cases[0].outcome.job_id = '00000000-0000-0000-0000-000000000999' }],
    ['cancelled publication', m => { m.cases[0].outcome.status = 'CANCELLED'; m.cases[0].outcome.error_code = 'cancelled'; m.cases[0].outcome.campaigns_analyzed = [] }],
    ['unavailable ratio marker', m => { m.cases[0].simulation_batch.projections[2].undefined_ratios = [] }],
  ]
  for (const [name, mutate] of mutations) {
    const broken = structuredClone(manifest)
    mutate(broken)
    assert.throws(() => validate(broken), `failed to reject ${name}`)
  }
  console.log(`PASS ARCH-03: ${manifest.cases.length} fixture cases; canonical rows and links; ${mutations.length} injected failures rejected`)
} catch (error) {
  console.error(`FAIL ARCH-03: ${error.message}`)
  process.exitCode = 1
}
