"""The commands the workflows call instead of inline shell."""

import base64
import io
import json
import stat
import tarfile

import pytest

from factory.cli import buildkit_service, escape_issue, nightly, override_check, prefetch_images, quarantine, revert, verify_run
from factory.scm import GitHubAdapter
from factory.scm import github as gh_module


class FakeSCM:
    def __init__(self, issues=(), labeler=None, admins=()):
        self.issues, self.labeler, self.admins = list(issues), labeler, set(admins)
        self.opened, self.changes = [], []

    def list_issues(self, labels, state="open"):
        return self.issues

    def open_issue(self, title, body, labels, assignees=()):
        self.opened.append({"title": title, "body": body, "labels": labels, "assignees": list(assignees)})
        return f"https://x/issues/{len(self.opened)}"

    def open_change(self, branch, title, body, labels):
        self.changes.append({"branch": branch, "title": title, "body": body, "labels": labels})
        return "https://x/pull/9"

    def label_added_by(self, number, label):
        return self.labeler

    def is_admin(self, login):
        return login in self.admins


@pytest.mark.parametrize("title, want", [
    ("product: fix x (#12)", "product: revert fix x (#12)"),
    ("ci: feat(gate)!: y", "ci: revert feat(gate)!: y"),
    ("fix: old style (#3)", "revert: fix: old style (#3)"),
    ("Update README", "revert: Update README"),
])
def test_revert_title_keeps_the_project(title, want):
    assert revert.revert_title(title) == want


def test_revert_opens_the_pr_and_the_escape(monkeypatch):
    scm, calls = FakeSCM(), []
    monkeypatch.setattr(revert, "get_scm", lambda: scm)
    monkeypatch.setattr(revert, "git", lambda *a: calls.append(a) or "product: fix x (#12)")
    monkeypatch.setattr(revert, "set_git_identity", lambda: None)
    monkeypatch.setenv("GITHUB_SHA", "0123456789abcdef")
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_RUN_ID", "5")
    monkeypatch.delenv("HAS_APP_TOKEN", raising=False)
    revert.main([])
    assert ("revert", "--no-edit", "0123456789abcdef") in calls and ("push", "origin", "revert/0123456789ab") in calls
    [pr] = scm.changes
    assert pr["title"] == "product: revert fix x (#12)" and pr["labels"] == ["P0"]
    assert "actions/runs/5" in pr["body"] and "close and reopen" in pr["body"]
    [issue] = scm.opened
    assert issue["title"] == "escape: product: fix x (#12)" and "https://x/pull/9" in issue["body"]


def tls_bundle() -> str:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in ("ca.crt", "tls.crt", "tls.key"):
            data = name.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            tar.addfile(info, io.BytesIO(data))
    return base64.b64encode(buf.getvalue()).decode()


def test_buildkit_service_sets_the_env_and_keeps_the_key_private(tmp_path, monkeypatch):
    github_env = tmp_path / "env"
    monkeypatch.setenv("GITHUB_ENV", str(github_env))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("BUILDKIT_ADDR", "tcp://bk:1234")
    monkeypatch.setenv("BUILDKIT_TLS", tls_bundle())
    monkeypatch.setenv("BUILDKIT_CACHE_REF", "ghcr.io/o/cache")
    monkeypatch.setenv("BUILDKIT_CACHE_WRITE", "true")
    buildkit_service.main([])
    tls = tmp_path / "buildkit-tls"
    assert github_env.read_text().splitlines() == [
        "FACTORY_BUILDKIT_ADDR=tcp://bk:1234", f"FACTORY_BUILDKIT_TLS_DIR={tls}",
        "FACTORY_BUILDKIT_CACHE_REF=ghcr.io/o/cache", "FACTORY_BUILDKIT_CACHE_WRITE=true"]
    assert (tls / "tls.key").read_text() == "tls.key"
    assert stat.S_IMODE((tls / "tls.key").stat().st_mode) == 0o600
    assert stat.S_IMODE(tls.stat().st_mode) == 0o700


def test_buildkit_service_without_an_address_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ENV", str(tmp_path / "env"))
    monkeypatch.delenv("BUILDKIT_ADDR", raising=False)
    buildkit_service.main([])
    assert not (tmp_path / "env").exists()


def test_escape_issue_is_assigned_to_the_hotfix_author(monkeypatch):
    scm = FakeSCM()
    monkeypatch.setattr(escape_issue, "get_scm", lambda: scm)
    monkeypatch.setenv("PR", "7")
    monkeypatch.setenv("TITLE", "api: fix crash")
    monkeypatch.setenv("AUTHOR", "dev")
    escape_issue.main([])
    assert scm.opened == [{"title": "escape: api: fix crash (hotfix #7)", "body": scm.opened[0]["body"], "labels": ["escape"], "assignees": ["dev"]}]
    assert "Hotfix #7 merged" in scm.opened[0]["body"]


@pytest.mark.parametrize("labeler, admins, ok", [("boss", {"boss"}, True), ("dev", {"boss"}, False), (None, {"boss"}, False)])
def test_override_counts_only_an_admins_label(tmp_path, monkeypatch, labeler, admins, ok):
    monkeypatch.setattr(override_check, "get_scm", lambda: FakeSCM(labeler=labeler, admins=admins))
    monkeypatch.setenv("GITHUB_ENV", str(tmp_path / "env"))
    monkeypatch.setenv("PR", "3")
    override_check.main([])
    assert ((tmp_path / "env").read_text() if (tmp_path / "env").exists() else "") == ("FACTORY_OVERRIDE_OK=true\n" if ok else "")


def test_quarantine_list_is_in_the_gates_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(quarantine, "get_scm", lambda: FakeSCM([{"title": "quarantine: t1", "createdAt": "2026-10-01T00:00:00Z", "labels": []}]))
    quarantine.main(["list", str(tmp_path / "q.json")])
    assert json.loads((tmp_path / "q.json").read_text()) == [{"title": "quarantine: t1", "created_at": "2026-10-01T00:00:00Z"}]


def test_quarantine_opens_one_issue_per_new_flaky_test(monkeypatch):
    monkeypatch.setenv("FACTORY_SHA", "abc")
    scm = FakeSCM([{"title": "quarantine: old"}])
    assert quarantine.open_issues(["old", "new", "new"], scm) == ["new"]
    [issue] = scm.opened
    assert issue["title"] == "quarantine: new" and issue["labels"] == ["quarantine"] and "Found on abc." in issue["body"]


def test_verify_run_records_a_failure_without_raising(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(verify_run, "nx", lambda *a: ran.append(a) or a[-1] != "b:check")
    monkeypatch.setenv("FACTORY_OUT", str(tmp_path))
    monkeypatch.setenv("FACTORY_AFFECTED", "2")
    monkeypatch.setenv("FACTORY_BASE", "b1")
    monkeypatch.setenv("FACTORY_HEAD", "h1")
    verify_run.main(["affected", "format-lint", "lint"])
    assert ran[0] == ("affected", "-t", "lint", "--base=b1", "--head=h1")
    assert json.loads((tmp_path / "evidence/format-lint.json").read_text())["status"] == "pass"
    monkeypatch.setenv("OWNER_CHECKS", "a:check b:check")
    verify_run.main(["owners"])
    rec = json.loads((tmp_path / "evidence/owner-checks.json").read_text())
    assert rec["status"] == "fail" and rec["details"] == "a:check b:check"


def test_pull_images_logs_in_with_a_throwaway_config(monkeypatch):
    calls = []
    monkeypatch.setattr(prefetch_images.subprocess, "run", lambda args, **kw: calls.append((args, kw["env"]["DOCKER_CONFIG"], kw.get("input"))))
    monkeypatch.setenv("REGISTRY_TOKEN", "t0ken")
    monkeypatch.setenv("GITHUB_ACTOR", "bot")
    prefetch_images.pull(["ghcr.io/o/ci-go@sha256:" + "0" * 64])
    assert [c[0][1] for c in calls] == ["login", "pull", "logout"]
    assert calls[0][2] == "t0ken" and "t0ken" not in " ".join(calls[0][0])
    assert len({c[1] for c in calls}) == 1 and not __import__("os").path.exists(calls[0][1])


def test_mutation_summary_lines():
    report = {"files": {"a.ts": {"mutations": [{"status": "KILLED"}, {"status": "KILLED"}, {"status": "LIVED"}, {"status": "NoCoverage"}]}}}
    assert nightly.mutation_line("product/x", report) == "product/x: 66.7% of 3 mutants killed"
    assert nightly.mutation_line("p", {"files": {"a": {"mutations": [{"status": "KILLED"}]}}}) == "p: 100% of 1 mutants killed"
    assert nightly.mutation_line("p", {}) == "p: no mutants"


def test_nightly_opens_an_issue_only_for_a_drop(tmp_path, monkeypatch):
    scm = FakeSCM()
    monkeypatch.setattr(nightly, "get_scm", lambda: scm)
    monkeypatch.setenv("FACTORY_OUT", str(tmp_path))
    (tmp_path / "evidence").mkdir()
    record = tmp_path / "evidence/coverage-ratchet.json"
    record.write_text(json.dumps({"status": "pass", "details": "ok"}))
    nightly.main(["drop-issue"])
    assert scm.opened == []
    record.write_text(json.dumps({"status": "fail", "details": "x coverage 50% is below main's 60%"}))
    nightly.main(["drop-issue"])
    assert scm.opened[0]["labels"] == ["test-adequacy"] and "x coverage 50%" in scm.opened[0]["body"]


def test_github_adapter_reads_who_added_a_label(monkeypatch):
    monkeypatch.setattr(gh_module, "_gh", lambda *a: '["first"]\n["boss"]' if "events" in a[1] else "admin\n")
    adapter = GitHubAdapter("o/r")
    assert adapter.label_added_by(3, "boundary-override") == "boss"
    assert adapter.is_admin("boss")


def test_github_adapter_opens_an_issue(monkeypatch):
    seen = []
    monkeypatch.setattr(gh_module, "_gh", lambda *a: seen.append(a) or "https://x/issues/1\n")
    assert GitHubAdapter("o/r").open_issue("t", "b", ["escape"], ["dev"]) == "https://x/issues/1"
    assert seen[0] == ("issue", "create", "--repo", "o/r", "--title", "t", "--body", "b", "--label", "escape", "--assignee", "dev")


def test_agent_trust_opens_a_demotion_pr(tmp_path, monkeypatch):
    from factory.cli import agent_trust

    (tmp_path / "agents.yaml").write_text("agents: []\n")
    scm, pushed = FakeSCM(), []
    monkeypatch.setattr(agent_trust, "get_scm", lambda: type("S", (), {"list_merged_changes": lambda s, d: [], "list_issues": lambda s, *a, **k: [],
                                                                       "open_change": lambda s, *a: scm.open_change(*a)})())
    monkeypatch.setattr(agent_trust, "load_policy", lambda name: {"agents": [{"id": "bot", "trust": "L2"}]})
    monkeypatch.setattr(agent_trust, "policy_dir", lambda: str(tmp_path))
    monkeypatch.setattr(agent_trust, "stats", lambda *a: {"accepted": 3, "escapes": 1, "reverts": 0})
    monkeypatch.setattr(agent_trust, "evaluate", lambda *a: {"action": "demote", "to": "L1", "reasons": ["critical escape"], "gap": []})
    monkeypatch.setattr(agent_trust, "apply_trust", lambda text, *a: text + "# demoted\n")
    monkeypatch.setattr(agent_trust, "push_branch", lambda *a: pushed.append(a))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    agent_trust.main(["--apply", "--open-pr"])
    assert (tmp_path / "agents.yaml").read_text().endswith("# demoted\n")
    assert pushed[0][0].startswith("agent-trust/") and pushed[0][1] == agent_trust.TITLE
    [pr] = scm.changes
    assert pr["labels"] == ["P0"] and "**demote to L1**" in pr["body"]
    assert "| bot | L2 |" in (tmp_path / "summary").read_text()


def test_metrics_report_posts_the_issue(tmp_path, monkeypatch):
    from factory.cli import metrics_report

    scm = FakeSCM()
    scm.list_merged_changes = scm.list_pipeline_runs = lambda since: []
    monkeypatch.setattr(metrics_report, "get_scm", lambda: scm)
    monkeypatch.setattr(metrics_report, "load_policy", lambda name: {"agents": []})
    monkeypatch.setattr(metrics_report, "report", lambda *a, **k: "## Report")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    metrics_report.main(["--issue"])
    [issue] = scm.opened
    assert issue["title"].startswith("Factory metrics, week of ") and issue["body"] == "## Report" and issue["labels"] == ["factory-metrics"]
    assert (tmp_path / "summary").read_text() == "## Report\n"
