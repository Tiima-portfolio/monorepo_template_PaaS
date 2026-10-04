import test from 'node:test';
import assert from 'node:assert/strict';
import { classify, fileTier, testOnly } from '../risk.mjs';
import { requiredEvidence } from '../evidence.mjs';
import { loadPolicy } from '../lib/policy.mjs';

const risk = loadPolicy('risk');

test('file tiers', () => {
  assert.equal(fileTier('docs/x.md', risk), 'R0');
  assert.equal(fileTier('product/services/a/README.md', risk), 'R0');
  assert.equal(fileTier('product/services/a/main.go', risk), 'R1');
  assert.equal(fileTier('product/services/a/api/openapi.yaml', risk), 'R2');
  assert.equal(fileTier('product/libraries/money/x.ts', risk), 'R2');
  assert.equal(fileTier('ci/policy/risk.yaml', risk), 'R3');
  assert.equal(fileTier('product/services/a/migrations/001.sql', risk), 'R3');
});

test('docs only is R0', () => {
  assert.equal(classify({ files: ['docs/a.md', 'README.md'] }).tier, 'R0');
});

test('test-only change is R1, never R0', () => {
  const files = ['product/services/a/src/x.test.ts'];
  assert.ok(testOnly(files));
  assert.equal(classify({ files }).tier, 'R1');
});

test('highest file wins', () => {
  assert.equal(classify({ files: ['docs/a.md', 'product/services/a/main.go', 'product/services/a/api/v1.proto'] }).tier, 'R2');
});

test('wide blast radius and critical projects reach R2', () => {
  assert.equal(classify({ files: ['product/services/a/x.go'], affectedProjects: 11 }).tier, 'R2');
  assert.equal(classify({ files: ['product/services/a/x.go'], affectedProjects: 10 }).tier, 'R1');
  assert.equal(classify({ files: ['product/services/a/x.go'], criticalities: ['critical'] }).tier, 'R2');
});

test('override and major bump are R3', () => {
  assert.equal(classify({ files: ['docs/a.md'], override: true }).tier, 'R3');
  assert.equal(classify({ files: ['product/services/a/x.go'], majorBump: true }).tier, 'R3');
});

test('raisers add one tier each, capped at R3', () => {
  assert.equal(classify({ files: ['docs/a.md'], raise: ['protected_path'] }).tier, 'R1');
  assert.equal(classify({ files: ['product/a/x.go'], raise: ['weak_test_history', 'agent_above_trust'] }).tier, 'R3');
  assert.equal(classify({ files: ['ci/x'], raise: ['protected_path'] }).tier, 'R3');
  assert.throws(() => classify({ files: [], raise: ['nope'] }));
});

test('reasons explain the tier', () => {
  const r = classify({ files: ['ci/x.mjs'] });
  assert.match(r.reasons.join(' '), /ci\/x.mjs is R3/);
});

test('evidence accumulates by tier', () => {
  const r0 = requiredEvidence('R0').map((e) => e.name);
  const r1 = requiredEvidence('R1').map((e) => e.name);
  const r3 = requiredEvidence('R3').map((e) => e.name);
  assert.ok(r0.includes('format-lint') && !r0.includes('unit-tests'));
  assert.ok(r1.includes('unit-tests'));
  assert.ok(r0.every((n) => r1.includes(n)));
  assert.ok(r3.includes('owner-approval'));
});

test('extra evidence for agents and removed tests', () => {
  assert.ok(requiredEvidence('R1', { agent: true }).some((e) => e.name === 'provenance'));
  assert.ok(requiredEvidence('R1', { testsRemoved: true }).some((e) => e.name === 'owner-approval'));
});

test('every evidence has a mode', () => {
  for (const tier of ['R0', 'R1', 'R2', 'R3']) {
    for (const e of requiredEvidence(tier, { agent: true, testsRemoved: true })) {
      assert.ok(['enforce', 'shadow'].includes(e.mode), e.name);
    }
  }
});

test('escape fixes need a regression test', () => {
  assert.ok(requiredEvidence('R1', { escapeFix: true }).some((e) => e.name === 'regression-test' && e.mode === 'enforce'));
  assert.ok(!requiredEvidence('R1').some((e) => e.name === 'regression-test'));
});

test('owner checks are required when triggered', () => {
  assert.ok(requiredEvidence('R1', { ownerChecks: true }).some((e) => e.name === 'owner-checks' && e.mode === 'enforce'));
});
