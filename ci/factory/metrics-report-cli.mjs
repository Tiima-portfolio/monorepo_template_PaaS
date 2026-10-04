#!/usr/bin/env node
// Fetches last week's PRs, issues and factory runs and prints the report.
// Env: GITHUB_REPOSITORY, GH_TOKEN, FACTORY_METRICS_DAYS (default 7).
import { execFileSync } from 'node:child_process';
import { report } from './metrics-report.mjs';
import { loadPolicy } from './lib/policy.mjs';

const repo = process.env.GITHUB_REPOSITORY;
const days = Number(process.env.FACTORY_METRICS_DAYS || 7);
const until = new Date().toISOString();
const since = new Date(Date.now() - days * 86400000).toISOString();
const gh = (...a) => JSON.parse(execFileSync('gh', a, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }) || '[]');

const prs = gh('pr', 'list', '--repo', repo, '--state', 'merged', '--limit', '1000', '--search', `merged:>=${since.slice(0, 10)}`,
  '--json', 'number,author,createdAt,mergedAt,labels,body')
  .map((p) => ({ ...p, author: p.author?.login, labels: p.labels.map((l) => l.name) }));
const issues = gh('issue', 'list', '--repo', repo, '--state', 'all', '--limit', '1000', '--json', 'title,labels,createdAt,closedAt,state')
  .map((i) => ({ ...i, state: i.state.toLowerCase(), labels: i.labels.map((l) => l.name) }));
const runs = gh('run', 'list', '--repo', repo, '--workflow', 'factory.yml', '--event', 'pull_request', '--created', `>=${since.slice(0, 10)}`,
  '--limit', '1000', '--json', 'conclusion');
const agents = loadPolicy('agents').agents.map((a) => a.account.replace(/\[bot\]$/, ''));
process.stdout.write(report({ prs, issues, runs, agents: [...agents, 'app/tiima-factory'], since, until }) + '\n');
