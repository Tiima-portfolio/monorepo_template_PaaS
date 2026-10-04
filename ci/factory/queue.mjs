// Merge queue controller: which ready PRs to enqueue now, in what order.
import { matchesAny } from './lib/glob.mjs';

const RANK = { P0: 0, P1: 1, P2: 2, P3: 3, P4: 4 };

export function priorityOf(pr, policy, agentAccounts) {
  const label = (pr.labels || []).find((l) => /^P[0-4]$/.test(l));
  if (label) return label;
  return agentAccounts.includes(pr.author) ? policy.default_priority.agent : policy.default_priority.human;
}

export const isRuleChange = (pr, policy) => (pr.files || []).some((f) => matchesAny(f, policy.rule_change_paths));

// candidates: [{ number, author, labels, files, readyAt, admitted, inQueue }]
// queue: [{ number, ruleChange }] current merge queue entries.
// agentLimits: { account: maxEntriesInQueue }.
// Returns [{ number, priority, jump }] to enqueue, and why the others wait.
export function selectToEnqueue({ candidates, queue, policy, agentAccounts = [], agentLimits = {} }) {
  const waiting = [];
  const picks = [];
  const ready = candidates
    .filter((pr) => pr.labels.includes(policy.ready_label) && pr.admitted && !pr.inQueue)
    .map((pr) => ({ ...pr, priority: priorityOf(pr, policy, agentAccounts), ruleChange: isRuleChange(pr, policy) }))
    .sort((a, b) => RANK[a.priority] - RANK[b.priority] || a.readyAt.localeCompare(b.readyAt));

  // A rule change in the queue holds everything else until it has merged.
  if (queue.some((e) => e.ruleChange)) {
    return { picks, waiting: ready.map((pr) => ({ number: pr.number, reason: 'a rule change is merging alone' })) };
  }
  let depth = queue.length;
  const perAgent = {};
  for (const e of queue) if (e.author) perAgent[e.author] = (perAgent[e.author] || 0) + 1;

  for (const pr of ready) {
    if (pr.ruleChange) {
      if (depth === 0 && picks.length === 0) {
        picks.push({ number: pr.number, priority: pr.priority, jump: pr.priority === 'P0' });
        depth++;
        // Nothing else enters with it.
        for (const rest of ready.filter((x) => x.number !== pr.number)) waiting.push({ number: rest.number, reason: 'a rule change is merging alone' });
        return { picks, waiting };
      }
      waiting.push({ number: pr.number, reason: 'rule change waits for an empty queue' });
      continue;
    }
    if (pr.priority !== 'P0' && depth >= policy.max_depth) {
      waiting.push({ number: pr.number, reason: `queue is full (${depth})` });
      continue;
    }
    const holdAt = policy.hold_at_depth[pr.priority];
    if (holdAt !== undefined && depth >= holdAt) {
      waiting.push({ number: pr.number, reason: `backpressure: ${pr.priority} waits at depth ${depth}` });
      continue;
    }
    const limit = agentLimits[pr.author];
    if (limit !== undefined && (perAgent[pr.author] || 0) >= limit) {
      waiting.push({ number: pr.number, reason: `agent ${pr.author} has ${limit} entries queued` });
      continue;
    }
    picks.push({ number: pr.number, priority: pr.priority, jump: pr.priority === 'P0' });
    perAgent[pr.author] = (perAgent[pr.author] || 0) + 1;
    depth++;
  }
  return { picks, waiting };
}
