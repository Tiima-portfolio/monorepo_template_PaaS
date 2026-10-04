import test from 'node:test';
import assert from 'node:assert/strict';
import { latestVersion, nextVersion, planReleases } from '../release.mjs';

test('latest version per service', () => {
  const tags = ['orders/v0.1.0', 'orders/v0.10.0', 'orders/v0.9.1', 'catalog/v2.0.0', 'orders/vbad'];
  assert.equal(latestVersion('orders', tags), '0.10.0');
  assert.equal(latestVersion('pricing', tags), null);
});

test('next version', () => {
  assert.equal(nextVersion(null, 'patch'), '0.1.0');
  assert.equal(nextVersion('0.1.0', 'patch'), '0.1.1');
  assert.equal(nextVersion('0.1.1', 'minor'), '0.2.0');
  assert.equal(nextVersion('0.2.0', 'major'), '0.3.0');
  assert.equal(nextVersion('1.2.3', 'major'), '2.0.0');
  assert.equal(nextVersion('1.2.3', 'none'), null);
});

test('releases follow history order and see earlier releases', () => {
  const commits = [
    { sha: 'a', title: 'feat(orders): refunds', affected: ['orders', 'catalog'] },
    { sha: 'b', title: 'docs: readme', affected: ['orders'] },
    { sha: 'c', title: 'fix(orders): rounding', affected: ['orders'] },
  ];
  const r = planReleases(commits, ['orders/v1.0.0']);
  assert.deepEqual(r.map((x) => x.tag), ['catalog/v0.1.0', 'orders/v1.1.0', 'orders/v1.1.1']);
  assert.deepEqual(r.map((x) => x.sha), ['a', 'a', 'c']);
});
