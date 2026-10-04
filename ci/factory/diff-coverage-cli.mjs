#!/usr/bin/env node
// Writes the diff-coverage evidence record after the tests ran. Run from the
// base branch's copy by the verify job.
//
// Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_SHA, FACTORY_OUT, FACTORY_GATE (gate.json).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import YAML from 'yaml';
import { addedLines, diffCoverage, parseGoCover, parseLcov } from './coverage.mjs';
import { matchesAny } from './lib/glob.mjs';
import { loadPolicy } from './lib/policy.mjs';

const env = process.env;
const run = (cmd, args) => execFileSync(cmd, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
const gate = JSON.parse(fs.readFileSync(env.FACTORY_GATE || 'gate/gate.json', 'utf8'));
const testPaths = loadPolicy('risk').test_paths;
const floors = loadPolicy('test-adequacy').diff_coverage;

const results = [];
for (const name of gate.affected || []) {
  const project = JSON.parse(run('npx', ['nx', 'show', 'project', name, '--json']));
  const root = project.root;
  let coverage = null;
  if (fs.existsSync(path.join(root, 'coverage/lcov.info'))) {
    coverage = parseLcov(fs.readFileSync(path.join(root, 'coverage/lcov.info'), 'utf8'));
  } else if (fs.existsSync(path.join(root, 'coverage/cover.out'))) {
    const module = /^module\s+(\S+)/m.exec(fs.readFileSync(path.join(root, 'go.mod'), 'utf8'))?.[1] || '';
    coverage = parseGoCover(fs.readFileSync(path.join(root, 'coverage/cover.out'), 'utf8'), module);
  }
  if (!coverage) continue;
  const diff = run('git', ['diff', '-U0', `${env.FACTORY_BASE}...${env.FACTORY_HEAD}`, '--', root]);
  const added = new Map();
  for (const [file, lines] of addedLines(diff)) {
    if (!file.startsWith(`${root}/`) || matchesAny(file, testPaths)) continue;
    added.set(file.slice(root.length + 1), lines);
  }
  const result = diffCoverage(added, coverage);
  if (result.total === 0) continue;
  const criticality = (project.tags || []).find((t) => t.startsWith('criticality:'))?.split(':')[1] || 'normal';
  let guardrails = {};
  try { guardrails = YAML.parse(run('git', ['show', `${env.FACTORY_BASE}:${root}/guardrails.yaml`])) || {}; } catch {}
  const min = Math.max(floors[criticality] ?? floors.normal, guardrails.thresholds?.diff_coverage || 0);
  results.push({ name, ...result, min, ok: result.pct >= min });
}

const out = path.join(env.FACTORY_OUT || 'factory-out', 'evidence');
fs.mkdirSync(out, { recursive: true });
const status = !results.length ? 'skipped' : results.every((r) => r.ok) ? 'pass' : 'fail';
const details = results.length
  ? results.map((r) => `${r.name} ${r.pct}% of ${r.total} changed line(s), needs ${r.min}%${r.uncovered.length ? `; not run: ${r.uncovered.slice(0, 5).join(', ')}` : ''}`).join('; ')
  : 'no changed executable lines with coverage';
fs.writeFileSync(path.join(out, 'diff-coverage.json'), JSON.stringify({ check: 'diff-coverage', status, sha: env.FACTORY_SHA, details }, null, 2));
console.log(`diff-coverage: ${status} (${details})`);
