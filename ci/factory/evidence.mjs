// Required evidence per tier, from evidence.yaml.
import { loadPolicy } from './lib/policy.mjs';

// Returns [{ name, mode, about }] for a tier and the PR's conditions.
export function requiredEvidence(tier, { agent = false, testsRemoved = false } = {}, policy = loadPolicy('evidence')) {
  if (!policy.tiers[tier]) throw new Error(`unknown tier: ${tier}`);
  const names = new Set(policy.tiers[tier]);
  if (agent) policy.extra.agent.forEach((n) => names.add(n));
  if (testsRemoved) policy.extra.tests_removed.forEach((n) => names.add(n));
  return [...names].map((name) => {
    const def = policy.evidence[name];
    if (!def) throw new Error(`evidence "${name}" is required but not defined`);
    return { name, mode: def.mode, about: def.about };
  });
}
