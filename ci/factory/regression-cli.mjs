#!/usr/bin/env node
// For PRs labelled escape-fix: proves the fix comes with a test that would
// have caught the escape. The PR's tests are run against the parent commit's
// code (every changed non-test file put back to the base version) and must
// fail there; the normal test run already shows they pass with the fix.
//
// Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_SHA, FACTORY_OUT.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { matchesAny } from './lib/glob.mjs';
import { loadPolicy } from './lib/policy.mjs';

const env = process.env;
const git = (...a) => execFileSync('git', a, { encoding: 'utf8' }).trim();
const out = path.join(env.FACTORY_OUT || 'factory-out', 'evidence');
fs.mkdirSync(out, { recursive: true });
const write = (ok, details) => {
  fs.writeFileSync(path.join(out, 'regression-test.json'), JSON.stringify({ check: 'regression-test', status: ok ? 'pass' : 'fail', sha: env.FACTORY_SHA, details }, null, 2));
  console.log(`regression-test: ${ok ? 'pass' : 'fail'} (${details})`);
};

const testPaths = loadPolicy('risk').test_paths;
const changes = git('diff', '--name-status', `${env.FACTORY_BASE}...${env.FACTORY_HEAD}`).split('\n').filter(Boolean).map((l) => l.split('\t'));
const tests = changes.filter(([s, f]) => s !== 'D' && matchesAny(f, testPaths));
const code = changes.filter(([, f]) => !matchesAny(f, testPaths));
if (!tests.length) {
  write(false, 'an escape fix must add or change a test');
  process.exit(0);
}
if (!code.length) {
  write(false, 'an escape fix must change code as well as tests');
  process.exit(0);
}

// Put the code back as it was on the base branch, keep the new tests.
const mergeBase = git('merge-base', env.FACTORY_BASE, env.FACTORY_HEAD);
for (const [status, file] of code) {
  if (status === 'A') fs.rmSync(file, { force: true });
  else git('checkout', mergeBase, '--', file);
}
const onParent = spawnSync('npx', ['nx', 'affected', '-t', 'test', `--base=${env.FACTORY_BASE}`, `--head=${env.FACTORY_HEAD}`, '--skip-nx-cache', '--outputStyle=static'], { stdio: 'inherit' }).status;
git('checkout', env.FACTORY_HEAD, '--', '.');

write(onParent !== 0, onParent !== 0
  ? `the new tests (${tests.map(([, f]) => f).join(', ')}) fail without the fix`
  : 'the new tests also pass without the fix, so they would not have caught the escape');
