import test from 'node:test';
import assert from 'node:assert/strict';
import { activeQuarantine, classify, workingDaysBetween } from '../flaky.mjs';

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
  assert.deepEqual([...activeQuarantine(issues, now)], ['orders']);
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
