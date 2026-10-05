import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { createService } from '../new-service.mjs';
import { BUILDER, buildArgs, createArgs } from '../container/buildx.mjs';

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
  assert.deepEqual(p.implicitDependencies, ['billing', 'toolchain-typescript']);
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
  assert.match(p.targets.build.options.command, /'CGO_ENABLED=0 go build [^']*' && node \.\.\/\.\.\/\.\.\/internal-tools\/toolchains\/container\/buildx\.mjs api --load -t api:ci \.$/);
  assert.equal(p.targets.build.cache, false);
  assert.match(p.targets.lint.options.command, /go vet .* && .*'hadolint Dockerfile'$/);
  assert.ok(!(p.targets.test.dependsOn || []).includes('test'));
});

test('every language toolchain and the container lint run in a pinned image', () => {
  const toolchains = loadToolchains();
  for (const [name, tc] of Object.entries(toolchains)) {
    const image = name === 'container' ? tc.targets.lint.image : tc.image;
    assert.match(image || '', /^ghcr\.io\/[^@]+@sha256:[0-9a-f]{64}$/, `${name} has no image pinned by digest`);
  }
});

test('a plain container service gets lint, build, test and package', () => {
  const p = projectFor('product/services/edge/service.yaml', { name: 'edge', toolchains: ['container'] }, loadToolchains());
  for (const t of ['lint', 'build', 'test', 'package']) assert.ok(p.targets[t], t);
});

test('container builds use the local BuildKit unless the service answered', () => {
  const env = { FACTORY_BUILDKIT_ADDR: 'tcp://buildkit:1234', FACTORY_BUILDKIT_CACHE_REF: 'reg/cache' };
  assert.deepEqual(buildArgs({}, 'edge', ['--load', '.'], false), ['buildx', 'build', '--load', '.']);
  assert.deepEqual(buildArgs(env, 'edge', ['--load', '.'], false), ['buildx', 'build', '--load', '.']);
  assert.deepEqual(buildArgs(env, 'edge', ['--load', '.'], true), ['buildx', 'build', '--builder', BUILDER, '--cache-from', 'type=registry,ref=reg/cache:edge', '--load', '.']);
});

test('only main runners write the BuildKit layer cache', () => {
  const env = { FACTORY_BUILDKIT_CACHE_REF: 'reg/cache', FACTORY_BUILDKIT_CACHE_WRITE: 'true' };
  assert.ok(buildArgs(env, 'edge', ['.'], true).includes('type=registry,ref=reg/cache:edge,mode=max'));
  assert.ok(!buildArgs({ ...env, FACTORY_BUILDKIT_CACHE_WRITE: 'false' }, 'edge', ['.'], true).includes('--cache-to'));
});

test('the BuildKit service builder uses the client certificate', () => {
  assert.deepEqual(createArgs({ FACTORY_BUILDKIT_ADDR: 'tcp://buildkit:1234' }), ['buildx', 'create', '--name', BUILDER, '--driver', 'remote', 'tcp://buildkit:1234']);
  assert.deepEqual(createArgs({ FACTORY_BUILDKIT_ADDR: 'tcp://buildkit:1234', FACTORY_BUILDKIT_TLS_DIR: '/certs' }).slice(6, 12),
    ['--driver-opt', 'cacert=/certs/ca.crt', '--driver-opt', 'cert=/certs/tls.crt', '--driver-opt', 'key=/certs/tls.key']);
});

const fakeToolchains = {
  go: {
    image: 'ghcr.io/o/r/ci-go@sha256:1',
    targets: {
      lint: { command: "test -z \"$(gofmt -l .)\" && echo 'vetted'", inputs: ['{projectRoot}/**/*.go'] },
      build: { command: 'go build -o dist/{name} .', inputs: ['{projectRoot}/**/*.go'] },
      local: { command: 'echo on host', image: false },
    },
  },
  container: {
    targets: {
      lint: { command: 'hadolint Dockerfile', image: 'ghcr.io/o/r/ci-lint@sha256:2', inputs: ['{projectRoot}/Dockerfile'] },
      build: { command: 'docker buildx build .' },
    },
  },
};

test('a toolchain with an image runs its targets through in-image.sh', () => {
  const p = projectFor('product/services/api/service.yaml', { name: 'api', toolchains: ['go'] }, fakeToolchains);
  assert.equal(p.targets.build.options.command, "sh ../../../internal-tools/toolchains/in-image.sh 'ghcr.io/o/r/ci-go@sha256:1' 'go build -o dist/api .'");
  assert.deepEqual(p.targets.build.inputs, ['{projectRoot}/**/*.go', { env: 'FACTORY_TOOLCHAIN_IMAGES' }]);
  assert.equal(p.targets.local.options.command, 'echo on host');
});

const workspace = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../..');
const run = (command, cwd, env = {}) => execFileSync('sh', ['-c', command], { cwd, encoding: 'utf8', env: { ...process.env, FACTORY_TOOLCHAIN_IMAGES: '', ...env } });

test('a wrapped command runs unchanged on the host when images are off', () => {
  const raw = "printf '%s|' \"it's\" \"$(echo ok)\" 'a b'";
  const toolchains = { sh: { image: 'ci-sh:1', targets: { t: { command: raw } } } };
  const p = projectFor('product/services/orders/service.yaml', { name: 'orders', toolchains: ['sh'] }, toolchains);
  const cwd = path.join(workspace, p.targets.t.options.cwd);
  assert.equal(run(p.targets.t.options.command, cwd), "it's|ok|a b|");
});

test('with images on, in-image.sh runs the command in the image as the caller', () => {
  const bin = fs.mkdtempSync(path.join(os.tmpdir(), 'docker-'));
  fs.writeFileSync(path.join(bin, 'docker'), '#!/bin/sh\nfor a in "$@"; do printf "%s\\n" "$a"; done\n', { mode: 0o755 });
  const cwd = path.join(workspace, 'product/services/orders');
  const env = { FACTORY_TOOLCHAIN_IMAGES: 'true', FACTORY_VERSION: '1.2.3', FACTORY_TOOLCHAIN_CACHE: path.join(bin, 'cache'), PATH: `${bin}:${process.env.PATH}` };
  const args = run("sh ../../../internal-tools/toolchains/in-image.sh 'ghcr.io/o/r/ci-go:abc@sha256:1' 'go test'", cwd, env).trim().split('\n');
  const uid = execFileSync('id', ['-u'], { encoding: 'utf8' }).trim();
  assert.equal(args[0], 'run');
  assert.ok(args.join(' ').includes(`--user ${uid}:`));
  assert.ok(args.join(' ').includes(`-v ${fs.realpathSync(workspace)}:${fs.realpathSync(workspace)}`));
  assert.ok(args.join(' ').includes(`-v ${path.join(bin, 'cache', 'ci-go')}:/home/ci`));
  assert.ok(args.includes('FACTORY_VERSION'));
  assert.deepEqual(args.slice(-4), ['ghcr.io/o/r/ci-go:abc@sha256:1', 'sh', '-c', 'go test']);
  const byToolchain = run("sh ../../../internal-tools/toolchains/in-image.sh python true", cwd, env);
  const pinned = loadToolchains().python.image;
  assert.ok(byToolchain.includes(`${pinned}\n`), `expected ${pinned}`);
  const mirrored = run("sh ../../../internal-tools/toolchains/in-image.sh 'ghcr.io/o/r/ci-go@sha256:1' true", cwd, { ...env, FACTORY_TOOLCHAIN_REGISTRY: 'registry.internal' });
  assert.ok(mirrored.includes('registry.internal/o/r/ci-go@sha256:1\n'));
});

test('a target can name its own image, and combined targets keep each one', () => {
  const p = projectFor('product/services/api/service.yaml', { name: 'api', toolchains: ['go', 'container'] }, fakeToolchains);
  assert.match(p.targets.lint.options.command, /ci-go@sha256:1' .* && sh \S+in-image\.sh 'ghcr\.io\/o\/r\/ci-lint@sha256:2' 'hadolint Dockerfile'$/);
  assert.match(p.targets.build.options.command, / && docker buildx build \.$/);
  assert.equal(p.targets.lint.inputs.filter((i) => i.env).length, 1);
});
