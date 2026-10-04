// Provider side of consumer contracts: every consumer's example listing in
// product/services/*/contracts/catalog/products.json must match what
// listProducts() really returns.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { listProducts } from './products.ts';

const services = path.resolve(import.meta.dirname, '../..');
const consumers = fs.readdirSync(services).filter((s) => fs.existsSync(path.join(services, s, 'contracts/catalog/products.json')));

test('at least one consumer contract exists', () => {
  assert.ok(consumers.length > 0);
});

for (const consumer of consumers) {
  test(`${consumer}'s contract matches the real listing`, () => {
    const expected = JSON.parse(fs.readFileSync(path.join(services, consumer, 'contracts/catalog/products.json'), 'utf8'));
    assert.deepEqual(listProducts(), expected);
  });
}
