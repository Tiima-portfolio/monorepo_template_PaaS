import test from 'node:test';
import assert from 'node:assert/strict';
import { activeQuarantine, classify, classifyTests, parseGoJson, parseJunit, workingDaysBetween } from '../flaky.mjs';

test('working days skip weekends', () => {
  // Friday 2026-10-02 to Monday 2026-10-05 is one working day.
  assert.equal(workingDaysBetween(new Date('2026-10-02T12:00:00Z'), new Date('2026-10-05T12:00:00Z')), 1);
  assert.equal(workingDaysBetween(new Date('2026-10-05T12:00:00Z'), new Date('2026-10-12T12:00:00Z')), 5);
});

test('quarantine expires after 5 working days', () => {
  const now = new Date('2026-10-12T13:00:00Z');
  const issues = [
    { title: 'quarantine: orders:test', created_at: '2026-10-08T12:00:00Z' },
    { title: 'quarantine: catalog:test', created_at: '2026-10-01T12:00:00Z' },
    { title: 'something else', created_at: '2026-10-11T12:00:00Z' },
  ];
  assert.deepEqual([...activeQuarantine(issues, now).keys()], ['orders']);
});

test('a single pass on retry is not a confirmed flake', () => {
  assert.equal(classify([true]), 'pass');
  assert.equal(classify([false, false]), 'fail');
  assert.equal(classify([false, true, ...Array(20).fill(true)]), 'pass-on-retry');
  assert.equal(classify([false, true, ...Array(19).fill(true), false]), 'flaky');
});

test('a quarantined test must still pass one of three runs', () => {
  assert.equal(classify([false, false, true], { quarantined: true }), 'pass-quarantined');
  assert.equal(classify([false, false, false], { quarantined: true }), 'fail');
});

test('junit and go reports', () => {
  const xml = '<testsuites><testcase name="a" classname="s"/><testcase name="b" classname="s"><failure message="x"/></testcase><testcase name="c"><skipped/></testcase></testsuites>';
  assert.deepEqual([...parseJunit(xml)], [['s.a', 'pass'], ['s.b', 'fail']]);
  const go = '{"Action":"run","Test":"TestA","Package":"p"}\n{"Action":"fail","Test":"TestA","Package":"p"}\n{"Action":"pass","Test":"TestB","Package":"p"}';
  assert.deepEqual([...parseGoJson(go)], [['p.TestA', 'fail'], ['p.TestB', 'pass']]);
});

test('per-test verdicts', () => {
  const run = (o) => new Map(Object.entries(o));
  const first = run({ a: 'fail', b: 'fail', c: 'pass', q: 'fail' });
  const runs = [first, run({ a: 'pass', b: 'fail', q: 'pass' }), ...Array(19).fill(run({ a: 'pass' })), run({ a: 'fail' })];
  const v = classifyTests(runs, new Set(['q']));
  assert.equal(v.get('a'), 'flaky');
  assert.equal(v.get('b'), 'fail');
  assert.equal(v.get('q'), 'pass-quarantined');
  assert.equal(v.has('c'), false);
});

test('per-test quarantine titles', () => {
  const q = activeQuarantine([{ title: 'quarantine: orders:orders.TestDiscount', created_at: '2026-10-08T12:00:00Z' }], new Date('2026-10-09T12:00:00Z'));
  assert.ok(q.get('orders').has('orders.TestDiscount'));
});
