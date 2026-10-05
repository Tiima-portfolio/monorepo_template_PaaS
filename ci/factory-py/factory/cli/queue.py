"""Merge queue controller, run by .github/workflows/queue.yml. Reads open PRs
and the merge queue, picks what to enqueue and enqueues it.

Env: GITHUB_REPOSITORY, GH_TOKEN (the factory App's token, so the
merge_group run starts; GITHUB_TOKEN events don't start workflows).
"""

import json

from ..policy import load_policy
from ..queue import is_rule_change, select_to_enqueue
from .common import env, run

QUERY = """query($owner: String!, $name: String!) {
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
  } }"""
ENQUEUE = "mutation($id: ID!, $jump: Boolean!) { enqueuePullRequest(input: { pullRequestId: $id, jump: $jump }) { mergeQueueEntry { position } } }"


def gql(query, **variables):
    args = []
    for k, v in variables.items():
        args += ["-f" if isinstance(v, str) else "-F", f"{k}={json.dumps(v) if isinstance(v, bool) else v}"]
    return json.loads(run("gh", "api", "graphql", "-f", f"query={query}", *args))


def admitted(pr) -> bool:
    commit = (pr["commits"]["nodes"] or [{}])[0].get("commit")
    return bool(commit) and any(r["conclusion"] == "SUCCESS" for s in commit["checkSuites"]["nodes"] for r in s["checkRuns"]["nodes"])


def main(argv):
    owner, _, name = (env.get("GITHUB_REPOSITORY") or "").partition("/")
    data = gql(QUERY, owner=owner, name=name)["data"]["repository"]
    policy = load_policy("queue")
    agents = load_policy("agents")["agents"]
    candidates = [{
        "id": pr["id"], "number": pr["number"], "author": (pr.get("author") or {}).get("login"),
        "labels": [l["name"] for l in pr["labels"]["nodes"]], "files": [f["path"] for f in pr["files"]["nodes"]],
        "readyAt": pr["createdAt"], "inQueue": pr["isInMergeQueue"], "admitted": admitted(pr),
    } for pr in data["pullRequests"]["nodes"]]
    queue = []
    for e in ((data.get("mergeQueue") or {}).get("entries") or {}).get("nodes") or []:
        p = e["pullRequest"]
        entry = {"number": p["number"], "author": (p.get("author") or {}).get("login"), "files": [f["path"] for f in p["files"]["nodes"]]}
        queue.append({**entry, "ruleChange": is_rule_change(entry, policy)})

    result = select_to_enqueue(candidates, queue, policy, agent_accounts=[a["account"] for a in agents],
                               agent_limits={a["account"]: a.get("max_queue_entries_per_hour") for a in agents})
    for w in result["waiting"]:
        print(f"#{w['number']} waits: {w['reason']}")
    dry = env.get("FACTORY_DRY_RUN") == "true"
    for p in result["picks"]:
        if dry:
            print(f"#{p['number']} would be enqueued as {p['priority']}")
            continue
        pr_id = next(c["id"] for c in candidates if c["number"] == p["number"])
        gql(ENQUEUE, id=pr_id, jump=p["jump"])
        print(f"#{p['number']} enqueued as {p['priority']}{' (front of the queue)' if p['jump'] else ''}")
    if not result["picks"] and not result["waiting"]:
        print("Nothing ready.")
