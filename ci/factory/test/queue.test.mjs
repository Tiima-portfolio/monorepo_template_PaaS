import test from 'node:test';
import assert from 'node:assert/strict';
import { selectToEnqueue } from '../queue.mjs';
import { loadPolicy } from '../lib/policy.mjs';

const policy = loadPolicy('queue');
let n = 0;
const pr = (over = {}) => ({ number: ++n, author: 'sami', labels: ['ready'], files: ['product/a/x.go'], readyAt: `2026-10-04T10:${String(n).padStart(2, '0')}:00Z`, admitted: true, inQueue: false, ...over });

test('only ready, admitted PRs outside the queue are picked', () => {
  const r = selectToEnqueue({ candidates: [pr(), pr({ labels: [] }), pr({ admitted: false }), pr({ inQueue: true })], queue: [], policy });
  assert.equal(r.picks.length, 1);
});

test('priority first, then age; P0 jumps', () => {
  const a = pr({ labels: ['ready', 'P3'] });
  const b = pr({ labels: ['ready', 'P0'] });
  const c = pr();
  const r = selectToEnqueue({ candidates: [a, b, c], queue: [], policy });
  assert.deepEqual(r.picks.map((p) => [p.number, p.jump]), [[b.number, true], [c.number, false], [a.number, false]]);
});

test('agents default to P3 and have a queue limit', () => {
  const agent = 'example-docs-agent[bot]';
  const r = selectToEnqueue({ candidates: [pr({ author: agent }), pr({ author: agent })], queue: [], policy, agentAccounts: [agent], agentLimits: { [agent]: 1 } });
  assert.equal(r.picks.length, 1);
  assert.equal(r.picks[0].priority, 'P3');
  assert.match(r.waiting[0].reason, /entries queued/);
});

test('backpressure holds P4 then P3, never P0 to P2', () => {
  const queue = Array.from({ length: 15 }, (_, i) => ({ number: 900 + i }));
  const r = selectToEnqueue({ candidates: [pr({ labels: ['ready', 'P4'] }), pr({ labels: ['ready', 'P3'] }), pr({ labels: ['ready', 'P2'] })], queue, policy });
  assert.deepEqual(r.picks.map((p) => p.priority), ['P2']);
  assert.equal(r.waiting.length, 2);
});

test('a rule change enters only an empty queue, alone', () => {
  const rule = pr({ files: ['ci/policy/risk.yaml'] });
  const other = pr();
  assert.deepEqual(selectToEnqueue({ candidates: [rule, other], queue: [{ number: 1 }], policy }).picks.map((p) => p.number), [other.number]);
  const r = selectToEnqueue({ candidates: [rule, other], queue: [], policy });
  assert.deepEqual(r.picks.map((p) => p.number), [rule.number]);
  assert.match(r.waiting[0].reason, /merging alone/);
  const held = selectToEnqueue({ candidates: [other], queue: [{ number: rule.number, ruleChange: true }], policy });
  assert.equal(held.picks.length, 0);
});

test('workspace changes wait for the off-peak window, except P0', () => {
  const ws = pr({ files: ['package.json'] });
  const day = new Date('2026-10-04T12:00:00Z');
  const night = new Date('2026-10-04T22:00:00Z');
  assert.match(selectToEnqueue({ candidates: [ws], queue: [], policy, now: day }).waiting[0].reason, /off-peak/);
  assert.equal(selectToEnqueue({ candidates: [ws], queue: [], policy, now: night }).picks.length, 1);
  assert.equal(selectToEnqueue({ candidates: [pr({ files: ['nx.json'], labels: ['ready', 'P0'] })], queue: [], policy, now: day }).picks.length, 1);
});
