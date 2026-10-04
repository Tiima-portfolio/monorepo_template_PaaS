#!/usr/bin/env node
// Keeps the repository rulesets equal to the files in .github/rulesets/.
//
//   node ci/factory/rulesets.mjs check   # report drift, exit 1 if any
//   node ci/factory/rulesets.mjs apply   # create or update to match the files
//
// Needs gh with a token that can administer the repository for "apply".
// Env: GITHUB_REPOSITORY, FACTORY_RULESETS (default: all files).
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const DIR = '.github/rulesets';
const repo = process.env.GITHUB_REPOSITORY || execFileSync('gh', ['repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner'], { encoding: 'utf8' }).trim();
const api = (args, input) => execFileSync('gh', ['api', ...args], { encoding: 'utf8', input, stdio: [input ? 'pipe' : 'ignore', 'pipe', 'pipe'] });

// The fields that make up a ruleset's behaviour, in a stable order.
export function normalize(r) {
  const sortKeys = (v) => (Array.isArray(v) ? v.map(sortKeys) : v && typeof v === 'object'
    ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, sortKeys(v[k])])) : v);
  const rules = [...(r.rules || [])].map((x) => ({ type: x.type, parameters: x.parameters || {} })).sort((a, b) => a.type.localeCompare(b.type));
  const bypass = [...(r.bypass_actors || [])].map(({ actor_id, actor_type, bypass_mode }) => ({ actor_id, actor_type, bypass_mode }))
    .sort((a, b) => `${a.actor_type}${a.actor_id}`.localeCompare(`${b.actor_type}${b.actor_id}`));
  return sortKeys({ name: r.name, target: r.target, enforcement: r.enforcement, conditions: r.conditions, bypass_actors: bypass, rules });
}

export function diff(want, have) {
  if (!have) return ['missing'];
  const a = normalize(want);
  const b = normalize(have);
  return Object.keys(a).filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]));
}

function main(mode) {
  const files = fs.readdirSync(DIR).filter((f) => f.endsWith('.json'));
  const live = JSON.parse(api([`repos/${repo}/rulesets`, '--paginate']) || '[]');
  let drift = 0;
  for (const f of files) {
    const want = JSON.parse(fs.readFileSync(path.join(DIR, f), 'utf8'));
    const summary = live.find((r) => r.name === want.name);
    const have = summary ? JSON.parse(api([`repos/${repo}/rulesets/${summary.id}`])) : null;
    const changed = diff(want, have);
    if (!changed.length) {
      console.log(`${want.name}: matches ${f}`);
      continue;
    }
    drift++;
    console.log(`${want.name}: differs from ${f} (${changed.join(', ')})`);
    if (mode === 'apply') {
      const body = JSON.stringify(want);
      if (have) api(['-X', 'PUT', `repos/${repo}/rulesets/${have.id}`, '--input', '-'], body);
      else api(['-X', 'POST', `repos/${repo}/rulesets`, '--input', '-'], body);
      console.log(`${want.name}: ${have ? 'updated' : 'created'}`);
    }
  }
  if (mode === 'check' && drift) {
    console.log(`::warning::${drift} ruleset(s) differ from .github/rulesets/. Run: node ci/factory/rulesets.mjs apply`);
    process.exit(1);
  }
}

if (process.argv[1]?.endsWith('rulesets.mjs')) main(process.argv[2] || 'check');
