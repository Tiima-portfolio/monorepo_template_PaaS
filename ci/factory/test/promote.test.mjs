import test from 'node:test';
import assert from 'node:assert/strict';
import { planPromotions } from '../promote.mjs';

const files = [
  { path: 'internal-services/sim/pins.yaml', pins: { orders: '0.1.1' } },
  { path: 'platform/ci-image/pins.yaml', pins: { orders: '0.1.2', lint: '1.0.0' } },
];

test('only consumers pinned below the new release get a bump', () => {
  const b = planPromotions(files, [{ service: 'orders', version: '0.1.2' }]);
  assert.deepEqual(b, [{ path: 'internal-services/sim/pins.yaml', service: 'orders', from: '0.1.1', to: '0.1.2' }]);
});

test('the newest release wins and holds stop promotion', () => {
  const rel = [{ service: 'orders', version: '0.1.3' }, { service: 'orders', version: '0.2.0' }];
  assert.equal(planPromotions(files, rel)[0].to, '0.2.0');
  assert.deepEqual(planPromotions(files, rel, ['orders']), []);
});
