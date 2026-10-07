"""Measures every agent against ci/policy/agents.yaml and prints what its trust
level should be.

Usage: agent-trust [--apply]   (--apply rewrites agents.yaml for demotions only;
promotions are a reviewed R3 change a human opens.)
Env: GITHUB_REPOSITORY, GH_TOKEN."""

import json
from datetime import date
from pathlib import Path

from ..policy import load_policy, policy_dir
from ..trust import apply_trust, evaluate, stats
from .common import env, run


def gh(*args):
    return json.loads(run("gh", *args) or "[]")


def main(argv):
    repo = env.get("GITHUB_REPOSITORY")
    policy = load_policy("agents")
    today = date.today()
    prs = [{**p, "author": (p.get("author") or {}).get("login"), "labels": [l["name"] for l in p["labels"]]}
           for p in gh("pr", "list", "--repo", repo, "--state", "merged", "--limit", "1000", "--json", "number,author,title,mergedAt,labels")]
    issues = [{**i, "labels": [l["name"] for l in i["labels"]]}
              for i in gh("issue", "list", "--repo", repo, "--state", "all", "--label", "escape", "--limit", "1000", "--json", "title,labels,createdAt")]
    file = Path(policy_dir()) / "agents.yaml"
    text = file.read_text()
    lines = ["### Agent trust", "", "| Agent | Level | Accepted | Escapes | Reverts | Verdict |", "| --- | --- | --- | --- | --- | --- |"]
    for agent in policy["agents"]:
        s = stats(agent, prs, issues, str(agent.get("trust_since") or "0000-00-00"))
        v = evaluate(agent, s, policy, today)
        verdict = {"hold": "holds" + (f", needs {'; '.join(v['gap'])}" if v["gap"] else ""),
                   "promote": f"**eligible for {v['to']}**", "demote": f"**demote to {v['to']}**: {'; '.join(v['reasons'])}"}[v["action"]]
        lines.append(f"| {agent['id']} | {agent['trust']} | {s['accepted']} | {s['escapes']} | {s['reverts']} | {verdict} |")
        if v["action"] == "demote" and "--apply" in argv:
            text = apply_trust(text, agent["id"], v["to"], today.isoformat())
    if "--apply" in argv:
        file.write_text(text)
    print("\n".join(lines))
