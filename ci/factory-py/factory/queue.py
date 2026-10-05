"""Merge queue controller: which ready PRs to enqueue now, in what order."""

import re
from datetime import datetime, timezone

from .globs import matches_any

RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}


def priority_of(pr, policy, agent_accounts) -> str:
    label = next((l for l in pr.get("labels") or [] if re.match(r"^P[0-4]$", l)), None)
    if label:
        return label
    return policy["default_priority"]["agent" if pr.get("author") in agent_accounts else "human"]


def is_workspace_change(pr, policy) -> bool:
    return any(f in (policy.get("workspace_paths") or []) for f in pr.get("files") or [])


def off_peak(now: datetime, window) -> bool:
    if not window:
        return True
    h = now.astimezone(timezone.utc).hour
    if window["from"] > window["to"]:
        return h >= window["from"] or h < window["to"]
    return window["from"] <= h < window["to"]


def is_rule_change(pr, policy) -> bool:
    return any(matches_any(f, policy["rule_change_paths"]) for f in pr.get("files") or [])


def select_to_enqueue(candidates, queue, policy, agent_accounts=(), agent_limits=None, now=None) -> dict:
    """candidates: [{number, author, labels, files, readyAt, admitted, inQueue}]
    queue: [{number, ruleChange}] current merge queue entries.
    agent_limits: {account: max entries in the queue}.
    Returns {picks: [{number, priority, jump}], waiting: [{number, reason}]}."""
    agent_limits = agent_limits or {}
    now = now or datetime.now(timezone.utc)
    waiting = []
    picks = []
    ready = [{**pr, "priority": priority_of(pr, policy, agent_accounts), "ruleChange": is_rule_change(pr, policy)}
             for pr in candidates if policy["ready_label"] in pr["labels"] and pr.get("admitted") and not pr.get("inQueue")]
    ready.sort(key=lambda pr: (RANK[pr["priority"]], pr["readyAt"]))

    # A rule change in the queue holds everything else until it has merged.
    if any(e.get("ruleChange") for e in queue):
        return {"picks": picks, "waiting": [{"number": pr["number"], "reason": "a rule change is merging alone"} for pr in ready]}
    depth = len(queue)
    per_agent = {}
    for e in queue:
        if e.get("author"):
            per_agent[e["author"]] = per_agent.get(e["author"], 0) + 1

    for pr in ready:
        number, priority, author = pr["number"], pr["priority"], pr.get("author")
        window = policy.get("off_peak_utc")
        if priority != "P0" and is_workspace_change(pr, policy) and not off_peak(now, window):
            waiting.append({"number": number, "reason": f"workspace change waits for the off-peak window ({window['from']}:00 to {window['to']}:00 UTC)"})
            continue
        if pr["ruleChange"]:
            if depth == 0 and not picks:
                picks.append({"number": number, "priority": priority, "jump": priority == "P0"})
                # Nothing else enters with it.
                waiting += [{"number": rest["number"], "reason": "a rule change is merging alone"} for rest in ready if rest["number"] != number]
                return {"picks": picks, "waiting": waiting}
            waiting.append({"number": number, "reason": "rule change waits for an empty queue"})
            continue
        if priority != "P0" and depth >= policy["max_depth"]:
            waiting.append({"number": number, "reason": f"queue is full ({depth})"})
            continue
        hold_at = (policy.get("hold_at_depth") or {}).get(priority)
        if hold_at is not None and depth >= hold_at:
            waiting.append({"number": number, "reason": f"backpressure: {priority} waits at depth {depth}"})
            continue
        limit = agent_limits.get(author)
        if limit is not None and per_agent.get(author, 0) >= limit:
            waiting.append({"number": number, "reason": f"agent {author} has {limit} entries queued"})
            continue
        picks.append({"number": number, "priority": priority, "jump": priority == "P0"})
        per_agent[author] = per_agent.get(author, 0) + 1
        depth += 1
    return {"picks": picks, "waiting": waiting}
