import test from 'node:test';
import assert from 'node:assert/strict';
import { decide } from '../admission.mjs';

const sha = 'a'.repeat(40);
const required = [
  { name: 'boundary', mode: 'enforce' },
  { name: 'unit-tests', mode: 'enforce' },
  { name: 'diff-coverage', mode: 'shadow' },
];
const pass = (check, s = sha) => ({ check, status: 'pass', sha: s });

test('allows when all enforced evidence passes', () => {
  const r = decide({ sha, tier: 'R1', required, records: [pass('boundary'), pass('unit-tests')] });
  assert.equal(r.allowed, true);
  assert.match(r.summary, /allowed/);
});

test('blocks on missing enforced evidence', () => {
  const r = decide({ sha, tier: 'R1', required, records: [pass('boundary')] });
  assert.equal(r.allowed, false);
  assert.deepEqual(r.blocking, ['unit-tests (missing)']);
});

test('blocks on failed evidence', () => {
  const r = decide({ sha, tier: 'R1', required, records: [pass('boundary'), { check: 'unit-tests', status: 'fail', sha }] });
  assert.equal(r.allowed, false);
});

test('evidence for another commit does not count', () => {
  const r = decide({ sha, tier: 'R1', required, records: [pass('boundary'), pass('unit-tests', 'b'.repeat(40))] });
  assert.equal(r.allowed, false);
  assert.match(r.blocking[0], /another commit/);
});

test('shadow evidence never blocks', () => {
  const r = decide({ sha, tier: 'R1', required, records: [pass('boundary'), pass('unit-tests'), { check: 'diff-coverage', status: 'fail', sha }] });
  assert.equal(r.allowed, true);
});

test('nothing affected counts as passing', () => {
  const r = decide({ sha, tier: 'R1', required, records: [pass('boundary'), { check: 'unit-tests', status: 'skipped', sha, details: 'nothing affected' }] });
  assert.equal(r.allowed, true);
});

test('agent above its trust needs a human approval', () => {
  const records = [pass('boundary'), pass('unit-tests')];
  assert.equal(decide({ sha, tier: 'R1', required, records, needsHuman: true }).allowed, false);
  assert.equal(decide({ sha, tier: 'R1', required, records: [...records, pass('human-approval')], needsHuman: true }).allowed, true);
});

test('override is shown in the summary', () => {
  const r = decide({ sha, tier: 'R3', required, records: [pass('boundary'), pass('unit-tests')], override: true });
  assert.match(r.summary, /Boundary override/);
});
