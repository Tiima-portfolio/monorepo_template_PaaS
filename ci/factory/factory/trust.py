#!/usr/bin/env python3
"""Agent trust from measured outcomes, not from a label someone gives a model.

Levels (experimental, observed, trusted, autonomous) are still set in
ci/policy/agents.yaml, and R3 always needs a human. What moves an agent between
them is its record at the current level, measured against the thresholds in
`trust_progression`:

- promotion needs enough accepted changes, escape and revert rates under their
  limits, few policy violations, no critical escape and enough time observed;
- a critical escape demotes immediately, and an escape or revert rate over the
  limit of the level the agent holds demotes it one level.

Everything here is a pure function of the numbers. The `agent-trust` command
gathers them.
"""

import re
from datetime import date

from .checks import parse_title

PR_REF = re.compile(r"\(#(\d+)\)\s*$")


def stats(agent: dict, prs: list[dict], issues: list[dict], since: str) -> dict:
    """The agent's record since it reached its current level.
    prs: merged [{number, author, title, mergedAt, labels}]; issues: [{title,
    labels, createdAt}]. A revert PR or an escape issue is attributed to the
    agent through the "(#N)" of the squash commit it names."""
    logins = {agent["account"], agent["account"].removesuffix("[bot]")}
    mine = {p["number"]: p for p in prs if p.get("author") in logins and (p.get("mergedAt") or "")[:10] >= since}
    others = [p for p in prs if p["number"] not in mine]

    def origin(title):
        m = PR_REF.search(title or "")
        return mine.get(int(m.group(1))) if m else None

    def is_revert(title):
        return (parse_title(title) or {}).get("type") == "revert"

    reverts = sum(1 for p in others if is_revert(p.get("title")) and origin(p["title"]))
    escapes = [i for i in issues if (i.get("title") or "").startswith("escape:") and "escape" in i.get("labels", [])
               and (i.get("createdAt") or "")[:10] >= since and origin(i["title"])]
    return {
        "accepted": len([p for p in mine.values() if not is_revert(p.get("title"))]),
        "reverts": reverts,
        "escapes": len(escapes),
        "critical_escapes": len([i for i in escapes if "critical" in i["labels"]]),
        "violations": len([p for p in mine.values() if "policy-violation" in p.get("labels", [])]),
    }


def rate(count: int, accepted: int) -> float:
    return count / accepted if accepted else 0.0


def evaluate(agent: dict, s: dict, policy: dict, today: date) -> dict:
    """{action: promote | demote | hold, to, reasons, next_gap}."""
    levels = list(policy["trust_levels"])
    level = agent["trust"]
    if level not in levels:
        return {"action": "hold", "to": level, "reasons": [f"unknown trust level {level}"], "gap": []}
    i = levels.index(level)
    steps = {t["to"]: t for t in policy.get("trust_progression") or []}
    floor = policy.get("demotion", {}).get("critical_escape_to", levels[0])

    if s["critical_escapes"] and i > 0:
        to = levels[min(i - 1, levels.index(floor))] if floor in levels else levels[i - 1]
        return {"action": "demote", "to": to, "reasons": [f"{s['critical_escapes']} critical escape(s)"], "gap": []}
    held = steps.get(level)
    min_sample = policy.get("demotion", {}).get("min_accepted", 20)
    if held and i > 0 and s["accepted"] >= min_sample:
        over = []
        if rate(s["escapes"], s["accepted"]) > held["max_escape_rate"]:
            over.append(f"escape rate {rate(s['escapes'], s['accepted']):.1%} over {held['max_escape_rate']:.1%}")
        if rate(s["reverts"], s["accepted"]) > held["max_revert_rate"]:
            over.append(f"revert rate {rate(s['reverts'], s['accepted']):.1%} over {held['max_revert_rate']:.1%}")
        if over:
            return {"action": "demote", "to": levels[i - 1], "reasons": over, "gap": []}
    nxt = steps.get(levels[i + 1]) if i + 1 < len(levels) else None
    if not nxt:
        return {"action": "hold", "to": level, "reasons": ["top level" if i + 1 >= len(levels) else "no thresholds for the next level"], "gap": []}
    days = (today - date.fromisoformat(str(agent["trust_since"]))).days if agent.get("trust_since") else 0
    gap = []
    if s["accepted"] < nxt["min_accepted"]:
        gap.append(f"{nxt['min_accepted'] - s['accepted']} more accepted change(s)")
    if rate(s["escapes"], s["accepted"]) > nxt["max_escape_rate"] or (not s["accepted"] and s["escapes"]):
        gap.append(f"escape rate under {nxt['max_escape_rate']:.1%}")
    if rate(s["reverts"], s["accepted"]) > nxt["max_revert_rate"]:
        gap.append(f"revert rate under {nxt['max_revert_rate']:.1%}")
    if s["violations"] > nxt["max_violations"]:
        gap.append(f"at most {nxt['max_violations']} policy violation(s)")
    if days < nxt["min_days"]:
        gap.append(f"{nxt['min_days'] - days} more day(s) observed")
    if gap:
        return {"action": "hold", "to": level, "reasons": [], "gap": gap}
    return {"action": "promote", "to": levels[i + 1], "reasons": [f"meets the thresholds for {levels[i + 1]}"], "gap": []}


def apply_trust(text: str, agent_id: str, level: str, since: str) -> str:
    """agents.yaml with one agent's trust and trust_since changed, keeping comments."""
    out, inside = [], False
    for line in text.split("\n"):
        m = re.match(r"^(\s*)- id:\s*(\S+)", line)
        if m:
            inside = m.group(2) == agent_id
        if inside and re.match(r"^\s+trust:\s", line):
            indent = re.match(r"^(\s+)", line).group(1)
            line = f"{indent}trust: {level}\n{indent}trust_since: {since}"
        elif inside and re.match(r"^\s+trust_since:\s", line):
            continue
        out.append(line)
    return "\n".join(out)
