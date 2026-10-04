import test from 'node:test';
import assert from 'node:assert/strict';
import { listProducts } from './products.ts';

test('lists every product without a query', () => {
  assert.equal(listProducts().length, 2);
});

test('filters by name, ignoring case and spaces', () => {
  assert.deepEqual(listProducts('  TEAM ').map((p) => p.id), ['p-2']);
});
