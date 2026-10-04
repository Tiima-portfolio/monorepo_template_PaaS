#!/usr/bin/env node
// Writes mutation-score evidence from the affected projects' mutation reports
// (written by their toolchain's mutation target). Run from the base branch's
// copy by the verify job, from risk tier R2 up.
// Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_SHA, FACTORY_OUT, FACTORY_GATE.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import YAML from 'yaml';
import { addedLines, diffMutation } from './coverage.mjs';
import { matchesAny } from './lib/glob.mjs';
import { loadPolicy } from './lib/policy.mjs';

const env = process.env;
const run = (cmd, args) => execFileSync(cmd, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
const gate = JSON.parse(fs.readFileSync(env.FACTORY_GATE || 'gate/gate.json', 'utf8'));
const testPaths = loadPolicy('risk').test_paths;
const floors = loadPolicy('test-adequacy').mutation_score;

const results = [];
for (const name of gate.affected || []) {
  const project = JSON.parse(run('npx', ['nx', 'show', 'project', name, '--json']));
  const file = path.join(project.root, 'mutation/report.json');
  if (!fs.existsSync(file)) continue;
  const added = new Map();
  for (const [f, lines] of addedLines(run('git', ['diff', '-U0', `${env.FACTORY_BASE}...${env.FACTORY_HEAD}`, '--', project.root]))) {
    if (f.startsWith(`${project.root}/`) && !matchesAny(f, testPaths)) added.set(f.slice(project.root.length + 1), lines);
  }
  const r = diffMutation(added, JSON.parse(fs.readFileSync(file, 'utf8')));
  if (!r.total) continue;
  const criticality = (project.tags || []).find((t) => t.startsWith('criticality:'))?.split(':')[1] || 'normal';
  let guardrails = {};
  try { guardrails = YAML.parse(run('git', ['show', `${env.FACTORY_BASE}:${project.root}/guardrails.yaml`])) || {}; } catch {}
  const min = Math.max(floors[criticality] ?? floors.normal, guardrails.thresholds?.mutation_score || 0);
  results.push({ name, ...r, min, ok: r.pct >= min });
}

const status = !results.length ? 'skipped' : results.every((r) => r.ok) ? 'pass' : 'fail';
const details = results.length
  ? results.map((r) => `${r.name} ${r.pct}% of ${r.total} mutant(s) killed, needs ${r.min}%${r.survivors.length ? `; survived: ${r.survivors.slice(0, 5).join(', ')}` : ''}`).join('; ')
  : 'no mutants on changed lines (or no mutation target for these languages yet)';
const out = path.join(env.FACTORY_OUT || 'factory-out', 'evidence');
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, 'mutation-score.json'), JSON.stringify({ check: 'mutation-score', status, sha: env.FACTORY_SHA, details }, null, 2));
console.log(`mutation-score: ${status} (${details})`);
