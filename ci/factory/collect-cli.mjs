#!/usr/bin/env node
// Evidence collector, run by .github/workflows/evidence.yml on every push to
// main, on the main runner pool and with base-branch code. It finds the PR the
// commit came from, takes that PR's last admitted evidence bundle, checks it,
// links it to the main commit and stores the result.
//
// Env: GITHUB_REPOSITORY, GITHUB_SHA, GH_TOKEN, FACTORY_EVIDENCE_KEY (optional
// HMAC key), FACTORY_EVIDENCE_S3_URI (optional, e.g. s3://factory-evidence).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { indexSql, linkToMain, sign } from './collect.mjs';

const env = process.env;
const repo = env.GITHUB_REPOSITORY;
const sha = env.GITHUB_SHA;
const sh = (cmd, args) => (execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }) || '').trim();
const gh = (...args) => sh('gh', args);
const tryRun = (fn) => { try { return fn(); } catch { return null; } };

const main = { sha, tree: sh('git', ['rev-parse', `${sha}^{tree}`]) };
const pr = tryRun(() => JSON.parse(gh('api', `repos/${repo}/commits/${sha}/pulls`, '--jq', '[.[] | select(.merged_at != null)] | first | {number, head: .head.sha}')));

let result;
let prBundle = null;
if (!pr?.number) {
  // A commit on main without a PR bypassed the factory: break-glass.
  result = { ok: false, treeMatch: false, problems: ['commit reached main without a PR: recorded as a break-glass override'] };
} else {
  const runId = tryRun(() => gh('api', `repos/${repo}/actions/workflows/factory.yml/runs?head_sha=${pr.head}&event=pull_request&per_page=30`,
    '--jq', '[.workflow_runs[] | select(.conclusion == "success")] | first | .id'));
  const dir = fs.mkdtempSync('evidence-');
  if (runId && runId !== 'null') {
    tryRun(() => gh('run', 'download', runId, '--repo', repo, '-n', 'factory-evidence', '-D', dir));
  }
  const file = path.join(dir, 'bundle.json');
  prBundle = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : null;
  result = linkToMain(prBundle, main, pr.head);
}

const body = {
  version: 1,
  main,
  pr: pr?.number || null,
  pr_head: pr?.head || null,
  linked: result.ok && result.treeMatch,
  tree_match: result.treeMatch,
  problems: result.problems,
  pr_bundle: prBundle,
  collected_at: new Date().toISOString(),
};
const out = { ...body, signature: env.FACTORY_EVIDENCE_KEY ? sign(body, env.FACTORY_EVIDENCE_KEY) : null };
fs.writeFileSync('main-bundle.json', JSON.stringify(out, null, 2));

let bundleUri = null;
if (env.FACTORY_EVIDENCE_S3_URI) {
  bundleUri = `${env.FACTORY_EVIDENCE_S3_URI}/${new Date().toISOString().slice(0, 7)}/${sha}.json`;
  sh('aws', ['s3', 'cp', 'main-bundle.json', bundleUri]);
  console.log(`Stored ${bundleUri}`);
}
// For the evidence index; the workflow runs it when a database is configured.
fs.writeFileSync('index.sql', indexSql(body, repo, bundleUri || `${env.GITHUB_SERVER_URL || 'https://github.com'}/${repo}/actions/runs/${env.GITHUB_RUN_ID}`));

const lines = [
  `### Evidence for ${sha.slice(0, 12)}`,
  '',
  pr?.number ? `From PR #${pr.number} (head ${pr.head.slice(0, 12)}).` : 'No PR found for this commit.',
  `Tree match with the verified commit: ${result.treeMatch ? 'yes' : 'no'}.`,
  ...(result.problems.length ? ['', ...result.problems.map((p) => `- ${p}`)] : []),
];
if (env.GITHUB_STEP_SUMMARY) fs.appendFileSync(env.GITHUB_STEP_SUMMARY, lines.join('\n') + '\n');
console.log(lines.join('\n'));
if (!result.treeMatch && result.ok) {
  console.log('::warning::main differs from the commit the PR verified; the full checks should run again on main.');
}
if (!result.ok) {
  console.log(`::error::${result.problems.join('; ')}`);
  process.exit(1);
}
