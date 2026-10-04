// Agent backpressure: an agent may have at most max_open_prs open PRs, and its
// sponsoring team at most review_budget agent PRs waiting for review.
//
// openPrs: [{ number, author, reviewDecision }] (open PRs in the repo).
export function agentBackpressure({ agent, openPrs, agents, teams, current }) {
  const problems = [];
  const mine = openPrs.filter((p) => p.author === agent.login && p.number !== current);
  if (mine.length >= agent.max_open_prs) {
    problems.push(`${agent.id} already has ${mine.length} open PRs (limit ${agent.max_open_prs}); finish or close some first`);
  }
  const sponsored = agents.filter((a) => a.sponsor === agent.sponsor).map((a) => a.login);
  const waiting = openPrs.filter((p) => sponsored.includes(p.author) && p.number !== current && p.reviewDecision !== 'APPROVED');
  const budget = teams.review_budget?.[agent.sponsor] ?? teams.review_budget?.default ?? 10;
  if (waiting.length >= budget) {
    problems.push(`${agent.sponsor} has ${waiting.length} agent PRs waiting for review (budget ${budget}); this one waits too`);
  }
  return problems;
}
