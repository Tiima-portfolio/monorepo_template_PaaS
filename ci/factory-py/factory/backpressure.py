"""Agent backpressure: an agent may have at most max_open_prs open PRs, and its
sponsoring team at most review_budget agent PRs waiting for review."""


def agent_backpressure(agent, open_prs, agents, teams, current=None) -> list[str]:
    """open_prs: [{number, author, reviewDecision}] (open PRs in the repo)."""
    problems = []
    mine = [p for p in open_prs if p["author"] == agent["login"] and p["number"] != current]
    if len(mine) >= agent["max_open_prs"]:
        problems.append(f"{agent['id']} already has {len(mine)} open PRs (limit {agent['max_open_prs']}); finish or close some first")
    sponsored = [a["login"] for a in agents if a["sponsor"] == agent["sponsor"]]
    waiting = [p for p in open_prs if p["author"] in sponsored and p["number"] != current and p.get("reviewDecision") != "APPROVED"]
    budgets = teams.get("review_budget") or {}
    budget = budgets.get(agent["sponsor"], budgets.get("default", 10))
    if len(waiting) >= budget:
        problems.append(f"{agent['sponsor']} has {len(waiting)} agent PRs waiting for review (budget {budget}); this one waits too")
    return problems
