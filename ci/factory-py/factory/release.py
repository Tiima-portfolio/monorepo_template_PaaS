"""Release planning: versions come from git tags, bumps from squash commit
titles, and releases happen in main's history order."""

import re

from .checks import check_title

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def parse(v) -> tuple[int, int, int]:
    m = SEMVER.match(v or "")
    if not m:
        raise ValueError(f"not a version: {v}")
    return tuple(int(x) for x in m.groups())


def latest_version(service: str, tags) -> str | None:
    """Highest version among tags like "orders/v1.2.3" for one service."""
    prefix = f"{service}/v"
    versions = [t[len(prefix):] for t in tags if t.startswith(prefix) and SEMVER.match(t[len(prefix):])]
    return max(versions, key=parse) if versions else None


def next_version(current: str | None, bump: str) -> str | None:
    """New services start at 0.1.0. Below 1.0 a breaking change is a minor bump."""
    if bump == "none":
        return None
    if not current:
        return "0.1.0"
    major, minor, patch = parse(current)
    if bump == "major" and major == 0:
        bump = "minor"
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def plan_releases(commits, tags) -> list[dict]:
    """commits: [{sha, title, affected: [service], changed: [service]}] in history
    order (oldest first). A service the commit changed gets the bump from the
    title; one affected only through a dependency is rebuilt as a patch.
    Returns the releases to make, in the same order."""
    known = list(tags)
    releases = []
    for c in commits:
        title = check_title(c["title"])
        title_bump = title["bump"] if title["ok"] else "none"
        changed = set(c["changed"] if c.get("changed") is not None else c["affected"])
        for service in sorted(c["affected"]):
            bump = title_bump if service in changed else "none" if title_bump == "none" else "patch"
            version = next_version(latest_version(service, known), bump)
            if not version:
                continue
            tag = f"{service}/v{version}"
            known.append(tag)
            releases.append({"sha": c["sha"], "service": service, "version": version, "tag": tag, "bump": bump})
    return releases
