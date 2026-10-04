import test from 'node:test';
import assert from 'node:assert/strict';
import { agentGuardrails, ownerChecks } from '../guardrails.mjs';

const svc = { name: 'orders', root: 'product/services/orders', base: { guardrails: {
  required_checks: [{ target: 'simulate', when: ['src/**'] }, { target: 'perf', when: ['src/pricing/**'], budget: '5m' }],
  agents: { max_autonomous_tier: 'R0', forbidden_paths: ['src/payments/**'] },
} } };

test('owner checks run when their paths change', () => {
  assert.deepEqual(ownerChecks([svc], ['product/services/orders/src/a.go']), [{ project: 'orders', target: 'simulate', budget: null }]);
  assert.equal(ownerChecks([svc], ['product/services/orders/src/pricing/p.go']).length, 2);
  assert.deepEqual(ownerChecks([svc], ['product/services/orders/README.md']), []);
});

test('agent guardrails: forbidden paths and max tier', () => {
  assert.equal(agentGuardrails([svc], ['product/services/orders/src/payments/x.go'], 'R0').ok, false);
  assert.equal(agentGuardrails([svc], ['product/services/orders/src/a.go'], 'R1').needsHuman, true);
  assert.deepEqual(agentGuardrails([svc], ['product/services/orders/src/a.go'], 'R0'), { ok: true, problems: [], needsHuman: false });
});
