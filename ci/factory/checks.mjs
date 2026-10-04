// PR title, history and agent provenance checks.
import { matchesAny } from './lib/glob.mjs';
import { loadPolicy } from './lib/policy.mjs';

const TITLE = /^(feat|fix|perf|refactor|revert|docs|test|chore|ci|build|style)(\([\w./-]+\))?(!)?: \S.*$/;
const BUMP = { feat: 'minor', fix: 'patch', perf: 'patch', refactor: 'patch', revert: 'patch' };

// Conventional PR title; the squash commit title sets the version bump.
export function checkTitle(title) {
  const m = TITLE.exec(title || '');
  if (!m) {
    return { ok: false, message: `PR title "${title}" must start with a type such as "fix:", "feat:", "feat!:", "docs:", "test:", "chore:", "ci:" or "build:".` };
  }
  const [, type, , bang] = m;
  const bump = bang ? 'major' : BUMP[type] || 'none';
  return { ok: true, type, bump, message: `Title type ${type}${bang ? '!' : ''}, version bump: ${bump}` };
}

// commits: [{ sha, parents: [sha] }]. Squash merges need no merge commits.
export function checkHistory(commits) {
  const merges = commits.filter((c) => (c.parents || []).length > 1);
  if (merges.length) {
    return { ok: false, message: `Merge commits aren't allowed; rebase instead: ${merges.map((c) => c.sha.slice(0, 7)).join(', ')}` };
  }
  return { ok: true, message: `${commits.length} commit(s), no merge commits` };
}

function trailers(message) {
  const found = {};
  for (const line of (message || '').split('\n')) {
    const m = /^([A-Za-z-]+):\s*(.+)$/.exec(line.trim());
    if (m) found[m[1]] = m[2];
  }
  return found;
}

// input: { author, commits: [{ sha, message }], files, boundary, tier }
export function checkProvenance(input, policy = loadPolicy('agents')) {
  const agent = policy.agents.find((a) => a.account === input.author);
  if (!agent) return { ok: true, isAgent: false, needsHuman: false, message: 'Human author' };

  const problems = [];
  for (const c of input.commits || []) {
    const t = trailers(c.message);
    const missing = policy.required_trailers.filter((k) => !t[k]);
    if (missing.length) problems.push(`commit ${c.sha.slice(0, 7)} lacks ${missing.join(', ')}`);
  }
  const forbidden = (input.files || []).filter((f) => matchesAny(f, policy.forbidden_paths));
  if (forbidden.length) problems.push(`agents may not change ${forbidden.join(', ')}`);
  const boundaryName = (input.boundary || '').split(':')[0];
  if (input.boundary && !agent.boundaries.includes(boundaryName)) {
    problems.push(`${agent.id} may not change the ${boundaryName} boundary`);
  }
  const level = policy.trust_levels[agent.trust];
  if (!level) problems.push(`${agent.id} has unknown trust level ${agent.trust}`);
  const needsHuman = !level || !level.merges_alone.includes(input.tier);

  return {
    ok: problems.length === 0,
    isAgent: true,
    agent: agent.id,
    trust: agent.trust,
    needsHuman,
    raise: needsHuman ? ['agent_above_trust'] : [],
    message: problems.length ? problems.join('; ') : `${agent.id} (${agent.trust}) ${needsHuman ? 'needs a human approval at ' + input.tier : 'may merge ' + input.tier + ' alone'}`,
  };
}
