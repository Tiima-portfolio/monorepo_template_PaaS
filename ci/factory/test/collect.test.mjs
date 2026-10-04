import test from 'node:test';
import assert from 'node:assert/strict';
import { digest, indexSql, linkToMain, sign } from '../collect.mjs';

const head = 'a'.repeat(40);
const rec = { check: 'unit-tests', status: 'pass', sha: head };
const bundle = () => ({ sha: head, tree: 't1', run: { path: '.github/workflows/factory.yml' }, decision: { allowed: true }, records: [{ ...rec, digest: digest(rec) }] });

test('an admitted bundle with the same tree links to main', () => {
  const r = linkToMain(bundle(), { sha: 'm', tree: 't1' }, head);
  assert.deepEqual(r, { ok: true, treeMatch: true, problems: [] });
});

test('a different tree is valid evidence but not carried over', () => {
  const r = linkToMain(bundle(), { sha: 'm', tree: 't2' }, head);
  assert.equal(r.ok, true);
  assert.equal(r.treeMatch, false);
});

test('altered records, blocked decisions and wrong commits are caught', () => {
  const b = bundle();
  b.records[0].status = 'fail';
  assert.match(linkToMain(b, { tree: 't1' }, head).problems[0], /altered/);
  const blocked = { ...bundle(), decision: { allowed: false } };
  assert.equal(linkToMain(blocked, { tree: 't1' }, head).ok, false);
  assert.equal(linkToMain(bundle(), { tree: 't1' }, 'b'.repeat(40)).ok, false);
  assert.equal(linkToMain(null, { tree: 't1' }, head).ok, false);
});

test('signatures depend on the key and the content', () => {
  assert.notEqual(sign({ a: 1 }, 'k1'), sign({ a: 1 }, 'k2'));
  assert.equal(sign({ a: 1 }, 'k1'), sign({ a: 1 }, 'k1'));
});

test('index rows for each check and the decision, safely quoted', () => {
  const body = { main: { sha: 'm1' }, pr: 7, pr_head: 'h', tree_match: true, problems: [], pr_bundle: { tier: 'R1', decision: { allowed: true, blocking: [] }, records: [{ check: 'unit-tests', status: 'pass', details: "it's fine" }] } };
  const sql = indexSql(body, 'org/repo', 's3://b/x.json');
  assert.match(sql, /'unit-tests', 'pass', 'it''s fine', 'R1', true, 's3:\/\/b\/x.json'/);
  assert.match(sql, /'admission', 'allowed'/);
});
