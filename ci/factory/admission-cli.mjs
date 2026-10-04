#!/usr/bin/env node
// Admission, run by .github/workflows/factory.yml after the gate and verify
// jobs. Reads gate.json and every evidence record under FACTORY_IN, decides,
// writes the summary and exits non-zero when the merge is blocked.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { decide } from './admission.mjs';
import { approvalsMet } from './owners.mjs';
import { loadPolicy } from './lib/policy.mjs';

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

const readJson = (f) => (f && fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : undefined);

// owner-approval: the routed approvals against the PR's current approvals.
const approvers = readJson(process.env.FACTORY_APPROVERS_FILE);
if (approvers && gate.approvals) {
  const met = approvalsMet(gate.approvals, approvers, { author: gate.author, requester: gate.requester, teams: loadPolicy('teams') });
  records.push({
    check: 'owner-approval',
    status: met.ok ? 'pass' : 'fail',
    sha: gate.sha,
    details: met.ok ? `approved by ${approvers.join(', ') || 'nobody needed'}` : `waiting for ${met.missing.map((m) => `${m.service}: ${m.teams.join(' or ')}`).join('; ')}`,
  });
}
const jobs = readJson(process.env.FACTORY_JOBS_FILE);
const run = readJson(process.env.FACTORY_RUN_FILE);
const result = decide({ ...gate, records, jobs, run });
const out = process.env.FACTORY_OUT || '.';
fs.writeFileSync(path.join(out, 'admission.md'), result.summary + '\n');
fs.writeFileSync(path.join(out, 'admission.json'), JSON.stringify({ allowed: result.allowed, blocking: result.blocking, tier: gate.tier, sha: gate.sha }, null, 2));
// The evidence bundle for this commit: what was required, what was present,
// what GitHub says the jobs did, and the decision.
const bundle = {
  version: 1,
  sha: gate.sha,
  tree: gate.tree,
  event: gate.event,
  run: { id: process.env.GITHUB_RUN_ID, attempt: process.env.GITHUB_RUN_ATTEMPT, ...(run || {}) },
  jobs: jobs || [],
  tier: gate.tier,
  reasons: gate.reasons,
  boundary: gate.boundary,
  override: gate.override,
  required: gate.required,
  records: records.map((r) => ({ ...r, digest: crypto.createHash('sha256').update(JSON.stringify(r)).digest('hex') })),
  decision: { allowed: result.allowed, blocking: result.blocking },
  decided_at: new Date().toISOString(),
};
fs.writeFileSync(path.join(out, 'bundle.json'), JSON.stringify(bundle, null, 2));
if (process.env.GITHUB_STEP_SUMMARY) fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, result.summary + '\n');
console.log(result.summary);
process.exit(result.allowed ? 0 : 1);
