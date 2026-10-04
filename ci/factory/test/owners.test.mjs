import test from 'node:test';
import assert from 'node:assert/strict';
import { route, approvalsMet } from '../owners.mjs';

const teams = {
  teams: { 'team-orders': ['olga'], 'team-checkout': ['carl'], 'team-search': ['sam'], 'factory-owners': ['fay'] },
  catalog_approvers: { product: ['factory-owners'] },
};
const orders = (guardrails = {}) => ({
  name: 'orders', root: 'product/services/orders', boundary: 'product',
  base: { service: { owner: 'team-orders', contract: ['api/openapi.yaml'] }, guardrails: { contributors: ['team-checkout'], protected_paths: ['migrations/**'], ...guardrails } },
  head: { service: { owner: 'team-orders' } },
});

test('a listed contributor approves an internal change', () => {
  const r = route({ services: [orders()], files: ['product/services/orders/main.go'], author: 'carl', tier: 'R1', teams });
  assert.deepEqual(r.approvals[0].teams, ['team-checkout']);
  assert.equal(r.approvals[0].notify, 'team-orders');
});

test('an unlisted contributor needs the owner', () => {
  const r = route({ services: [orders()], files: ['product/services/orders/main.go'], author: 'sam', tier: 'R1', teams });
  assert.deepEqual(r.approvals[0].teams, ['team-orders']);
});

test('contract, protected paths and R2 need the owner', () => {
  for (const [file, tier] of [['api/openapi.yaml', 'R2'], ['migrations/1.sql', 'R1'], ['main.go', 'R2'], ['guardrails.yaml', 'R1']]) {
    const r = route({ services: [orders()], files: [`product/services/orders/${file}`], author: 'carl', tier, teams });
    assert.deepEqual(r.approvals[0].teams, ['team-orders'], file);
  }
});

test('protected paths raise the tier', () => {
  const r = route({ services: [orders()], files: ['product/services/orders/migrations/1.sql'], author: 'carl', tier: 'R1', teams });
  assert.deepEqual(r.raise, ['protected_path']);
});

test('a new service needs a catalog approver and its owner', () => {
  const s = { name: 'billing', root: 'product/services/billing', boundary: 'product', base: null, head: { service: { owner: 'team-billing' } } };
  const r = route({ services: [s], files: ['product/services/billing/service.yaml'], author: 'carl', tier: 'R1', teams });
  assert.deepEqual(r.approvals.map((a) => a.teams[0]), ['factory-owners', 'team-billing']);
});

test('an owner change needs both owners', () => {
  const s = { ...orders(), head: { service: { owner: 'team-checkout' } } };
  const r = route({ services: [s], files: ['product/services/orders/service.yaml'], author: 'carl', tier: 'R1', teams });
  assert.deepEqual(r.approvals.map((a) => a.teams[0]), ['team-orders', 'team-checkout']);
});

test('more than three owning teams raises the tier', () => {
  const svc = (n) => ({ ...orders(), name: n, root: `product/services/${n}`, base: { service: { owner: `team-${n}` }, guardrails: {} } });
  const services = ['a', 'b', 'c', 'd'].map(svc);
  const r = route({ services, files: services.map((s) => `${s.root}/x.go`), author: 'carl', tier: 'R1', teams });
  assert.ok(r.raise.includes('owning_teams_over_3'));
});

test('approvals: author and requester never count', () => {
  const approvals = [{ service: 'orders', teams: ['team-orders'] }];
  assert.equal(approvalsMet(approvals, ['olga'], { author: 'carl', teams }).ok, true);
  assert.equal(approvalsMet(approvals, ['olga'], { author: 'olga', teams }).ok, false);
  assert.equal(approvalsMet(approvals, ['olga'], { author: 'bot', requester: 'olga', teams }).ok, false);
});
