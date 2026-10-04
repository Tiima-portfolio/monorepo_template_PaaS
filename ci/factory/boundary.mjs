// Boundary check: a PR must stay inside one boundary.
import { matchesAny } from './lib/glob.mjs';
import { loadPolicy } from './lib/policy.mjs';

// Returns the boundary key of one path, such as "product" or
// "internal-tool:internal-tools/search", or null when no rule owns it.
export function boundaryOf(file, policy) {
  for (const b of policy.boundaries) {
    if (matchesAny(file, b.paths)) {
      if (!b.per) return b.name;
      return `${b.name}:${file.split('/').slice(0, b.per).join('/')}`;
    }
  }
  return null;
}

// files: changed paths. override: true when a factory owner added the
// override label (the workflow verifies who added it).
export function checkBoundary(files, policy, { override = false } = {}) {
  const byBoundary = new Map();
  const unowned = [];
  for (const file of files) {
    const key = boundaryOf(file, policy);
    if (!key) {
      unowned.push(file);
      continue;
    }
    if (!byBoundary.has(key)) byBoundary.set(key, []);
    byBoundary.get(key).push(file);
  }
  const boundaries = [...byBoundary.keys()].sort();
  const result = { boundaries, byBoundary: Object.fromEntries(byBoundary), unowned, override: false };

  if (unowned.length) {
    return { ...result, ok: false, message: `No boundary owns these paths; add them to ci/policy/boundaries.yaml or move them:\n${unowned.map((f) => `- ${f}`).join('\n')}` };
  }
  if (boundaries.length <= 1) {
    return { ...result, ok: true, boundary: boundaries[0] || null, message: boundaries.length ? `Boundary: ${boundaries[0]}` : 'No changed files' };
  }
  if (override) {
    return { ...result, ok: true, boundary: null, override: true, message: `Cross-boundary change allowed by the ${policy.override.label} label: ${boundaries.join(', ')}. Risk tier is R3.` };
  }
  const split = boundaries.map((b) => `- ${b}: ${byBoundary.get(b).length} file(s), e.g. ${byBoundary.get(b)[0]}`).join('\n');
  return { ...result, ok: false, message: `This PR touches ${boundaries.length} boundaries. Split it into one PR per boundary:\n${split}` };
}

export function run(files, opts = {}) {
  return checkBoundary(files, opts.policy || loadPolicy('boundaries'), opts);
}
