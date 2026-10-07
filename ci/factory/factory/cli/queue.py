"""Merge queue controller, run by .github/workflows/queue.yml. Reads open PRs
and the merge queue, picks what to enqueue and enqueues it.

Env: GITHUB_REPOSITORY, GH_TOKEN (the factory App's token, so the
merge_group run starts; GITHUB_TOKEN events don't start workflows).
"""

from ..policy import load_policy
from ..queue import is_rule_change, select_to_enqueue
from ..scm import SCMError, get_scm
from .common import env

def main(argv):
    scm = get_scm()
    candidates, queued = scm.list_queue_state()
    policy = load_policy("queue")
    agents = load_policy("agents")["agents"]
    queue = [{**e, "ruleChange": is_rule_change(e, policy)} for e in queued]

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
        try:
            scm.enqueue_change(pr_id, jump=p["jump"])
        except SCMError as e:
            # GitHub refuses a PR that just changed state (a new push, a
            # conflict); the next run picks it up again. The rest still go in.
            print(f"::warning::#{p['number']} not enqueued: {e}")
            continue
        print(f"#{p['number']} enqueued as {p['priority']}{' (front of the queue)' if p['jump'] else ''}")
    if not result["picks"] and not result["waiting"]:
        print("Nothing ready.")
