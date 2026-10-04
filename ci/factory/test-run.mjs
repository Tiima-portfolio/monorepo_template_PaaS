#!/usr/bin/env node
// Runs the affected test targets with flaky-test handling and writes the
// unit-tests evidence record plus flaky.json. Run from the base branch's copy
// by the verify job.
//
// Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_SHA, FACTORY_OUT, FACTORY_AFFECTED,
// FACTORY_QUARANTINE_FILE (JSON list of open quarantine issues).
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync, execFileSync } from 'node:child_process';
import { FLAKE_RERUNS, QUARANTINE_ATTEMPTS, activeQuarantine, classify } from './flaky.mjs';

const env = process.env;
const out = path.join(env.FACTORY_OUT || 'factory-out', 'evidence');
fs.mkdirSync(out, { recursive: true });
const write = (status, details) => {
  fs.writeFileSync(path.join(out, 'unit-tests.json'), JSON.stringify({ check: 'unit-tests', status, sha: env.FACTORY_SHA, details }, null, 2));
  console.log(`unit-tests: ${status} (${details})`);
};

if (Number(env.FACTORY_AFFECTED || '0') === 0) {
  write('skipped', 'nothing affected');
  process.exit(0);
}

const nx = (args, opts = {}) => spawnSync('npx', ['nx', ...args, '--outputStyle=static'], { stdio: 'inherit', ...opts }).status === 0;
const range = [`--base=${env.FACTORY_BASE}`, `--head=${env.FACTORY_HEAD}`];

if (nx(['affected', '-t', 'test', ...range])) {
  write('pass', 'nx affected -t test');
  fs.writeFileSync(path.join(env.FACTORY_OUT || 'factory-out', 'flaky.json'), '[]');
  process.exit(0);
}

const projects = JSON.parse(execFileSync('npx', ['nx', 'show', 'projects', '--affected', '--withTarget=test', ...range, '--json'], { encoding: 'utf8' }));
const issues = env.FACTORY_QUARANTINE_FILE && fs.existsSync(env.FACTORY_QUARANTINE_FILE) ? JSON.parse(fs.readFileSync(env.FACTORY_QUARANTINE_FILE, 'utf8')) : [];
const quarantine = activeQuarantine(issues);
const results = {};
for (const p of projects) {
  const runs = [nx(['run', `${p}:test`])];
  if (runs[0]) { results[p] = 'pass'; continue; }
  const q = quarantine.has(p);
  const extra = q ? QUARANTINE_ATTEMPTS - 1 : 1;
  for (let i = 0; i < extra && !runs.some(Boolean); i++) runs.push(nx(['run', `${p}:test`, '--skip-nx-cache']));
  if (!q && runs[1]) {
    for (let i = 0; i < FLAKE_RERUNS; i++) runs.push(nx(['run', `${p}:test`, '--skip-nx-cache']));
  }
  results[p] = classify(runs, { quarantined: q });
}

const flaky = Object.entries(results).filter(([, r]) => r === 'flaky').map(([p]) => p);
fs.writeFileSync(path.join(env.FACTORY_OUT || 'factory-out', 'flaky.json'), JSON.stringify(flaky));
const failed = Object.entries(results).filter(([, r]) => r === 'fail').map(([p]) => p);
const notes = Object.entries(results).filter(([, r]) => r !== 'pass').map(([p, r]) => `${p}: ${r}`).join(', ');
// A confirmed flake doesn't block this PR; it is quarantined instead.
write(failed.length ? 'fail' : 'pass', notes || 'all passed');
