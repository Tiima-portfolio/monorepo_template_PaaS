"""Boundary check: a PR must stay inside one boundary."""

from .globs import matches_any


def boundary_of(file: str, policy: dict) -> str | None:
    """The boundary key of a path, e.g. "product" or
    "internal-tool:internal-tools/search", or None when no rule owns it."""
    for b in policy["boundaries"]:
        if matches_any(file, b["paths"]):
            if not b.get("per"):
                return b["name"]
            return f"{b['name']}:{'/'.join(file.split('/')[: b['per']])}"
    return None


def project_of(key: str) -> str:
    """The project a boundary key names in PR titles: the boundary, or the
    folder for a split one ("internal-service:internal-services/buildkit" is
    "buildkit")."""
    return key.split("/")[-1] if ":" in key else key


def check_boundary(files, policy: dict, override: bool = False) -> dict:
    """A failed check has no "boundary" key, so gate.json leaves it out as the
    JS did. override: a factory owner added the override label (the workflow checks who)."""
    by_boundary: dict[str, list[str]] = {}
    unowned = []
    for f in files:
        key = boundary_of(f, policy)
        if key is None:
            unowned.append(f)
        else:
            by_boundary.setdefault(key, []).append(f)
    boundaries = sorted(by_boundary)
    result = {"boundaries": boundaries, "by_boundary": by_boundary, "unowned": unowned, "override": False}
    if unowned:
        listing = "\n".join(f"- {f}" for f in unowned)
        return {**result, "ok": False,
                "message": f"No boundary owns these paths; add them to ci/policy/boundaries.yaml or move them:\n{listing}"}
    if len(boundaries) <= 1:
        b = boundaries[0] if boundaries else None
        return {**result, "ok": True, "boundary": b, "message": f"Boundary: {b}" if b else "No changed files"}
    if override:
        return {**result, "ok": True, "boundary": None, "override": True,
                "message": f"Cross-boundary change allowed by the {policy['override']['label']} label: {', '.join(boundaries)}. Risk tier is R3."}
    split = "\n".join(f"- {b}: {len(by_boundary[b])} file(s), e.g. {by_boundary[b][0]}" for b in boundaries)
    return {**result, "ok": False,
            "message": f"This PR touches {len(boundaries)} boundaries. Split it into one PR per boundary:\n{split}"}
