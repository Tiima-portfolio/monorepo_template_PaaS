#!/usr/bin/env python3
import json
import subprocess

import pytest

from factory.scm import SCM, GitHubAdapter, SCMError, get_scm
from factory.scm import github as gh_module


def test_every_interface_method_is_implemented_by_the_github_adapter():
    for name in SCM.__abstractmethods__:
        assert callable(getattr(GitHubAdapter, name)), name


def test_the_platform_is_chosen_by_environment():
    assert isinstance(get_scm({"GITHUB_REPOSITORY": "o/r"}), GitHubAdapter)
    with pytest.raises(ValueError):
        get_scm({"FACTORY_SCM": "svn"})


def test_github_listings_come_back_in_the_cores_shape(monkeypatch):
    seen = []

    def fake(*args):
        seen.append(args)
        return json.dumps([{"number": 7, "title": "feat: x", "author": {"login": "dev"}, "labels": [{"name": "ready"}],
                            "createdAt": "2026-10-01T00:00:00Z", "mergedAt": "2026-10-02T00:00:00Z", "isDraft": False, "headRefOid": "abc"}])

    monkeypatch.setattr(gh_module, "_gh", fake)
    [change] = GitHubAdapter("o/r").list_merged_changes("2026-10-01T00:00:00Z")
    assert change["author"] == "dev" and change["labels"] == ["ready"] and change["head"] == "abc"
    assert "merged:>=2026-10-01" in seen[0]


def test_github_issues_are_lowercase_and_filtered_by_label(monkeypatch):
    monkeypatch.setattr(gh_module, "_gh", lambda *a: json.dumps([{"number": 1, "title": "escape: x", "labels": [{"name": "escape"}],
                                                                  "createdAt": "t", "closedAt": None, "state": "OPEN"}]))
    [issue] = GitHubAdapter("o/r").list_issues(["escape"])
    assert issue["state"] == "open" and issue["labels"] == ["escape"]


def test_a_refused_call_is_an_scm_error(monkeypatch):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "gh", stderr="not mergeable")
    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(SCMError, match="not mergeable"):
        GitHubAdapter("o/r").enqueue_change("id")


def test_publish_decision_updates_the_existing_comment(monkeypatch):
    calls = []

    def fake(*args):
        calls.append(args)
        return "42\n" if "--paginate" in args else ""

    monkeypatch.setattr(gh_module, "_gh", fake)
    GitHubAdapter("o/r").publish_decision(5, "body", "<!-- m -->")
    assert calls[-1][:3] == ("api", "-X", "PATCH") and "comments/42" in calls[-1][3]
    assert calls[-1][-1] == "body=<!-- m -->\nbody"


def test_the_core_does_not_call_gh_directly():
    """Only the adapters and the release and ruleset integrations may shell out to gh."""
    import pathlib
    allowed = {"scm/github.py", "cli/release.py", "cli/rulesets.py"}
    root = pathlib.Path(__file__).resolve().parents[1] / "factory"
    offenders = [str(p.relative_to(root)) for p in root.rglob("*.py")
                 if str(p.relative_to(root)) not in allowed and ('"gh"' in p.read_text() or "'gh'" in p.read_text())]
    assert offenders == []


def test_paged_output_is_flattened(monkeypatch):
    monkeypatch.setattr(gh_module, "_gh", lambda *a: '["a","b"]\n["c"]\n[]\n')
    assert GitHubAdapter("o/r").get_changed_files(1) == ["a", "b", "c"]
    assert GitHubAdapter("o/r").get_approvals(1) == ["a", "b", "c"]
