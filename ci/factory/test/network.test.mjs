import test from 'node:test';
import assert from 'node:assert/strict';
import { networkProblems } from '../network.mjs';

const policy = { allowed_hosts: ['npm.internal', 'registry.internal'], checked_files: ['**/package-lock.json', '**/Dockerfile'] };

test('public registries are caught in air-gapped policy', () => {
  const added = new Map([
    ['product/a/package-lock.json', ['"resolved": "https://registry.npmjs.org/x/-/x-1.0.0.tgz"', '"resolved": "https://npm.internal/y.tgz"']],
    ['product/a/Dockerfile', ['FROM alpine:3.22', 'FROM registry.internal/base/alpine:3.22']],
    ['product/a/README.md', ['see https://example.com']],
  ]);
  assert.deepEqual(networkProblems(added, policy), [
    "product/a/package-lock.json uses registry.npmjs.org, which isn't an allowed host in ci/policy/network.yaml",
    "product/a/Dockerfile uses docker.io, which isn't an allowed host in ci/policy/network.yaml",
  ]);
});
