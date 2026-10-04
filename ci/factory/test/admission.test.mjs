import test from 'node:test';
import assert from 'node:assert/strict';
import { decide, jobProblems } from '../admission.mjs';

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

const okJobs = [{ name: 'factory/gate', conclusion: 'success' }, { name: 'factory/verify', conclusion: 'success' }];

test('job results from GitHub must agree', () => {
  const records = [pass('boundary'), pass('unit-tests')];
  assert.equal(decide({ sha, tier: 'R1', required, records, affected: ['a'], jobs: okJobs }).allowed, true);
  const failedGate = [{ name: 'factory/gate', conclusion: 'failure' }, okJobs[1]];
  assert.equal(decide({ sha, tier: 'R1', required, records, affected: ['a'], jobs: failedGate }).allowed, false);
});

test('a skipped verify job is fine only when nothing is affected', () => {
  const jobs = [okJobs[0], { name: 'factory/verify', conclusion: 'skipped' }];
  assert.deepEqual(jobProblems({ sha, affected: [], jobs }), []);
  assert.deepEqual(jobProblems({ sha, affected: ['a'], jobs }), ['factory/verify job skipped']);
});

test('evidence must come from the factory workflow for this commit', () => {
  assert.match(jobProblems({ sha, affected: [], jobs: okJobs, run: { path: '.github/workflows/other.yml', head_sha: sha } })[0], /not the factory workflow/);
  assert.match(jobProblems({ sha, affected: [], jobs: okJobs, run: { path: '.github/workflows/factory.yml', head_sha: 'b'.repeat(40) } })[0], /another commit/);
});
