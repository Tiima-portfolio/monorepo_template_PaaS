import test from 'node:test';
import assert from 'node:assert/strict';
import { boundaryOf, checkBoundary } from '../boundary.mjs';
import { loadPolicy } from '../lib/policy.mjs';
import { matches } from '../lib/glob.mjs';

const policy = loadPolicy('boundaries');

test('glob: ** and *', () => {
  assert.ok(matches('product/services/a/x.go', 'product/**'));
  assert.ok(matches('internal-tools/lint/a/b.py', 'internal-tools/*/**'));
  assert.ok(!matches('internal-tools/README.md', 'internal-tools/*/**'));
  assert.ok(matches('README.md', 'README.md'));
  assert.ok(!matches('docs/README.md', 'README.md'));
});

test('each path maps to its boundary', () => {
  assert.equal(boundaryOf('product/services/orders/main.go', policy), 'product');
  assert.equal(boundaryOf('internal-tools/toolchains/go/toolchain.yaml', policy), 'internal-tool:internal-tools/toolchains');
  assert.equal(boundaryOf('internal-services/sim/app.py', policy), 'internal-service:internal-services/sim');
  assert.equal(boundaryOf('.github/workflows/pr.yml', policy), 'ci');
  assert.equal(boundaryOf('ci/policy/risk.yaml', policy), 'ci');
  assert.equal(boundaryOf('nx.json', policy), 'workspace');
  assert.equal(boundaryOf('docs/plan.md', policy), 'docs');
  assert.equal(boundaryOf('README.md', policy), 'docs');
  assert.equal(boundaryOf('platform/runners/values.yaml', policy), 'platform');
  assert.equal(boundaryOf('test-framework/contracts/x.ts', policy), 'test-framework');
});

test('one boundary passes, even across product services', () => {
  const r = checkBoundary(['product/services/a/x.ts', 'product/libraries/b/y.ts'], policy);
  assert.equal(r.ok, true);
  assert.equal(r.boundary, 'product');
});

test('two tools are two boundaries', () => {
  const r = checkBoundary(['internal-tools/a/x', 'internal-tools/b/y'], policy);
  assert.equal(r.ok, false);
  assert.match(r.message, /Split it/);
});

test('ci plus product fails with split advice', () => {
  const r = checkBoundary(['ci/policy/risk.yaml', 'product/services/a/x.ts'], policy);
  assert.equal(r.ok, false);
  assert.deepEqual(r.boundaries, ['ci', 'product']);
});

test('override allows a cross-boundary PR and flags it', () => {
  const r = checkBoundary(['ci/x', 'product/y'], policy, { override: true });
  assert.equal(r.ok, true);
  assert.equal(r.override, true);
});

test('unowned paths fail', () => {
  const r = checkBoundary(['random.txt'], policy);
  assert.equal(r.ok, false);
  assert.deepEqual(r.unowned, ['random.txt']);
});

test('empty change passes', () => {
  assert.equal(checkBoundary([], policy).ok, true);
});
