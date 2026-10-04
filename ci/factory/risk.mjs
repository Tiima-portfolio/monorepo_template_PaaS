// Risk tier classifier: sets R0 to R3 for a PR from policy in risk.yaml.
import { matchesAny } from './lib/glob.mjs';
import { loadPolicy } from './lib/policy.mjs';

export const TIERS = ['R0', 'R1', 'R2', 'R3'];
const rank = (t) => TIERS.indexOf(t);
const max = (a, b) => (rank(a) >= rank(b) ? a : b);

export function fileTier(file, policy) {
  for (const tier of ['R3', 'R2', 'R0']) {
    if (matchesAny(file, policy.paths[tier] || [])) return tier;
  }
  return 'R1'; // test files and everything else
}

// input: { files, affectedProjects, criticalities, override, majorBump, raise: [names] }
export function classify(input, policy = loadPolicy('risk')) {
  const reasons = [];
  let tier = 'R0';
  for (const f of input.files || []) {
    const t = fileTier(f, policy);
    if (rank(t) > rank(tier)) reasons.push(`${f} is ${t}`);
    tier = max(tier, t);
  }
  if (!(input.files || []).length) reasons.push('no changed files');

  const r2 = policy.at_least.R2;
  if ((input.affectedProjects || 0) > r2.affected_projects_over) {
    tier = max(tier, 'R2');
    reasons.push(`${input.affectedProjects} affected projects`);
  }
  const critical = (input.criticalities || []).filter((c) => r2.criticality.includes(c));
  if (critical.length) {
    tier = max(tier, 'R2');
    reasons.push('affects a critical project');
  }
  const r3 = policy.at_least.R3;
  if (r3.boundary_override && input.override) {
    tier = 'R3';
    reasons.push('boundary override');
  }
  if (r3.major_bump && input.majorBump) {
    tier = 'R3';
    reasons.push('major version bump');
  }
  for (const name of input.raise || []) {
    if (!policy.raise.includes(name)) throw new Error(`unknown raise rule: ${name}`);
    const next = TIERS[Math.min(rank(tier) + 1, 3)];
    if (next !== tier) reasons.push(`raised by ${name}`);
    tier = next;
  }
  return { tier, reasons };
}

// True when the PR changes only test files (they are R1, never R0).
export function testOnly(files, policy = loadPolicy('risk')) {
  return files.length > 0 && files.every((f) => matchesAny(f, policy.test_paths));
}
