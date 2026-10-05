"""Required evidence per tier, from ci/policy/evidence.yaml."""

from .policy import load_policy


def required_evidence(tier, agent=False, tests_removed=False, escape_fix=False, owner_checks=False, policy=None) -> list[dict]:
    policy = policy or load_policy("evidence")
    if tier not in policy["tiers"]:
        raise ValueError(f"unknown tier: {tier}")
    names = list(dict.fromkeys(policy["tiers"][tier]))
    for flag, key in ((agent, "agent"), (tests_removed, "tests_removed"), (escape_fix, "escape_fix"), (owner_checks, "owner_checks")):
        if flag:
            names += [n for n in policy["extra"][key] if n not in names]
    out = []
    for n in names:
        d = policy["evidence"].get(n)
        if not d:
            raise ValueError(f'evidence "{n}" is required but not defined')
        out.append({"name": n, "mode": d["mode"], "about": d["about"]})
    return out
