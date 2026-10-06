import test from 'node:test';
import assert from 'node:assert/strict';
import { age, escape, overall, percent, render, type Radiator, type Service } from './radiator.ts';

const service = (name: string, status: Service['status']): Service => ({ name, owner: 'team-x', status, build_minutes: 3.5, coverage: 0.814 });
const NOW = new Date('2026-10-06T12:00:00Z');
const data: Radiator = {
  generated_at: NOW.toISOString(),
  services: [service('orders', 'passing'), service('catalog', 'running')],
  queue: { depth: 3, oldest_minutes: 7, by_priority: { P0: 0, P1: 1, P2: 0, P3: 2, P4: 0 } },
  releases: [{ service: 'orders', version: '0.1.6', released_at: '2026-10-06T11:55:00Z' }],
};

test('one failing build turns the whole radiator red', () => {
  assert.equal(overall([service('a', 'passing'), service('b', 'failing'), service('c', 'running')]), 'failing');
  assert.equal(overall([service('a', 'passing'), service('b', 'running')]), 'running');
  assert.equal(overall([service('a', 'passing')]), 'passing');
});

test('percent rounds to whole numbers', () => {
  assert.equal(percent(0.814), '81%');
  assert.equal(percent(1), '100%');
});

test('ages read in minutes, then hours', () => {
  assert.equal(age('2026-10-06T11:55:00Z', NOW), '5 min ago');
  assert.equal(age('2026-10-06T09:00:00Z', NOW), '3 h ago');
  assert.equal(age('2026-10-06T12:01:00Z', NOW), '0 min ago');
});

test('render shows each service, the queue and releases', () => {
  const html = render(data, NOW);
  assert.match(html, /<header class="running">/);
  assert.match(html, /class="tile passing">\s*<span class="name">orders/);
  assert.match(html, /running · 3.5 min · coverage 81%/);
  assert.match(html, /<p class="depth">3<\/p>/);
  assert.match(html, /oldest 7 min/);
  assert.match(html, /P3 2/);
  assert.match(html, /orders <b>0.1.6<\/b> <span>5 min ago/);
});

test('an empty queue says so', () => {
  assert.match(render({ ...data, queue: { depth: 0, oldest_minutes: 0, by_priority: {} } }, NOW), /empty/);
});

test('names from the API are escaped', () => {
  assert.equal(escape(`<b>"x" & 'y'</b>`), '&lt;b&gt;&quot;x&quot; &amp; &#39;y&#39;&lt;/b&gt;');
  assert.doesNotMatch(render({ ...data, services: [service('<script>', 'passing')] }, NOW), /<script>/);
});
