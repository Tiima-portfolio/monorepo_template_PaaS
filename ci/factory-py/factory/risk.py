"""Risk tier classifier: sets R0 to R3 for a PR from ci/policy/risk.yaml."""

from .globs import matches_any
from .policy import load_policy

TIERS = ["R0", "R1", "R2", "R3"]


def _higher(a: str, b: str) -> str:
    return a if TIERS.index(a) >= TIERS.index(b) else b


def file_tier(file: str, policy: dict) -> str:
    for tier in ("R3", "R2", "R0"):
        if matches_any(file, policy["paths"].get(tier, [])):
            return tier
    return "R1"  # test files and everything else


def classify(files=(), affected_projects=0, criticalities=(), override=False, major_bump=False, raise_=(), policy=None) -> dict:
    policy = policy or load_policy("risk")
    reasons = []
    tier = "R0"
    for f in files:
        t = file_tier(f, policy)
        if TIERS.index(t) > TIERS.index(tier):
            reasons.append(f"{f} is {t}")
        tier = _higher(tier, t)
    if not files:
        reasons.append("no changed files")
    r2 = policy["at_least"]["R2"]
    if affected_projects > r2["affected_projects_over"]:
        tier = _higher(tier, "R2")
        reasons.append(f"{affected_projects} affected projects")
    if any(c in r2["criticality"] for c in criticalities):
        tier = _higher(tier, "R2")
        reasons.append("affects a critical project")
    r3 = policy["at_least"]["R3"]
    if r3.get("boundary_override") and override:
        tier = "R3"
        reasons.append("boundary override")
    if r3.get("major_bump") and major_bump:
        tier = "R3"
        reasons.append("major version bump")
    for name in raise_:
        if name not in policy["raise"]:
            raise ValueError(f"unknown raise rule: {name}")
        nxt = TIERS[min(TIERS.index(tier) + 1, 3)]
        if nxt != tier:
            reasons.append(f"raised by {name}")
        tier = nxt
    return {"tier": tier, "reasons": reasons}


def test_only(files, policy=None) -> bool:
    """True when the PR changes only test files (they are R1, never R0)."""
    policy = policy or load_policy("risk")
    return bool(files) and all(matches_any(f, policy["test_paths"]) for f in files)
