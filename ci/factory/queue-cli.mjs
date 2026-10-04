#!/usr/bin/env node
// Merge queue controller, run by .github/workflows/queue.yml. Reads open PRs
// and the merge queue, picks what to enqueue (queue.mjs) and enqueues it.
// Env: GITHUB_REPOSITORY, GH_TOKEN (the factory App's token, so the
// merge_group run starts; GITHUB_TOKEN events don't start workflows).
import { execFileSync } from 'node:child_process';
import { selectToEnqueue, isRuleChange } from './queue.mjs';
import { loadPolicy } from './lib/policy.mjs';

const [owner, name] = (process.env.GITHUB_REPOSITORY || '').split('/');
const gql = (query, vars = {}) => JSON.parse(execFileSync('gh', ['api', 'graphql', '-f', `query=${query}`,
  ...Object.entries(vars).flatMap(([k, v]) => [typeof v === 'string' ? '-f' : '-F', `${k}=${v}`])], { encoding: 'utf8' }));

const data = gql(`query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: OPEN, first: 100) { nodes {
      id number createdAt isInMergeQueue author { login }
      labels(first: 20) { nodes { name } }
      files(first: 100) { nodes { path } }
      commits(last: 1) { nodes { commit { checkSuites(first: 20) { nodes {
        checkRuns(first: 20, filterBy: { checkName: "factory/admission" }) { nodes { conclusion } } } } } } }
    } }
    mergeQueue(branch: "main") { entries(first: 100) { nodes { pullRequest {
      number author { login } files(first: 100) { nodes { path } } } } } }
  } }`, { owner, name }).data.repository;

const policy = loadPolicy('queue');
const agents = loadPolicy('agents').agents;
const candidates = data.pullRequests.nodes.map((pr) => ({
  id: pr.id,
  number: pr.number,
  author: pr.author?.login,
  labels: pr.labels.nodes.map((l) => l.name),
  files: pr.files.nodes.map((f) => f.path),
  readyAt: pr.createdAt,
  inQueue: pr.isInMergeQueue,
  admitted: pr.commits.nodes[0]?.commit.checkSuites.nodes.some((s) => s.checkRuns.nodes.some((r) => r.conclusion === 'SUCCESS')) || false,
}));
const queue = (data.mergeQueue?.entries.nodes || []).map((e) => {
  const pr = { number: e.pullRequest.number, author: e.pullRequest.author?.login, files: e.pullRequest.files.nodes.map((f) => f.path) };
  return { ...pr, ruleChange: isRuleChange(pr, policy) };
});

const { picks, waiting } = selectToEnqueue({
  candidates,
  queue,
  policy,
  agentAccounts: agents.map((a) => a.account),
  agentLimits: Object.fromEntries(agents.map((a) => [a.account, a.max_queue_entries_per_hour])),
});
for (const w of waiting) console.log(`#${w.number} waits: ${w.reason}`);
const dry = process.env.FACTORY_DRY_RUN === 'true';
for (const p of picks) {
  if (dry) { console.log(`#${p.number} would be enqueued as ${p.priority}`); continue; }
  const id = candidates.find((c) => c.number === p.number).id;
  gql(`mutation($id: ID!, $jump: Boolean!) { enqueuePullRequest(input: { pullRequestId: $id, jump: $jump }) { mergeQueueEntry { position } } }`, { id, jump: p.jump });
  console.log(`#${p.number} enqueued as ${p.priority}${p.jump ? ' (front of the queue)' : ''}`);
}
if (!picks.length && !waiting.length) console.log('Nothing ready.');
