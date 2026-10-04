import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { createService } from '../new-service.mjs';

const require = createRequire(import.meta.url);
const { loadToolchains, projectFor } = require('../plugin.js');

test('every toolchain declares lint, test and build', () => {
  const toolchains = loadToolchains();
  assert.ok(Object.keys(toolchains).length > 0);
  for (const [name, tc] of Object.entries(toolchains)) {
    if (name === 'container') continue; // adds image targets only
    for (const t of ['lint', 'test', 'build']) assert.ok(tc.targets[t], `${name} lacks ${t}`);
  }
});

test('a service gets targets from its toolchains', () => {
  const p = projectFor('product/services/orders/service.yaml', { name: 'orders', toolchains: ['typescript'], criticality: 'critical', consumes: ['billing'] }, loadToolchains());
  assert.equal(p.root, 'product/services/orders');
  assert.equal(p.targets.test.options.cwd, 'product/services/orders');
  assert.deepEqual(p.implicitDependencies, ['billing']);
  assert.ok(p.tags.includes('boundary:product'));
  assert.ok(p.tags.includes('criticality:critical'));
});

test('an unknown toolchain is a clear error', () => {
  assert.throws(() => projectFor('product/x/service.yaml', { toolchains: ['cobol'] }, loadToolchains()), /unknown toolchain "cobol"/);
});

test('new-service creates a project from the template', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'svc-'));
  const dest = createService({ name: 'orders', lang: 'typescript', owner: 'team-orders', root });
  const yaml = fs.readFileSync(path.join(dest, 'service.yaml'), 'utf8');
  assert.match(yaml, /owner: team-orders/);
  assert.match(fs.readFileSync(path.join(dest, 'src/index.ts'), 'utf8'), /orders/);
  assert.ok(fs.existsSync(path.join(dest, 'guardrails.yaml')));
  assert.throws(() => createService({ name: 'orders', lang: 'typescript', owner: 'x', root }), /already exists/);
  assert.throws(() => createService({ name: 'Bad Name', lang: 'typescript', owner: 'x', root }), /lowercase/);
});

test('a language plus container runs both, in order', () => {
  const p = projectFor('product/services/api/service.yaml', { name: 'api', toolchains: ['go', 'container'] }, loadToolchains());
  assert.match(p.targets.build.options.command, /^CGO_ENABLED=0 go build .* && docker buildx build --load -t api:ci \.$/);
  assert.equal(p.targets.build.cache, false);
  assert.match(p.targets.lint.options.command, /go vet .* && hadolint Dockerfile/);
  assert.ok(!(p.targets.test.dependsOn || []).includes('test'));
});

test('a plain container service gets lint, build, test and package', () => {
  const p = projectFor('product/services/edge/service.yaml', { name: 'edge', toolchains: ['container'] }, loadToolchains());
  for (const t of ['lint', 'build', 'test', 'package']) assert.ok(p.targets[t], t);
});
