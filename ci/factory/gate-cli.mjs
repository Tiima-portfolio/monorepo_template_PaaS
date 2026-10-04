#!/usr/bin/env node
// Factory gate, run by .github/workflows/factory.yml.
//
// Works out the PR's boundary, risk tier and required evidence, records the
// gate's own evidence, and writes the toolchain setup for the verify job.
//
// Env: FACTORY_BASE, FACTORY_HEAD (commits to compare), FACTORY_SHA (commit
// the evidence is for), FACTORY_OUT (output dir), GITHUB_EVENT_NAME,
// GITHUB_EVENT_PATH, FACTORY_OVERRIDE_OK ("true" when a factory owner added
// the override label).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import YAML from 'yaml';
import { checkBoundary } from './boundary.mjs';
import { classify, testOnly } from './risk.mjs';
import { requiredEvidence } from './evidence.mjs';
import { checkTitle, checkHistory, checkProvenance } from './checks.mjs';
import { loadPolicy } from './lib/policy.mjs';
import { miseToml } from './lib/mise.mjs';
import { route } from './owners.mjs';
import { activeQuarantine } from './flaky.mjs';
import { checkDependencies } from './deps.mjs';
import { lintTestFile } from './test-quality.mjs';
import { contractProblems } from './contracts.mjs';
import { agentGuardrails, ownerChecks } from './guardrails.mjs';

const env = process.env;
const out = env.FACTORY_OUT || 'factory-out';
const base = env.FACTORY_BASE;
const head = env.FACTORY_HEAD || 'HEAD';
const sha = env.FACTORY_SHA || head;
const eventName = env.GITHUB_EVENT_NAME || 'pull_request';
const event = env.GITHUB_EVENT_PATH ? JSON.parse(fs.readFileSync(env.GITHUB_EVENT_PATH, 'utf8')) : {};
const pr = event.pull_request || {};

const git = (...args) => execFileSync('git', args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }).trim();
const lines = (s) => (s ? s.split('\n').filter(Boolean) : []);

fs.mkdirSync(path.join(out, 'evidence'), { recursive: true });
const records = [];
const record = (check, ok, details) => {
  const r = { check, status: ok ? 'pass' : 'fail', sha, details };
  records.push(r);
  fs.writeFileSync(path.join(out, 'evidence', `${check}.json`), JSON.stringify(r, null, 2));
};

const files = lines(git('diff', '--name-only', `${base}...${head}`));
const commits = lines(git('log', '--format=%H %P', `${base}..${head}`)).map((l) => {
  const [c, ...parents] = l.split(' ');
  return { sha: c, parents, message: git('log', '-1', '--format=%B', c) };
});

// Affected projects, their criticality and toolchains, from the Nx graph.
function affected() {
  try {
    const names = JSON.parse(execFileSync('npx', ['nx', 'show', 'projects', '--affected', `--base=${base}`, `--head=${head}`, '--json'], { encoding: 'utf8' }));
    const graphFile = path.join(out, 'graph.json');
    execFileSync('npx', ['nx', 'graph', `--file=${graphFile}`], { stdio: 'ignore' });
    const graph = JSON.parse(fs.readFileSync(graphFile, 'utf8')).graph;
    const nodes = graph.nodes;
    const tags = names.flatMap((n) => nodes[n]?.data?.tags || []);
    const pick = (prefix) => [...new Set(tags.filter((t) => t.startsWith(prefix)).map((t) => t.slice(prefix.length)))];
    return { names, nodes, graph, criticalities: pick('criticality:'), toolchains: pick('toolchain:') };
  } catch (e) {
    console.error(`Could not read the Nx graph: ${e.message}`);
    return { names: [], nodes: {}, criticalities: [], toolchains: [], error: true };
  }
}

const isPR = eventName === 'pull_request';
const policyOverrideLabel = loadPolicy('boundaries').override.label;
const override = isPR && (pr.labels || []).some((l) => l.name === policyOverrideLabel) && env.FACTORY_OVERRIDE_OK === 'true';

// PR-level checks. In the merge queue a group spans several PRs, each already
// checked on its own, so these are carried as passed.
let boundary = { ok: true, boundary: null, message: 'Checked on each PR' };
let title = { ok: true, bump: 'none', message: 'Checked on each PR' };
let provenance = { ok: true, needsHuman: false, raise: [], message: 'Checked on each PR' };
if (isPR) {
  boundary = checkBoundary(files, loadPolicy('boundaries'), { override });
  title = checkTitle(pr.title);
}
const history = checkHistory(commits);

const aff = affected();
const testsRemoved = commits.length > 0 && lines(git('diff', '--diff-filter=D', '--name-only', `${base}...${head}`)).some((f) => testOnly([f]));
let risk = classify({
  files,
  affectedProjects: aff.names.length,
  criticalities: aff.criticalities,
  override: boundary.override,
  majorBump: title.bump === 'major',
});
// Services this PR changes, read from the base branch (owners, guardrails) and
// from the PR (a new owner), for approval routing.
const show = (ref, file) => { try { return YAML.parse(git('show', `${ref}:${file}`)); } catch { return null; } };
const touched = Object.values(aff.nodes || {})
  .filter((n) => files.some((f) => f.startsWith(`${n.data.root}/`)) && fs.existsSync(path.join(n.data.root, 'service.yaml')))
  .map((n) => {
    const root = n.data.root;
    const baseService = show(base, `${root}/service.yaml`);
    return {
      name: n.name,
      root,
      boundary: root.split('/')[0],
      base: baseService ? { service: baseService, guardrails: show(base, `${root}/guardrails.yaml`) || {} } : null,
      head: { service: YAML.parse(fs.readFileSync(path.join(root, 'service.yaml'), 'utf8')) },
    };
  });
let routing = { approvals: [], raise: [], owningTeams: [] };
if (isPR) {
  provenance = checkProvenance({ author: pr.user?.login, commits, files, boundary: boundary.boundary, tier: risk.tier });
  routing = route({ services: touched, files, author: pr.user?.login, tier: risk.tier, teams: loadPolicy('teams') });
  const quarantineFile = env.FACTORY_QUARANTINE_FILE;
  const quarantined = quarantineFile && fs.existsSync(quarantineFile) ? activeQuarantine(JSON.parse(fs.readFileSync(quarantineFile, 'utf8'))) : new Set();
  const inQuarantine = aff.names.filter((n) => quarantined.has(n));
  const raise = [...provenance.raise, ...routing.raise, ...(inQuarantine.length ? ['quarantined_tests'] : [])];
  if (raise.length) {
    risk = classify({ files, affectedProjects: aff.names.length, criticalities: aff.criticalities, override: boundary.override, majorBump: title.bump === 'major', raise });
  }
}
const requester = commits.map((c) => /^Requested-By:\s*(\S+)/m.exec(c.message)?.[1]).find(Boolean) || null;

record('boundary', boundary.ok, boundary.message);
record('title', title.ok, title.message);
record('history', history.ok, history.message);
record('provenance', provenance.ok, provenance.message);
{
  const problems = files.filter((f) => fs.existsSync(f)).flatMap((f) => lintTestFile(f, fs.readFileSync(f, 'utf8')));
  record('test-quality', problems.length === 0, problems.length ? problems.join('; ') : 'no skipped or assertion-free tests in changed files');
}
if (aff.nodes) {
  // Contract coverage for the affected projects that are services.
  const services = aff.names
    .map((n) => aff.nodes[n]?.data?.root)
    .filter((root) => root && fs.existsSync(path.join(root, 'service.yaml')))
    .map((root) => ({
      name: path.basename(root),
      root,
      service: YAML.parse(fs.readFileSync(path.join(root, 'service.yaml'), 'utf8')) || {},
      files: lines(git('ls-files', '--', root)).map((f) => f.slice(root.length + 1)),
    }));
  const problems = contractProblems(services);
  record('contract-tests', problems.length === 0, problems.length ? problems.join('; ') : services.length ? 'declared contracts exist and every consumes edge has a contract test' : 'no affected services');
}
if (aff.graph) {
  const problems = checkDependencies(aff.graph);
  record('dependency-rules', problems.length === 0, problems.length ? problems.join('; ') : 'dependency directions and no cycles');
}

// With nothing affected the verify job doesn't run; say so in the evidence.
if (aff.names.length === 0 && !aff.error) {
  for (const check of ['format-lint', 'build', 'unit-tests']) {
    const r = { check, status: 'skipped', sha, details: 'nothing affected' };
    records.push(r);
    fs.writeFileSync(path.join(out, 'evidence', `${check}.json`), JSON.stringify(r, null, 2));
  }
}

// Owners' required checks, and their rules for agents.
const checks = ownerChecks(touched, files);
if (isPR && provenance.isAgent) {
  const g = agentGuardrails(touched, files, risk.tier);
  if (!g.ok) provenance = { ...provenance, ok: false, message: `${provenance.message}; ${g.problems.join('; ')}` };
  if (g.needsHuman) provenance = { ...provenance, needsHuman: true };
  record('provenance', provenance.ok, provenance.message);
}
const escapeFix = isPR && (pr.labels || []).some((l) => l.name === 'escape-fix');
const required = requiredEvidence(risk.tier, { agent: provenance.isAgent, testsRemoved, escapeFix, ownerChecks: checks.length > 0 });

// mise config for the toolchains the affected projects use.
const tools = {};
for (const tc of aff.toolchains) {
  const file = path.join('internal-tools/toolchains', tc, 'toolchain.yaml');
  if (fs.existsSync(file)) Object.assign(tools, YAML.parse(fs.readFileSync(file, 'utf8'))?.setup?.mise || {});
}
fs.writeFileSync(path.join(out, 'mise.toml'), miseToml(tools));

const gate = {
  sha, tree: git('rev-parse', `${head}^{tree}`), base, head, event: eventName, tier: risk.tier, reasons: risk.reasons, boundary: boundary.boundary,
  override: !!boundary.override, needsHuman: provenance.needsHuman, affected: aff.names,
  toolchains: aff.toolchains, files: files.length, required,
  author: pr.user?.login || null, requester, ownerChecks: checks, approvals: routing.approvals, owningTeams: routing.owningTeams,
};
fs.writeFileSync(path.join(out, 'gate.json'), JSON.stringify(gate, null, 2));

const summary = [
  `### Factory gate`,
  '',
  `Tier **${risk.tier}** (${risk.reasons.join('; ') || 'default'}). ${files.length} changed file(s), ${aff.names.length} affected project(s).`,
  '',
  ...records.map((r) => `- ${r.status === 'pass' ? '✅' : '❌'} ${r.check}: ${r.details}`),
  ...(routing.approvals.length ? ['', 'Approvals needed:', ...routing.approvals.map((a) => `- ${a.service}: ${a.teams.join(' or ')} (${a.reason})`)] : []),
].join('\n');
if (env.GITHUB_STEP_SUMMARY) fs.appendFileSync(env.GITHUB_STEP_SUMMARY, summary + '\n');
console.log(summary);

if (env.GITHUB_OUTPUT) {
  fs.appendFileSync(env.GITHUB_OUTPUT, `tier=${risk.tier}\naffected=${aff.names.length}\nhas_tools=${Object.keys(tools).length > 0}\nescape_fix=${escapeFix}\nhard_minutes=${loadPolicy('budgets').feedback[risk.tier].hard}\nowner_checks=${checks.map((c) => `${c.project}:${c.target}`).join(' ')}\n`);
}
// The gate never fails the job itself: admission decides, so the PR shows one
// clear verdict with every reason in it.
