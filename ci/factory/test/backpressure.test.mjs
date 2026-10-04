import test from 'node:test';
import assert from 'node:assert/strict';
import { agentBackpressure } from '../backpressure.mjs';

const agents = [{ id: 'a', login: 'a-bot', sponsor: 'team-x', max_open_prs: 2 }, { id: 'b', login: 'b-bot', sponsor: 'team-x', max_open_prs: 5 }];
const teams = { review_budget: { 'team-x': 3, default: 10 } };
const pr = (number, author, reviewDecision = 'REVIEW_REQUIRED') => ({ number, author, reviewDecision });

test('within limits', () => {
  assert.deepEqual(agentBackpressure({ agent: agents[0], openPrs: [pr(1, 'a-bot'), pr(9, 'a-bot')], agents, teams, current: 9 }), []);
});

test('too many open PRs for the agent', () => {
  const p = agentBackpressure({ agent: agents[0], openPrs: [pr(1, 'a-bot'), pr(2, 'a-bot'), pr(9, 'a-bot')], agents, teams, current: 9 });
  assert.match(p[0], /already has 2 open PRs/);
});

test("the sponsoring team's review budget holds new agent PRs", () => {
  const open = [pr(1, 'b-bot'), pr(2, 'b-bot'), pr(3, 'a-bot'), pr(4, 'b-bot', 'APPROVED'), pr(9, 'b-bot')];
  const p = agentBackpressure({ agent: agents[1], openPrs: open, agents, teams, current: 9 });
  assert.match(p.at(-1), /3 agent PRs waiting for review \(budget 3\)/);
});
