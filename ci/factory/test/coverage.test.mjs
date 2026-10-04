import test from 'node:test';
import assert from 'node:assert/strict';
import { addedLines, diffCoverage, parseGoCover, parseLcov, ratchet, totalCoverage, diffMutation } from '../coverage.mjs';

test('lcov', () => {
  const c = parseLcov('TN:\nSF:src/a.ts\nDA:1,1\nDA:2,0\nend_of_record\n');
  assert.deepEqual([...c.get('src/a.ts')], [[1, 1], [2, 0]]);
});

test('go cover profile', () => {
  const c = parseGoCover('mode: set\norders/main.go:6.35,8.2 1 1\norders/main.go:10.13,12.2 1 0\n', 'orders');
  assert.equal(c.get('main.go').get(7), 1);
  assert.equal(c.get('main.go').get(11), 0);
});

test('added lines from a zero-context diff', () => {
  const d = 'diff --git a/x b/x\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1,0 +2,2 @@\n+a\n+b\n@@ -9 +11 @@\n-c\n+d\n--- a/gone.ts\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n';
  assert.deepEqual([...addedLines(d).get('src/a.ts')], [2, 3, 11]);
  assert.equal(addedLines(d).has('gone.ts'), false);
});

test('only executable changed lines count', () => {
  const added = new Map([['src/a.ts', new Set([1, 2, 3])]]);
  const cov = new Map([['src/a.ts', new Map([[1, 1], [2, 0]])]]);
  assert.deepEqual(diffCoverage(added, cov), { covered: 1, total: 2, pct: 50, uncovered: ['src/a.ts:2'] });
  assert.equal(diffCoverage(new Map(), cov).pct, null);
});

test('total coverage and the ratchet', () => {
  const cov = new Map([['a.ts', new Map([[1, 1], [2, 0], [3, 2], [4, 1]])]]);
  assert.equal(totalCoverage(cov), 75);
  assert.deepEqual(ratchet({ a: 75, b: 50, c: 40 }, { a: { coverage: 75.4 }, b: { coverage: 60 } }), [{ name: 'b', before: 60, now: 50 }]);
});

test('mutation score counts only changed lines', () => {
  const report = { files: [{ file_name: 'a.go', mutations: [
    { line: 4, status: 'KILLED' }, { line: 4, status: 'LIVED', type: 'CONDITIONALS_BOUNDARY' }, { line: 9, status: 'LIVED' }, { line: 4, status: 'NOT COVERED' },
  ] }] };
  const r = diffMutation(new Map([['a.go', new Set([4])]]), report);
  assert.equal(r.pct, 50);
  assert.deepEqual(r.survivors, ['a.go:4 CONDITIONALS_BOUNDARY']);
});
