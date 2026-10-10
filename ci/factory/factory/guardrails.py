#!/usr/bin/env python3
"""Owner guardrails from each touched service's guardrails.yaml (base branch):
required owner checks to run, and the rules for agents."""

from .globs import matches_any
from .owners import own_files
from .risk import TIERS


def _guardrails(s) -> dict:
    return (s.get("base") or {}).get("guardrails") or {}


def owner_checks(services, files) -> list[dict]:
    """services: [{name, root, base: {guardrails} | None}]; files: changed paths."""
    checks = []
    for s in services:
        own = own_files(s["root"], files)
        for c in _guardrails(s).get("required_checks") or []:
            if any(matches_any(f, c.get("when") or ["**"]) for f in own):
                checks.append({"project": s["name"], "target": c["target"], "budget": c.get("budget")})
    return checks


def agent_guardrails(services, files, tier) -> dict:
    """Forbidden paths block; a tier above max_autonomous_tier needs a human."""
    problems = []
    needs_human = False
    for s in services:
        g = _guardrails(s).get("agents") or {}
        own = own_files(s["root"], files)
        if not own:
            continue
        forbidden = [f for f in own if matches_any(f, g.get("forbidden_paths") or [])]
        if forbidden:
            problems.append(f"{s['name']}'s owner doesn't allow agents to change {', '.join(forbidden)}")
        if g.get("max_autonomous_tier") and TIERS.index(tier) > TIERS.index(g["max_autonomous_tier"]):
            needs_human = True
    return {"ok": not problems, "problems": problems, "needs_human": needs_human}
