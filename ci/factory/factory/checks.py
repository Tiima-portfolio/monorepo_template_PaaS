"""PR title, history and agent provenance checks."""

import re

from .globs import matches_any
from .policy import load_policy

TYPES = "feat|fix|perf|refactor|revert|docs|test|chore|ci|build|style"
# "<project>: <type> <description>", e.g. "product: fix rounding" or
# "buildkit: feat! drop the v1 API". An optional scope follows the type.
TITLE = re.compile(rf"^(?P<project>[a-z0-9][\w.-]*): (?P<type>{TYPES})(?:\((?P<scope>[\w./-]+)\))?(?P<bang>!)? \S.*$")
# Titles on main from before the project prefix, e.g. "feat(orders): refunds".
# Release and trust still read them; new PRs can't use them.
LEGACY_TITLE = re.compile(rf"^(?P<type>{TYPES})(?:\((?P<scope>[\w./-]+)\))?(?P<bang>!)?: \S.*$")
BUMP = {"feat": "minor", "fix": "patch", "perf": "patch", "refactor": "patch", "revert": "patch"}


def parse_title(title: str | None) -> dict | None:
    """A squash commit title in either format, or None."""
    m = TITLE.match(title or "") or LEGACY_TITLE.match(title or "")
    if not m:
        return None
    d = m.groupdict()
    return {"project": d.get("project"), "type": d["type"], "scope": d["scope"],
            "bump": "major" if d["bang"] else BUMP.get(d["type"], "none")}


def check_title(title: str | None, projects=()) -> dict:
    """PR title "<project>: <type> <description>"; it becomes the squash commit
    title on main, which sets the version bump. projects: the projects the PR
    changes (see boundary.project_of); the title must name one of them."""
    m = TITLE.match(title or "")
    if not m:
        example = f"{projects[0]}: fix ..." if projects else "product: fix ..."
        return {"ok": False, "message": f'PR title "{title}" must be "<project>: <type> <description>", for example "{example}". '
                                        f'Types: {TYPES.replace("|", ", ")}; "feat!" for a breaking change.'}
    t = parse_title(title)
    if projects and t["project"] not in projects:
        return {"ok": False, "message": f'PR title names the project "{t["project"]}", but this PR changes {", ".join(projects)}. '
                                        f'Start the title with "{projects[0]}: ".'}
    bang = "!" if t["bump"] == "major" else ""
    return {"ok": True, **t, "message": f"Project {t['project']}, type {t['type']}{bang}, version bump: {t['bump']}"}


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
