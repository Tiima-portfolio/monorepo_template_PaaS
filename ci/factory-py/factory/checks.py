"""PR title, history and agent provenance checks."""

import re

from .globs import matches_any
from .policy import load_policy

TITLE = re.compile(r"^(feat|fix|perf|refactor|revert|docs|test|chore|ci|build|style)(\([\w./-]+\))?(!)?: \S.*$")
BUMP = {"feat": "minor", "fix": "patch", "perf": "patch", "refactor": "patch", "revert": "patch"}


def check_title(title: str | None) -> dict:
    """Conventional PR title; the squash commit title sets the version bump."""
    m = TITLE.match(title or "")
    if not m:
        return {"ok": False, "message": f'PR title "{title}" must start with a type such as "fix:", "feat:", "feat!:", "docs:", "test:", "chore:", "ci:" or "build:".'}
    kind, bang = m.group(1), m.group(3)
    bump = "major" if bang else BUMP.get(kind, "none")
    return {"ok": True, "type": kind, "bump": bump, "message": f"Title type {kind}{'!' if bang else ''}, version bump: {bump}"}


def check_history(commits) -> dict:
    """commits: [{sha, parents}]. Squash merges need no merge commits."""
    merges = [c for c in commits if len(c.get("parents") or []) > 1]
    if merges:
        return {"ok": False, "message": "Merge commits aren't allowed; rebase instead: " + ", ".join(c["sha"][:7] for c in merges)}
    return {"ok": True, "message": f"{len(commits)} commit(s), no merge commits"}


def trailers(message: str) -> dict:
    found = {}
    for line in (message or "").split("\n"):
        m = re.match(r"^([A-Za-z-]+):\s*(.+)$", line.strip())
        if m:
            found[m.group(1)] = m.group(2)
    return found


def check_provenance(author, commits=(), files=(), boundary=None, tier="R0", policy=None) -> dict:
    policy = policy or load_policy("agents")
    agent = next((a for a in policy["agents"] if a["account"] == author), None)
    if not agent:
        return {"ok": True, "is_agent": False, "needs_human": False, "raise": [], "message": "Human author"}
    problems = []
    for c in commits:
        t = trailers(c.get("message", ""))
        missing = [k for k in policy["required_trailers"] if k not in t]
        if missing:
            problems.append(f"commit {c['sha'][:7]} lacks {', '.join(missing)}")
    forbidden = [f for f in files if matches_any(f, policy["forbidden_paths"])]
    if forbidden:
        problems.append(f"agents may not change {', '.join(forbidden)}")
    boundary_name = (boundary or "").split(":")[0]
    if boundary and boundary_name not in agent["boundaries"]:
        problems.append(f"{agent['id']} may not change the {boundary_name} boundary")
    level = policy["trust_levels"].get(agent["trust"])
    if not level:
        problems.append(f"{agent['id']} has unknown trust level {agent['trust']}")
    needs_human = not level or tier not in level["merges_alone"]
    alone = f"needs a human approval at {tier}" if needs_human else f"may merge {tier} alone"
    return {
        "ok": not problems,
        "is_agent": True,
        "agent": agent["id"],
        "trust": agent["trust"],
        "needs_human": needs_human,
        "raise": ["agent_above_trust"] if needs_human else [],
        "message": "; ".join(problems) if problems else f"{agent['id']} ({agent['trust']}) {alone}",
    }
