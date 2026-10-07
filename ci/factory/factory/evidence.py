"""Required evidence per tier, from ci/policy/evidence.yaml.

The active profile (`profile:` in that file) decides each check's mode. The
`production-example` profile is never active by default; its mode is carried
along as `example_mode` so admission can report what it would have blocked.
"""

from .policy import load_policy

EXAMPLE = "production-example"


def mode_in(profile: str, name: str, policy: dict) -> str:
    """A check's mode under a profile: the base mode unless the profile lists it."""
    profiles = policy.get("profiles") or {}
    if profile not in profiles:
        raise ValueError(f"unknown evidence profile: {profile}")
    spec = profiles[profile] or {}
    for mode in ("enforce", "shadow"):
        if name in (spec.get(mode) or []):
            return mode
    return policy["evidence"][name]["mode"]


def required_evidence(tier, agent=False, tests_removed=False, escape_fix=False, owner_checks=False, policy=None) -> list[dict]:
    policy = policy or load_policy("evidence")
    if tier not in policy["tiers"]:
        raise ValueError(f"unknown tier: {tier}")
    names = list(dict.fromkeys(policy["tiers"][tier]))
    for flag, key in ((agent, "agent"), (tests_removed, "tests_removed"), (escape_fix, "escape_fix"), (owner_checks, "owner_checks")):
        if flag:
            names += [n for n in policy["extra"][key] if n not in names]
    profile = policy.get("profile") or "template"
    out = []
    for n in names:
        d = policy["evidence"].get(n)
        if not d:
            raise ValueError(f'evidence "{n}" is required but not defined')
        row = {"name": n, "mode": mode_in(profile, n, policy), "about": d["about"]}
        if EXAMPLE in (policy.get("profiles") or {}):
            row["example_mode"] = mode_in(EXAMPLE, n, policy)
        out.append(row)
    return out
