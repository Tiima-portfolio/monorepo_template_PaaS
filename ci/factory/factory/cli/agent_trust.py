"""Measures every agent against ci/policy/agents.yaml and prints what its trust
level should be.

Usage: agent-trust [--apply] [--open-pr]
  --apply    rewrites agents.yaml for demotions only; promotions are a
             reviewed R3 change a human opens.
  --open-pr  with --apply, opens a P0 PR with the demotions, and writes the
             report to the run summary.
Env: GITHUB_REPOSITORY, GH_TOKEN, FACTORY_GIT_USER."""

import subprocess
from datetime import date
from pathlib import Path

from ..policy import load_policy, policy_dir
from ..scm import get_scm
from ..trust import apply_trust, evaluate, stats
from .common import append, push_branch

TITLE = "ci: chore demote agents on measured outcomes"


def main(argv):
    policy = load_policy("agents")
    today = date.today()
    scm = get_scm()
    prs = scm.list_merged_changes("2000-01-01")
    issues = scm.list_issues(["escape"], state="all")
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
    report = "\n".join(lines)
    print(report)
    if "--apply" not in argv:
        return 0
    changed = file.read_text() != text
    file.write_text(text)
    if "--open-pr" not in argv:
        return 0
    append("GITHUB_STEP_SUMMARY", report + "\n")
    if not changed:
        print("No agent earned a demotion.")
        return 0
    branch = f"agent-trust/{today.isoformat()}"
    push_branch(branch, TITLE)
    body = f"A critical escape or a rate over the limit demoted an agent (ci/policy/agents.yaml, `trust_progression`).\n\n{report}"
    print(f"Opened {scm.open_change(branch, TITLE, body, ['P0'])}")
