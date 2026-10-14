/**
 * QA-00 shared helpers for the Backend and AI contract validators.
 *
 * - Contract path: `--contract <path>` or SAWAKLI_CONTRACT_PATH (default: canonical.json here).
 * - Known deviations: `--deviations <path>` or SAWAKLI_DEVIATIONS_PATH
 *   (default: known-deviations.json here).
 * - Python source root: `--source-root <dir>` or SAWAKLI_SOURCE_ROOT (default: apps/backend/src/sawakli).
 * - Python models are read statically by extract_python_models.py (`python -I`, stdlib `ast`);
 *   the interpreter is `python` unless PYTHON is set.
 *
 * Everything fails closed: a missing file, class, enum, extractor error, unknown canonical type,
 * unlisted mismatch or stale deviation/declaration is a failure, never a pass.
 */

import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))
export const ROOT = resolve(__dirname, '../..')

function option(flag, envName, fallback) {
  const i = process.argv.indexOf(flag)
  if (i !== -1 && process.argv[i + 1]) return resolve(process.argv[i + 1])
  return process.env[envName] ? resolve(process.env[envName]) : fallback
}

export const CONTRACT_PATH = option('--contract', 'SAWAKLI_CONTRACT_PATH', resolve(__dirname, 'canonical.json'))
export const DEVIATIONS_PATH = option('--deviations', 'SAWAKLI_DEVIATIONS_PATH', resolve(__dirname, 'known-deviations.json'))
// Root the Python file paths are relative to; overridden only by the negative test's tampered copies.
export const BACKEND_SRC = option('--source-root', 'SAWAKLI_SOURCE_ROOT', resolve(ROOT, 'apps/backend/src/sawakli'))

export function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf-8'))
}

/** Run the static extractor over files relative to BACKEND_SRC; returns { relPath: {classes, aliases} }. */
export function extractPython(relFiles) {
  const abs = relFiles.map((f) => resolve(BACKEND_SRC, f))
  const run = spawnSync(process.env.PYTHON || 'python', ['-I', resolve(__dirname, 'extract_python_models.py'), ...abs], {
    encoding: 'utf-8',
  })
  if (run.error || run.status !== 0) {
    throw new Error(`Python extractor failed: ${run.error?.message || run.stderr.trim()}`)
  }
  const raw = JSON.parse(run.stdout)
  return Object.fromEntries(relFiles.map((f, i) => [f, raw[abs[i]]]))
}

/** `list[UUID] | None` -> { optional: true, base: 'list' }. Unions of several non-None types -> base 'union'. */
export function parseAnnotation(annotation) {
  let text = annotation.replace(/\s+/g, '')
  let optional = false
  const optMatch = text.match(/^(?:typing\.)?Optional\[(.*)\]$/)
  if (optMatch) {
    text = optMatch[1]
    optional = true
  }
  const parts = []
  let depth = 0
  let current = ''
  for (const ch of text) {
    if (ch === '[') depth++
    if (ch === ']') depth--
    if (ch === '|' && depth === 0) {
      parts.push(current)
      current = ''
    } else current += ch
  }
  parts.push(current)
  const types = parts.filter((p) => p !== 'None')
  if (types.length !== parts.length) optional = true
  const base = types.length === 1 ? types[0].split('[')[0].split('.').pop() : 'union'
  return { optional, base }
}

// Canonical scalar type -> accepted Python base types (enum-typed fields are handled separately).
export const TYPE_COMPAT = {
  uuid: ['UUID'],
  varchar: ['str'],
  text: ['str'],
  timestamp: ['datetime'],
  date: ['date'],
  numeric: ['Decimal', 'int', 'float'],
  integer: ['int'],
  jsonb: ['list', 'dict', 'tuple', 'Any'],
}

/** Find a StrEnum class or Literal alias by name across all extracted files; returns its values or null. */
function enumLikeValues(extracted, name) {
  for (const file of Object.values(extracted)) {
    if (file.classes[name]?.kind === 'enum') return file.classes[name].values
    if (file.aliases[name]) return file.aliases[name]
  }
  return null
}

function compareValues(issues, base, canonicalValues, pyValues, pyName) {
  for (const v of canonicalValues) {
    if (!pyValues.includes(v)) issues.push({ ...base, kind: 'enum_value_missing', value: v, detail: `canonical value '${v}' missing from ${pyName}` })
  }
  for (const v of pyValues) {
    if (!canonicalValues.includes(v)) issues.push({ ...base, kind: 'enum_value_extra', value: v, detail: `${pyName} has value '${v}' not in canonical` })
  }
}

/**
 * Compare one Python model with one canonical entity.
 * mapping: { validator, entity, model, file, renames: {pyField: canonicalField},
 *            omitted: {canonicalField: reason}, extras: {pyField: reason},
 *            optional: {pyField: reason} (model may be optional where the contract is NOT NULL) }
 * Every declaration must still match the model and contract, otherwise it is a stale_declaration.
 * Returns { issues, checkedFields, declarations }.
 */
export function checkModel(contract, extracted, mapping) {
  const { validator, entity, model, file, renames = {}, omitted = {}, extras = {}, optional = {} } = mapping
  const base = { validator, entity, model }
  const issues = []
  const declarations = []
  const canonical = contract.entities[entity]
  const cls = extracted[file]?.classes[model]

  if (!canonical) return { issues: [{ ...base, field: '*', kind: 'entity_not_in_contract', detail: `entity '${entity}' not in contract` }], checkedFields: 0, declarations }
  if (!cls || cls.kind === 'enum') return { issues: [{ ...base, field: '*', kind: 'model_not_found', detail: `class ${model} not found in ${file}` }], checkedFields: 0, declarations }

  for (const feature of cls.unsupported ?? []) {
    issues.push({ ...base, field: '*', kind: 'unsupported_model_feature', detail: `${model} uses ${feature}; the static check cannot see the resulting fields` })
  }

  const toCanonical = (pyField) => renames[pyField] ?? pyField
  const pyByCanonical = {}
  for (const pyField of Object.keys(cls.fields)) {
    const canonicalField = toCanonical(pyField)
    if (pyByCanonical[canonicalField]) {
      issues.push({ ...base, field: canonicalField, kind: 'duplicate_mapping', detail: `${model}.${pyByCanonical[canonicalField]} and ${model}.${pyField} both map to '${canonicalField}'` })
    }
    pyByCanonical[canonicalField] = pyField
  }
  let checkedFields = 0

  for (const [pyField, canonicalField] of Object.entries(renames)) {
    if (!cls.fields[pyField] || !canonical.fields[canonicalField]) {
      issues.push({ ...base, field: pyField, kind: 'stale_declaration', detail: `rename ${pyField} -> ${canonicalField} no longer matches the model/contract` })
    } else declarations.push(`rename ${model}.${pyField} -> ${entity}.${canonicalField}`)
  }
  for (const [field, reason] of Object.entries(omitted)) {
    if (!canonical.fields[field] || pyByCanonical[field]) {
      issues.push({ ...base, field, kind: 'stale_declaration', detail: `omission of '${field}' no longer matches (field absent from contract or now present in model)` })
    } else declarations.push(`omitted ${entity}.${field}: ${reason}`)
  }
  for (const [field, reason] of Object.entries(extras)) {
    if (!cls.fields[field] || canonical.fields[toCanonical(field)]) {
      issues.push({ ...base, field, kind: 'stale_declaration', detail: `extra field '${field}' no longer matches (absent from model or now canonical)` })
    } else declarations.push(`model-only ${model}.${field}: ${reason}`)
  }
  for (const [field, reason] of Object.entries(optional)) {
    const def = canonical.fields[toCanonical(field)]
    if (!cls.fields[field] || !def || def.nullable !== false || !parseAnnotation(cls.fields[field].annotation).optional) {
      issues.push({ ...base, field, kind: 'stale_declaration', detail: `optional declaration for '${field}' no longer matches (not optional in model or not NOT NULL in contract)` })
    } else declarations.push(`optional in model ${model}.${field}: ${reason}`)
  }

  for (const [field, def] of Object.entries(canonical.fields)) {
    const pyField = pyByCanonical[field]
    if (!pyField) {
      if (!(field in omitted)) issues.push({ ...base, field, kind: 'missing_field', detail: `canonical field '${field}' (${def.type}) missing from ${model}` })
      continue
    }
    checkedFields++
    const fb = { ...base, field }
    const ann = parseAnnotation(cls.fields[pyField].annotation)
    if (ann.optional && def.nullable === false && !(pyField in optional)) {
      issues.push({ ...fb, kind: 'nullable_in_model', detail: `${model}.${pyField} is optional (${cls.fields[pyField].annotation}) but canonical '${field}' is NOT NULL` })
    }
    const enumLike = enumLikeValues(extracted, ann.base)
    if (contract.enums[def.type]) {
      if (enumLike) compareValues(issues, fb, contract.enums[def.type], enumLike, ann.base)
      else if (ann.base === 'str') issues.push({ ...fb, kind: 'weak_enum_type', detail: `${model}.${pyField} is plain str; canonical type is ${def.type}` })
      else issues.push({ ...fb, kind: 'type_mismatch', detail: `${model}.${pyField} is ${ann.base}; canonical type is ${def.type}` })
    } else if (!TYPE_COMPAT[def.type]) {
      issues.push({ ...fb, kind: 'unknown_canonical_type', detail: `no compatibility rule for canonical type '${def.type}'` })
    } else {
      const ok = TYPE_COMPAT[def.type].includes(ann.base) || (enumLike && ['varchar', 'text'].includes(def.type))
      if (!ok) issues.push({ ...fb, kind: 'type_mismatch', detail: `${model}.${pyField} is ${cls.fields[pyField].annotation}; canonical type is ${def.type}` })
    }
  }

  for (const pyField of Object.keys(cls.fields)) {
    if (!canonical.fields[toCanonical(pyField)] && !(pyField in extras)) {
      issues.push({ ...base, field: pyField, kind: 'extra_field', detail: `${model}.${pyField} is not a canonical '${entity}' field` })
    }
  }
  return { issues, checkedFields, declarations }
}

/** Compare a Python StrEnum class or Literal alias with a canonical enum, both directions. */
export function checkEnum(contract, extracted, { validator, enumName, pyName }) {
  const base = { validator, entity: `enum:${enumName}`, model: pyName, field: '*' }
  if (!contract.enums[enumName]) return [{ ...base, kind: 'entity_not_in_contract', detail: `enum '${enumName}' not in contract` }]
  const values = enumLikeValues(extracted, pyName)
  if (!values) return [{ ...base, kind: 'model_not_found', detail: `enum/Literal ${pyName} not found` }]
  const issues = []
  compareValues(issues, base, contract.enums[enumName], values, pyName)
  return issues
}

// An entry's `mismatch` matches the issue's `kind`; the entry's own `kind` is its reviewed category.
export const DEVIATION_KINDS = ['breaking-mismatch', 'contract-stale', 'loose-typing']
const VALIDATORS = ['db', 'backend', 'ai']
const KEY_FIELDS = ['validator', 'entity', 'model', 'field', 'kind', 'value']
const sameKey = (entry, issue) => KEY_FIELDS.every((k) => ((k === 'kind' ? entry.mismatch : entry[k]) ?? null) === (issue[k] ?? null))

/** Every entry in the file must be well-formed, whichever validator it belongs to. */
function malformedEntries(all) {
  const failures = []
  all.forEach((entry, i) => {
    const problems = []
    if (!DEVIATION_KINDS.includes(entry.kind)) problems.push(`kind '${entry.kind ?? '(missing)'}' is not one of ${DEVIATION_KINDS.join(', ')}`)
    if (!VALIDATORS.includes(entry.validator)) problems.push(`validator '${entry.validator ?? '(missing)'}' is not one of ${VALIDATORS.join(', ')}`)
    for (const k of ['entity', 'model', 'field', 'mismatch', 'reason', 'task', 'owner']) {
      if (typeof entry[k] !== 'string' || !entry[k].trim()) problems.push(`'${k}' is missing or empty`)
    }
    const twin = all.findIndex((other) => other !== entry && KEY_FIELDS.every((k) => (other[k === 'kind' ? 'mismatch' : k] ?? null) === (entry[k === 'kind' ? 'mismatch' : k] ?? null)))
    if (twin !== -1) problems.push(`duplicates entry #${twin + 1} (same validator/entity/model/field/mismatch/value)`)
    for (const problem of problems) {
      failures.push({ validator: entry.validator, entity: entry.entity, model: entry.model, field: entry.field, kind: 'invalid_deviation_entry', detail: `known-deviations.json entry #${i + 1}: ${problem}` })
    }
  })
  return failures
}

/** Split issues into accepted (listed in known-deviations.json) and failures; unused entries are stale failures. */
export function applyDeviations(validator, issues) {
  const all = readJson(DEVIATIONS_PATH).deviations
  const failures = malformedEntries(all)
  const entries = all.filter((d) => d.validator === validator)
  const accepted = []
  for (const issue of issues) {
    const entry = entries.find((d) => sameKey(d, issue))
    if (entry) accepted.push({ issue, entry })
    else failures.push(issue)
  }
  for (const entry of entries) {
    if (!issues.some((i) => sameKey(entry, i))) {
      const key = [entry.validator, entry.entity, entry.model, entry.field, entry.mismatch, entry.value]
      failures.push({ ...entry, kind: 'stale_deviation', detail: `known deviation no longer matches anything: ${key.filter((v) => v != null).join(' / ')}` })
    }
  }
  return { accepted, failures }
}

/** "breaking-mismatch 1, contract-stale 3, loose-typing 4" for accepted [{entry}] items. */
export function kindCounts(accepted) {
  return DEVIATION_KINDS.map((k) => `${k} ${accepted.filter(({ entry }) => entry.kind === k).length}`).join(', ')
}

export function report(title, { checkedModels, checkedFields, checkedEnums, declarations, accepted, failures }) {
  const out = failures.length ? console.error : console.log
  out(`\n=== ${title} ${failures.length ? 'FAILED' : 'PASSED'} ===`)
  out(`  Contract: ${CONTRACT_PATH}`)
  out(`  Checked: ${checkedModels} model(s), ${checkedFields} field(s), ${checkedEnums} enum mapping(s)`)
  if (declarations.length) {
    out(`  Declared mappings (${declarations.length}):`)
    for (const d of declarations) out(`    - ${d}`)
  }
  if (accepted.length) {
    out(`  Accepted known deviations (${accepted.length}): ${kindCounts(accepted)}`)
    for (const { issue, entry } of accepted) out(`    ~ (${entry.kind}) ${issue.detail} [${entry.task}, ${entry.owner}] ${entry.reason}`)
  }
  if (failures.length) {
    out(`  Failures (${failures.length}):`)
    for (const f of failures) out(`    x [${f.kind}] ${f.entity} / ${f.model} / ${f.field}${f.value ? ` / ${f.value}` : ''}: ${f.detail}`)
  }
  out('')
  process.exit(failures.length ? 1 : 0)
}

/** Shared driver: run model + enum mappings, apply deviations, report and exit. */
export function runValidator(title, validator, files, models, enums) {
  try {
    const contract = readJson(CONTRACT_PATH)
    const extracted = extractPython(files)
    const issues = []
    const declarations = []
    let checkedFields = 0
    for (const m of models) {
      const r = checkModel(contract, extracted, { validator, ...m })
      issues.push(...r.issues)
      declarations.push(...r.declarations)
      checkedFields += r.checkedFields
    }
    for (const e of enums) issues.push(...checkEnum(contract, extracted, { validator, ...e }))
    const { accepted, failures } = applyDeviations(validator, issues)
    report(title, { checkedModels: models.length, checkedFields, checkedEnums: enums.length, declarations, accepted, failures })
  } catch (err) {
    console.error(`\n=== ${title} FAILED ===\n  Validator error: ${err.message}\n`)
    process.exit(1)
  }
}
