#!/usr/bin/env node
// Admission, run by .github/workflows/factory.yml after the gate and verify
// jobs. Reads gate.json and every evidence record under FACTORY_IN, decides,
// writes the summary and exits non-zero when the merge is blocked.
import fs from 'node:fs';
import path from 'node:path';
import { decide } from './admission.mjs';

const dir = process.env.FACTORY_IN || 'factory-in';
const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]));
const all = walk(dir);
const gateFile = all.find((f) => path.basename(f) === 'gate.json');
if (!gateFile) {
  console.error('No gate.json found: the gate job did not finish.');
  process.exit(1);
}
const gate = JSON.parse(fs.readFileSync(gateFile, 'utf8'));
const records = all
  .filter((f) => f.includes(`${path.sep}evidence${path.sep}`) && f.endsWith('.json'))
  .map((f) => JSON.parse(fs.readFileSync(f, 'utf8')));

const result = decide({ ...gate, records });
const out = process.env.FACTORY_OUT || '.';
fs.writeFileSync(path.join(out, 'admission.md'), result.summary + '\n');
fs.writeFileSync(path.join(out, 'admission.json'), JSON.stringify({ allowed: result.allowed, blocking: result.blocking, tier: gate.tier, sha: gate.sha }, null, 2));
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, result.summary + '\n');
console.log(result.summary);
process.exit(result.allowed ? 0 : 1);
