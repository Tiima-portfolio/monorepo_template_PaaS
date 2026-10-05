"""Weekly factory metrics: flow and outcomes, not activity. Pure functions;
the metrics-report command fetches the data."""

import math
import re

from .budgets import parse_time
from .numbers import num, round1


def _hours(a, b) -> float:
    return (parse_time(b) - parse_time(a)).total_seconds() / 3600


def _percentile(values, p):
    if not values:
        return None
    s = sorted(values)
    return round1(s[min(len(s) - 1, math.floor(p / 100 * len(s)))])


def _dash(v):
    return "-" if v is None else v


def report(prs, issues, runs, since, until, agents=()) -> str:
    """prs: merged PRs [{number, author, createdAt, mergedAt, labels, body}];
    issues: [{title, labels, createdAt, closedAt, state}]; runs: factory runs on PRs [{conclusion}]."""
    lead = [_hours(p["createdAt"], p["mergedAt"]) for p in prs]
    features = {}
    for p in prs:
        m = re.search(r"^Feature-Id:\s*(\S+)", p.get("body") or "", re.M)
        if m:
            features.setdefault(m.group(1), []).append(_hours(p["createdAt"], p["mergedAt"]))

    def label(name):
        return [i for i in issues if name in i["labels"]]

    def open_now(name):
        return [i for i in label(name) if i["state"] == "open"]

    opened = len([i for i in label("escape") if i["createdAt"] >= since])
    failed = len([r for r in runs if r.get("conclusion") == "failure"])
    agent_prs = [p for p in prs if p.get("author") in agents]
    blocked = math.floor(failed / len(runs) * 100 + 0.5) if runs else 0
    quarantined = open_now("quarantine")
    oldest = f" (oldest {math.floor(max(_hours(i['createdAt'], until) for i in quarantined) / 24 + 0.5)} days)" if quarantined else ""
    lines = [
        f"## Factory metrics, {since[:10]} to {until[:10]}",
        "",
        "| Measure | Value |",
        "| --- | --- |",
        f"| PRs merged | {len(prs)} ({len(agent_prs)} by agents) |",
        f"| Lead time, PR opened to merged | median {_dash(_percentile(lead, 50))} h, p90 {_dash(_percentile(lead, 90))} h |",
        f"| Factory runs blocked | {blocked}% of {len(runs)} |",
        f"| Boundary overrides | {len([p for p in prs if 'boundary-override' in p['labels']])} |",
        f"| Hotfixes | {len([p for p in prs if 'hotfix' in p['labels']])} |",
        f"| Escapes opened / open now | {opened} / {len(open_now('escape'))} |",
        f"| Quarantined tests open | {len(quarantined)}{oldest} |",
        f"| Test strength drops open | {len(open_now('test-adequacy'))} |",
    ]
    if features:
        lines += ["", "| Feature | PRs | Lead time, p90 |", "| --- | --- | --- |"]
        for f, v in sorted(features.items(), key=lambda kv: -len(kv[1]))[:15]:
            lines.append(f"| {f} | {len(v)} | {num(_percentile(v, 90))} h |")
    return "\n".join(lines)
