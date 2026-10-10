#!/usr/bin/env python3
"""Compares the repository rulesets with the files in .github/rulesets/."""


def _sort_keys(v):
    if isinstance(v, list):
        return [_sort_keys(x) for x in v]
    if isinstance(v, dict):
        return {k: _sort_keys(v[k]) for k in sorted(v)}
    return v


def normalize(r: dict) -> dict:
    """The fields that make up a ruleset's behaviour, in a stable order."""
    rules = sorted(({"type": x["type"], "parameters": x.get("parameters") or {}} for x in r.get("rules") or []), key=lambda x: x["type"])
    bypass = sorted(({k: b.get(k) for k in ("actor_id", "actor_type", "bypass_mode")} for b in r.get("bypass_actors") or []),
                    key=lambda b: f"{b['actor_type']}{b['actor_id']}")
    return _sort_keys({"name": r.get("name"), "target": r.get("target"), "enforcement": r.get("enforcement"),
                       "conditions": r.get("conditions"), "bypass_actors": bypass, "rules": rules})


def _only_wanted(want: dict, have: dict) -> dict:
    """Only the parameters a file sets are compared: GitHub adds defaults for new
    options, which shouldn't count as drift."""
    rules = []
    for r in have.get("rules") or []:
        w = next((x for x in want.get("rules") or [] if x["type"] == r["type"]), None)
        if w and w.get("parameters") and r.get("parameters"):
            r = {**r, "parameters": {k: r["parameters"].get(k) for k in w["parameters"]}}
        rules.append(r)
    return {**have, "rules": rules}


def api_body(want: dict) -> dict:
    """Keys starting with "_" are ours, never sent to GitHub."""
    return {k: v for k, v in want.items() if not k.startswith("_")}


def diff(want: dict, have: dict | None) -> list[str]:
    if not have:
        return ["missing"]
    a = normalize(api_body(want))
    b = normalize(_only_wanted(want, have))
    # GitHub only shows bypass actors to repository admins; without them the
    # field is absent, which says nothing about drift.
    hidden = {"bypass_actors"} if "bypass_actors" not in have else set()
    return [k for k in a if a[k] != b[k] and k not in hidden]
