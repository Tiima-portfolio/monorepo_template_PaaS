import test from 'node:test';
import assert from 'node:assert/strict';
import { checkTitle, checkHistory, checkProvenance } from '../checks.mjs';

test('conventional titles and their bump', () => {
  assert.equal(checkTitle('fix: handle empty cart').bump, 'patch');
  assert.equal(checkTitle('feat(orders): add refunds').bump, 'minor');
  assert.equal(checkTitle('feat!: drop v1 API').bump, 'major');
  assert.equal(checkTitle('docs: typo').bump, 'none');
  assert.equal(checkTitle('ci: add gate').bump, 'none');
  assert.equal(checkTitle('Add stuff').ok, false);
  assert.equal(checkTitle('feat:missing space').ok, false);
});

test('merge commits fail history', () => {
  assert.equal(checkHistory([{ sha: 'a'.repeat(40), parents: ['b'] }]).ok, true);
  assert.equal(checkHistory([{ sha: 'c'.repeat(40), parents: ['a', 'b'] }]).ok, false);
});

const agentCommit = {
  sha: 'd'.repeat(40),
  message: 'docs: fix\n\nAgent-Id: example-docs-agent\nAgent-Model: m\nAgent-Task: T-1\nRequested-By: sami',
};

test('humans pass provenance', () => {
  const r = checkProvenance({ author: 'someone', commits: [], files: ['ci/x'], tier: 'R3' });
  assert.equal(r.isAgent, false);
  assert.equal(r.ok, true);
});

test('agent with trailers inside its boundary and trust passes alone', () => {
  const r = checkProvenance({ author: 'example-docs-agent[bot]', commits: [agentCommit], files: ['docs/a.md'], boundary: 'docs', tier: 'R0' });
  assert.equal(r.ok, true);
  assert.equal(r.needsHuman, false);
});

test('agent above its trust needs a human and raises the tier', () => {
  const r = checkProvenance({ author: 'example-docs-agent[bot]', commits: [agentCommit], files: ['docs/a.md'], boundary: 'docs', tier: 'R1' });
  assert.equal(r.needsHuman, true);
  assert.deepEqual(r.raise, ['agent_above_trust']);
});

test('missing trailers fail', () => {
  const r = checkProvenance({ author: 'example-docs-agent[bot]', commits: [{ sha: 'e'.repeat(40), message: 'docs: x' }], files: ['docs/a.md'], boundary: 'docs', tier: 'R0' });
  assert.equal(r.ok, false);
  assert.match(r.message, /lacks Agent-Id/);
});

test('agents can never touch policy or workflows', () => {
  const r = checkProvenance({ author: 'example-docs-agent[bot]', commits: [agentCommit], files: ['ci/policy/agents.yaml'], boundary: 'ci', tier: 'R3' });
  assert.equal(r.ok, false);
  assert.match(r.message, /may not change ci\/policy/);
});

test('agents stay in their boundaries', () => {
  const r = checkProvenance({ author: 'example-docs-agent[bot]', commits: [agentCommit], files: ['product/a/x.go'], boundary: 'product', tier: 'R1' });
  assert.equal(r.ok, false);
});
