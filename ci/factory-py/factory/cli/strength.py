"""Shared by diff-coverage and mutation: the lines a PR adds to a project's
code (not its tests), and the threshold that applies to the project."""

from ..coverage import added_lines
from ..globs import matches_any
from .common import env, git_yaml, run


def added_code_lines(root: str, test_paths) -> dict:
    """{project-relative file: set(lines)} added by the PR, tests left out."""
    diff = run("git", "diff", "-U0", f"{env.get('FACTORY_BASE')}...{env.get('FACTORY_HEAD')}", "--", root)
    return {f[len(root) + 1:]: ls for f, ls in added_lines(diff).items()
            if f.startswith(f"{root}/") and not matches_any(f, test_paths)}


def threshold(floors: dict, criticality: str, root: str, key: str):
    """The policy floor for the project's criticality, or the owner's own
    higher threshold from guardrails.yaml on the base branch."""
    guardrails = git_yaml(env.get("FACTORY_BASE"), f"{root}/guardrails.yaml") or {}
    return max(floors.get(criticality, floors["normal"]), (guardrails.get("thresholds") or {}).get(key) or 0)
