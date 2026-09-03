/**
 * QA-01 Deliberate Mismatch Test
 *
 * Creates a temporary copy of canonical.json with one wrong field injected,
 * runs the UI validator against it, and asserts that the validator FAILS.
 * This proves the validation suite is not blindly passing.
 *
 * Usage: node tests/contracts/test-deliberate-mismatch.mjs
 * Exit 0 = validator correctly caught the mismatch.
 * Exit 1 = validator failed to catch it (the suite is broken).
 */

import { readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'

const __dirname = dirname(fileURLToPath(import.meta.url))

const canonicalPath = resolve(__dirname, 'canonical.json')
const tampered = JSON.parse(readFileSync(canonicalPath, 'utf-8'))

// Inject a field that does NOT exist in the UI type
tampered.entities.anomalies.fields.fake_nonexistent_field = {
  type: 'varchar',
  nullable: false,
}

// Also inject a wrong enum value
tampered.enums.platform_enum.push('tiktok')

const tamperedPath = resolve(__dirname, '_tampered_canonical.json')
writeFileSync(tamperedPath, JSON.stringify(tampered, null, 2))

// Run the UI validator with the tampered contract
// We need to temporarily swap the canonical file
const originalContent = readFileSync(canonicalPath, 'utf-8')

try {
  writeFileSync(canonicalPath, JSON.stringify(tampered, null, 2))

  let validatorOutput = ''
  let exitCode = 0
  try {
    validatorOutput = execSync(
      `node "${resolve(__dirname, 'validate-ui-types.mjs')}"`,
      { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }
    )
    exitCode = 0
  } catch (err) {
    validatorOutput = (err.stdout || '') + (err.stderr || '')
    exitCode = err.status ?? 1
  }

  // Restore original
  writeFileSync(canonicalPath, originalContent)
  unlinkSync(tamperedPath)

  if (exitCode !== 0) {
    const caughtFakeField = validatorOutput.includes('fake_nonexistent_field')
    const caughtFakeEnum = validatorOutput.includes('tiktok')

    if (caughtFakeField && caughtFakeEnum) {
      console.log('\n=== QA-01 Deliberate Mismatch Test PASSED ===')
      console.log('  The validator correctly caught:')
      console.log('    - Missing field: fake_nonexistent_field')
      console.log('    - Missing enum value: tiktok')
      console.log('  The contract validation suite is working.\n')
      process.exit(0)
    } else {
      console.error('\n=== QA-01 Deliberate Mismatch Test PARTIAL ===')
      console.error('  Validator failed but did not catch all injected errors.')
      console.error(`  Caught fake_nonexistent_field: ${caughtFakeField}`)
      console.error(`  Caught tiktok enum: ${caughtFakeEnum}`)
      console.error(`\n  Validator output:\n${validatorOutput}`)
      process.exit(1)
    }
  } else {
    console.error('\n=== QA-01 Deliberate Mismatch Test FAILED ===')
    console.error('  The validator passed when it should have failed!')
    console.error('  Injected errors: fake_nonexistent_field, tiktok enum')
    console.error('  The contract validation suite is NOT catching mismatches.\n')
    process.exit(1)
  }
} catch (err) {
  // Always restore original on any error
  writeFileSync(canonicalPath, originalContent)
  try { unlinkSync(tamperedPath) } catch { /* ignore */ }
  console.error('Unexpected error:', err.message)
  process.exit(1)
}
