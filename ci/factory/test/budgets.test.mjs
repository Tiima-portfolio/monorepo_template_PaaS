import test from 'node:test';
import assert from 'node:assert/strict';
import { feedbackBudget } from '../budgets.mjs';
import { loadPolicy } from '../lib/policy.mjs';

test('feedback within and over budget', () => {
  const policy = loadPolicy('budgets');
  const start = '2026-10-04T10:00:00Z';
  assert.equal(feedbackBudget('R1', start, new Date('2026-10-04T10:08:00Z'), policy).ok, true);
  const over = feedbackBudget('R1', start, new Date('2026-10-04T10:12:30Z'), policy);
  assert.deepEqual([over.ok, over.minutes, over.budget], [false, 12.5, 10]);
});

test('hard limits are above budgets', () => {
  const policy = loadPolicy('budgets');
  for (const v of [...Object.values(policy.stages), ...Object.values(policy.feedback)]) assert.ok(v.hard > v.budget);
});
