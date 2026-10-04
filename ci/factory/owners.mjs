// Approval routing: who must approve a PR, per service it touches, from each
// service's service.yaml and guardrails.yaml on the base branch.
import { matchesAny } from './lib/glob.mjs';
import { TIERS } from './risk.mjs';

// services: [{ name, root, boundary, base: { service, guardrails } | null,
//              head: { service } }]  (base null = new service)
// files: changed paths. author: login. tier: the PR's risk tier.
export function route({ services, files, author, tier, teams }) {
  const teamsOf = (login) => Object.entries(teams.teams).filter(([, m]) => m.includes(login)).map(([t]) => t);
  const authorTeams = teamsOf(author);
  const approvals = [];
  const raise = new Set();
  const owningTeams = new Set();

  for (const s of services) {
    const own = files.filter((f) => f.startsWith(`${s.root}/`)).map((f) => f.slice(s.root.length + 1));
    if (!own.length) continue;
    if (!s.base) {
      approvals.push({ service: s.name, teams: teams.catalog_approvers[s.boundary] || ['factory-owners'], reason: 'new service' });
      if (s.head?.service?.owner) approvals.push({ service: s.name, teams: [s.head.service.owner], reason: 'named as owner of the new service' });
      continue;
    }
    const owner = s.base.service.owner;
    owningTeams.add(owner);
    const g = s.base.guardrails || {};
    const newOwner = s.head?.service?.owner;
    if (newOwner && newOwner !== owner) {
      approvals.push({ service: s.name, teams: [owner], reason: `owner change from ${owner}` });
      approvals.push({ service: s.name, teams: [newOwner], reason: `owner change to ${newOwner}` });
      continue;
    }
    const protectedHit = own.some((f) => matchesAny(f, g.protected_paths || []));
    if (protectedHit) raise.add('protected_path');
    const contract = (s.base.service.contract || []);
    const contractHit = own.some((f) => contract.includes(f) || matchesAny(f, contract));
    const guardrailsHit = own.includes('guardrails.yaml');
    const risky = protectedHit || contractHit || guardrailsHit || TIERS.indexOf(tier) >= 2 || own.some((f) => /(^|\/)migrations\//.test(f));
    const contributors = g.contributors || [];
    if (risky) {
      approvals.push({ service: s.name, teams: [owner], reason: protectedHit ? 'protected path' : contractHit ? 'contract change' : guardrailsHit ? 'guardrails change' : `risk tier ${tier}` });
    } else if (authorTeams.includes(owner)) {
      approvals.push({ service: s.name, teams: [owner], reason: 'owning team' });
    } else if (authorTeams.some((t) => contributors.includes(t))) {
      approvals.push({ service: s.name, teams: authorTeams.filter((t) => contributors.includes(t)), reason: 'listed contributor; owner notified', notify: owner });
    } else {
      approvals.push({ service: s.name, teams: [owner], reason: 'contributor not listed in guardrails.yaml' });
    }
  }
  if (owningTeams.size > 3) raise.add('owning_teams_over_3');
  return { approvals, raise: [...raise], owningTeams: [...owningTeams] };
}

// approvers: logins whose latest review is APPROVED. Never the author or requester.
export function approvalsMet(approvals, approvers, { author, requester, teams }) {
  const valid = approvers.filter((a) => a !== author && a !== requester);
  const members = (team) => teams.teams[team] || [];
  const missing = approvals.filter((req) => !req.teams.some((t) => members(t).some((m) => valid.includes(m))));
  return { ok: missing.length === 0, missing };
}
