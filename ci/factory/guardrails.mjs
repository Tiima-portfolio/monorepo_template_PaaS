// Owner guardrails from each touched service's guardrails.yaml (base branch):
// required owner checks to run, and the rules for agents.
import { matchesAny } from './lib/glob.mjs';
import { TIERS } from './risk.mjs';

// services: [{ name, root, base: { guardrails } | null }]; files: changed paths.
export function ownerChecks(services, files) {
  const checks = [];
  for (const s of services) {
    const own = files.filter((f) => f.startsWith(`${s.root}/`)).map((f) => f.slice(s.root.length + 1));
    for (const c of s.base?.guardrails?.required_checks || []) {
      if (own.some((f) => matchesAny(f, c.when || ['**']))) checks.push({ project: s.name, target: c.target, budget: c.budget || null });
    }
  }
  return checks;
}

// Agent rules: forbidden paths block; a tier above max_autonomous_tier needs a human.
export function agentGuardrails(services, files, tier) {
  const problems = [];
  let needsHuman = false;
  for (const s of services) {
    const g = s.base?.guardrails?.agents || {};
    const own = files.filter((f) => f.startsWith(`${s.root}/`)).map((f) => f.slice(s.root.length + 1));
    if (!own.length) continue;
    const forbidden = own.filter((f) => matchesAny(f, g.forbidden_paths || []));
    if (forbidden.length) problems.push(`${s.name}'s owner doesn't allow agents to change ${forbidden.join(', ')}`);
    if (g.max_autonomous_tier && TIERS.indexOf(tier) > TIERS.indexOf(g.max_autonomous_tier)) needsHuman = true;
  }
  return { ok: problems.length === 0, problems, needsHuman };
}
