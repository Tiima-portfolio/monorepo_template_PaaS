#!/usr/bin/env python3
"""Approval routing: who must approve a PR, per service it touches, from each
service's service.yaml and guardrails.yaml on the base branch."""

import re

from .globs import matches_any
from .risk import TIERS


def own_files(root: str, files) -> list[str]:
    """The changed paths inside a project, relative to its root."""
    return [f[len(root) + 1 :] for f in files if f.startswith(f"{root}/")]


def route(services, files, author, tier, teams) -> dict:
    """services: [{name, root, boundary, base: {service, guardrails} | None, head: {service}}]
    (base None means a new service)."""
    author_teams = [t for t, members in teams["teams"].items() if author in members]
    approvals = []
    raise_ = []
    owning_teams = []

    for s in services:
        own = own_files(s["root"], files)
        if not own:
            continue
        head_owner = ((s.get("head") or {}).get("service") or {}).get("owner")
        if not s.get("base"):
            approvals.append({"service": s["name"], "teams": teams["catalog_approvers"].get(s.get("boundary")) or ["factory-owners"], "reason": "new service"})
            if head_owner:
                approvals.append({"service": s["name"], "teams": [head_owner], "reason": "named as owner of the new service"})
            continue
        owner = s["base"]["service"]["owner"]
        if owner not in owning_teams:
            owning_teams.append(owner)
        g = s["base"].get("guardrails") or {}
        if head_owner and head_owner != owner:
            approvals.append({"service": s["name"], "teams": [owner], "reason": f"owner change from {owner}"})
            approvals.append({"service": s["name"], "teams": [head_owner], "reason": f"owner change to {head_owner}"})
            continue
        protected_hit = any(matches_any(f, g.get("protected_paths") or []) for f in own)
        if protected_hit and "protected_path" not in raise_:
            raise_.append("protected_path")
        contract = s["base"]["service"].get("contract") or []
        contract_hit = any(f in contract or matches_any(f, contract) for f in own)
        guardrails_hit = "guardrails.yaml" in own
        risky = (protected_hit or contract_hit or guardrails_hit or TIERS.index(tier) >= 2
                 or any(re.search(r"(^|/)migrations/", f) for f in own))
        contributors = g.get("contributors") or []
        if risky:
            reason = ("protected path" if protected_hit else "contract change" if contract_hit
                      else "guardrails change" if guardrails_hit else f"risk tier {tier}")
            approvals.append({"service": s["name"], "teams": [owner], "reason": reason})
        elif owner in author_teams:
            approvals.append({"service": s["name"], "teams": [owner], "reason": "owning team"})
        elif any(t in contributors for t in author_teams):
            approvals.append({"service": s["name"], "teams": [t for t in author_teams if t in contributors],
                              "reason": "listed contributor; owner notified", "notify": owner})
        else:
            approvals.append({"service": s["name"], "teams": [owner], "reason": "contributor not listed in guardrails.yaml"})
    if len(owning_teams) > 3:
        raise_.append("owning_teams_over_3")
    return {"approvals": approvals, "raise": raise_, "owning_teams": owning_teams}


def approvals_met(approvals, approvers, teams, author=None, requester=None) -> dict:
    """approvers: logins whose latest review is APPROVED. Never the author or requester."""
    valid = [a for a in approvers if a not in (author, requester)]
    missing = [req for req in approvals
               if not any(m in valid for t in req["teams"] for m in teams["teams"].get(t) or [])]
    return {"ok": not missing, "missing": missing}
