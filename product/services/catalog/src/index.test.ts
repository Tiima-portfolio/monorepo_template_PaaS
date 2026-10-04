import test from 'node:test';
import assert from 'node:assert/strict';
import { greeting } from './index.ts';

test('greets by name', () => {
  assert.equal(greeting('Ada'), 'Hello from catalog, Ada');
});
