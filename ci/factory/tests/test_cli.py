import json
import subprocess
import sys
from pathlib import Path

from factory.cli import admission, verify_record

ROOT = Path(__file__).resolve().parents[1]


def test_run_py_lists_the_commands():
    r = subprocess.run([sys.executable, str(ROOT / "run.py")], capture_output=True, text=True)
    assert r.returncode != 0
    assert "gate|admission" in r.stderr


def test_verify_record(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_OUT", str(tmp_path))
    monkeypatch.setenv("FACTORY_SHA", "abc")
    monkeypatch.setenv("FACTORY_AFFECTED", "2")
    verify_record.main(["build", "1", "nx affected -t build"])
    rec = json.loads((tmp_path / "evidence/build.json").read_text())
    assert rec == {"check": "build", "status": "fail", "sha": "abc", "details": "nx affected -t build"}
    monkeypatch.setenv("FACTORY_AFFECTED", "0")
    verify_record.main(["build", "1"])
    assert json.loads((tmp_path / "evidence/build.json").read_text())["status"] == "skipped"


def test_admission_writes_the_decision_and_bundle(tmp_path, monkeypatch):
    gate_dir = tmp_path / "in/factory-gate"
    (gate_dir / "evidence").mkdir(parents=True)
    required = [{"name": "boundary", "mode": "enforce", "about": "x"}]
    gate = {"sha": "s1", "tier": "R0", "reasons": [], "required": required, "affected": [], "approvals": []}
    (gate_dir / "gate.json").write_text(json.dumps(gate))
    (gate_dir / "evidence/boundary.json").write_text(json.dumps({"check": "boundary", "status": "pass", "sha": "s1", "details": "ok"}))
    for var in ("FACTORY_JOBS_FILE", "FACTORY_RUN_FILE", "FACTORY_APPROVERS_FILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FACTORY_IN", str(tmp_path / "in"))
    monkeypatch.setenv("FACTORY_OUT", str(tmp_path))
    assert admission.main([]) == 0
    assert json.loads((tmp_path / "admission.json").read_text())["allowed"] is True
    bundle = json.loads((tmp_path / "bundle.json").read_text())
    assert len(bundle["records"][0]["digest"]) == 64
    assert bundle["decided_at"].endswith("Z")


def test_queue_controller_skips_a_pr_github_refuses(monkeypatch, capsys):
    from factory.cli import queue

    def pr(id_, number):
        return {"id": id_, "number": number, "author": {"login": "dev"}, "labels": {"nodes": []},
                "files": {"nodes": []}, "createdAt": "2026-10-06T00:00:00Z", "isInMergeQueue": False,
                "commits": {"nodes": []}}

    calls = []

    def gql(query, **variables):
        if query == queue.QUERY:
            return {"data": {"repository": {"pullRequests": {"nodes": [pr("A", 1), pr("B", 2)]}, "mergeQueue": None}}}
        calls.append(variables["id"])
        if variables["id"] == "A":
            raise subprocess.CalledProcessError(1, "gh", stderr="Pull request is not mergeable")
        return {}

    monkeypatch.setattr(queue, "gql", gql)
    monkeypatch.setattr(queue, "env", {"GITHUB_REPOSITORY": "o/r"})
    picks = [{"number": 1, "priority": "P3", "jump": False}, {"number": 2, "priority": "P3", "jump": False}]
    monkeypatch.setattr(queue, "select_to_enqueue", lambda *a, **k: {"picks": picks, "waiting": []})
    queue.main([])
    out = capsys.readouterr().out
    assert calls == ["A", "B"]
    assert "#1 not enqueued: Pull request is not mergeable" in out
    assert "#2 enqueued as P3" in out
