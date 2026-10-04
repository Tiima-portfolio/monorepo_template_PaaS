import test from 'node:test';
import assert from 'node:assert/strict';
import { contractProblems } from '../contracts.mjs';

test('declared contracts and consumed providers are covered', () => {
  assert.deepEqual(contractProblems([{
    name: 'orders', service: { contract: ['api/openapi.yaml'], consumes: ['catalog'] },
    files: ['api/openapi.yaml', 'contracts/catalog/catalog_contract_test.go'],
  }]), []);
});

test('a missing contract file or consumer test is reported', () => {
  const p = contractProblems([{ name: 'orders', service: { contract: ['api/openapi.yaml'], consumes: ['catalog'] }, files: ['main.go'] }]);
  assert.equal(p.length, 2);
  assert.match(p[1], /no contract test under contracts\/catalog\//);
});
