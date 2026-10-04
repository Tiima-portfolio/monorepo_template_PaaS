import test from 'node:test';
import assert from 'node:assert/strict';
import { report } from '../metrics-report.mjs';

test('weekly report', () => {
  const md = report({
    since: '2026-10-01T00:00:00Z',
    until: '2026-10-08T00:00:00Z',
    agents: ['bot'],
    prs: [
      { number: 1, author: 'sami', createdAt: '2026-10-02T10:00:00Z', mergedAt: '2026-10-02T12:00:00Z', labels: ['hotfix'], body: 'Feature-Id: CHK-1' },
      { number: 2, author: 'bot', createdAt: '2026-10-03T10:00:00Z', mergedAt: '2026-10-03T11:00:00Z', labels: [], body: 'Feature-Id: CHK-1' },
    ],
    issues: [{ title: 'escape: x', labels: ['escape'], createdAt: '2026-10-04T00:00:00Z', state: 'open' }],
    runs: [{ conclusion: 'success' }, { conclusion: 'failure' }],
  });
  assert.match(md, /PRs merged \| 2 \(1 by agents\)/);
  assert.match(md, /Factory runs blocked \| 50% of 2/);
  assert.match(md, /Hotfixes \| 1/);
  assert.match(md, /Escapes opened \/ open now \| 1 \/ 1/);
  assert.match(md, /\| CHK-1 \| 2 \| 2 h \|/);
});
