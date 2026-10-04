#!/usr/bin/env node
// Promotion bot, run by the release workflow after releases with the factory
// App's token. For every pins.yaml whose consumer pins an older version of a
// service released in this run, it opens one bump PR, labelled ready and P4,
// so the queue controller merges it once the consumer's own checks pass.
// Promotion of a service with an open escape issue is on hold.
//
// Env: GITHUB_REPOSITORY, GH_TOKEN. Reads released.json.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import YAML from 'yaml';
import { planPromotions } from './promote.mjs';

const repo = process.env.GITHUB_REPOSITORY;
const sh = (cmd, args) => (execFileSync(cmd, args, { encoding: 'utf8' }) || '').trim();
const git = (...a) => sh('git', a);
const released = fs.existsSync('released.json') ? JSON.parse(fs.readFileSync('released.json', 'utf8')) : [];
if (!released.length) {
  console.log('Nothing released; nothing to promote.');
  process.exit(0);
}

const pinsFiles = git('ls-files', '*pins.yaml').split('\n').filter((f) => f.endsWith('/pins.yaml'))
  .map((p) => ({ path: p, pins: YAML.parse(fs.readFileSync(p, 'utf8'))?.pins || {} }));
// Open escape issues name the service in brackets, e.g. "escape: [orders] ...".
const escapes = JSON.parse(sh('gh', ['api', `repos/${repo}/issues?labels=escape&state=open&per_page=100`, '--jq', '[.[].title]']) || '[]');
const holds = released.map((r) => r.service).filter((s) => escapes.some((t) => t.includes(`[${s}]`)));
for (const s of holds) console.log(`::warning::Promotion of ${s} is on hold: it has an open escape.`);

const start = git('rev-parse', 'HEAD');
for (const b of planPromotions(pinsFiles, released, holds)) {
  const consumer = path.dirname(b.path);
  const branch = `promote/${consumer.replace(/\//g, '-')}-${b.service}-${b.to}`;
  if (sh('git', ['ls-remote', '--heads', 'origin', branch])) {
    console.log(`${branch} already exists`);
    continue;
  }
  git('checkout', '-q', '-B', branch, start);
  const doc = YAML.parseDocument(fs.readFileSync(b.path, 'utf8'));
  doc.setIn(['pins', b.service], b.to);
  fs.writeFileSync(b.path, doc.toString());
  const title = `fix(${path.basename(consumer)}): promote ${b.service} to ${b.to}`;
  git('commit', '-q', '-am', `${title}\n\nPromotes: ${b.service}@${b.to}`);
  git('push', '-q', 'origin', branch);
  const url = sh('gh', ['pr', 'create', '--repo', repo, '--base', 'main', '--head', branch, '--label', 'ready', '--label', 'P4', '--title', title,
    '--body', `${b.service} released ${b.to}; ${consumer} pinned ${b.from}. This bump runs ${consumer}'s own checks and merges through the queue as P4.\n\nPromotes: ${b.service}@${b.to}`]);
  console.log(`Opened ${url}`);
}
git('checkout', '-q', start);
