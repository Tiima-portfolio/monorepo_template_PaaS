import test from 'node:test';
import assert from 'node:assert/strict';
import { checkDependencies } from '../deps.mjs';

const node = (root) => ({ data: { root } });
const graph = (deps) => ({
  nodes: {
    orders: node('product/services/orders'),
    catalog: node('product/services/catalog'),
    sim: node('internal-services/sim'),
    lint: node('internal-tools/lint'),
  },
  dependencies: { orders: [], catalog: [], sim: [], lint: [], ...deps },
});

test('allowed directions pass', () => {
  assert.deepEqual(checkDependencies(graph({
    orders: [{ target: 'catalog', type: 'static' }],
    sim: [{ target: 'orders', type: 'implicit' }],
    lint: [{ target: 'orders', type: 'implicit' }],
  })), []);
});

test('product may never depend on an internal tool', () => {
  const p = checkDependencies(graph({ orders: [{ target: 'lint', type: 'implicit' }] }));
  assert.match(p[0], /orders \(product\) may not depend on lint \(internal-tools\)/);
});

test('cross-boundary source imports are refused', () => {
  const p = checkDependencies(graph({ sim: [{ target: 'orders', type: 'static' }] }));
  assert.match(p[0], /imports orders's code across boundaries/);
});

test('cycles are refused', () => {
  const p = checkDependencies(graph({ orders: [{ target: 'catalog', type: 'implicit' }], catalog: [{ target: 'orders', type: 'implicit' }] }));
  assert.ok(p.some((x) => /cycle: (orders -> catalog -> orders|catalog -> orders -> catalog)/.test(x)));
});

test('external packages are ignored', () => {
  assert.deepEqual(checkDependencies(graph({ orders: [{ target: 'npm:yaml', type: 'static' }] })), []);
});
