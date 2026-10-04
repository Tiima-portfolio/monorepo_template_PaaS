import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { apiBody, diff, normalize } from '../rulesets.mjs';

const want = JSON.parse(fs.readFileSync(new URL('../../../.github/rulesets/main.json', import.meta.url)));

test('ruleset files have the protections main needs', () => {
  const types = want.rules.map((r) => r.type);
  for (const t of ['deletion', 'non_fast_forward', 'required_linear_history', 'pull_request', 'required_status_checks']) assert.ok(types.includes(t), t);
  const pr = want.rules.find((r) => r.type === 'pull_request');
  assert.deepEqual(pr.parameters.allowed_merge_methods, ['squash']);
  const checks = want.rules.find((r) => r.type === 'required_status_checks');
  assert.deepEqual(checks.parameters.required_status_checks.map((c) => c.context), ['factory/admission']);
});

test('live rulesets with extra API fields still match', () => {
  const live = { ...want, id: 1, source: 'x', _links: {}, rules: [...want.rules].reverse(), bypass_actors: want.bypass_actors.map((b) => ({ ...b, extra: 1 })) };
  assert.deepEqual(diff(want, live), []);
});

test('drift is reported by field', () => {
  assert.deepEqual(diff(want, null), ['missing']);
  const live = { ...want, enforcement: 'disabled' };
  assert.deepEqual(diff(want, live), ['enforcement']);
  assert.ok(normalize(want).rules.length > 0);
});

test('defaults GitHub adds to rule parameters are not drift', () => {
  const live = JSON.parse(JSON.stringify(want));
  live.rules.find((r) => r.type === 'pull_request').parameters.required_reviewers = [];
  assert.deepEqual(diff(want, live), []);
});

test('our own keys are never sent', () => {
  assert.equal(apiBody({ _optional: 'x', name: 'n' })._optional, undefined);
});
