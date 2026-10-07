"""The gate must classify a PR without running anything the PR controls."""

import json
import subprocess
from pathlib import Path

import pytest

from factory.cli import common, gate

POLICY = Path(__file__).resolve().parents[2] / "policy"


def git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=t", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def pr(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")

    def write(path, text):
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)

    write("product/services/catalog/service.yaml", "name: catalog\nowner: team-a\ntoolchains: []\ncriticality: normal\n")
    write("product/services/orders/service.yaml", "name: orders\nowner: team-a\ntoolchains: []\nconsumes: [catalog]\n")
    write("README.md", "x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-qc", "pr")

    def finish(*paths, content="changed\n"):
        for p in paths:
            write(p, content)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "feat: change")
        head = git(repo, "rev-parse", "HEAD")
        for k, v in {"FACTORY_BASE": base, "FACTORY_HEAD": head, "FACTORY_SHA": head, "FACTORY_OUT": str(tmp_path / "out"),
                     "FACTORY_POLICY_DIR": str(POLICY), "GITHUB_EVENT_NAME": "push"}.items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.chdir(repo)
        return json.loads((gate.main([]), (tmp_path / "out/gate.json").read_text())[1])

    # Anything the gate runs through `run` (Nx, gh) would be PR-controlled or external.
    monkeypatch.setattr(common, "run", lambda *a: pytest.fail(f"the gate ran {a}"))
    monkeypatch.setattr(gate, "run", lambda *a: pytest.fail(f"the gate ran {a}"))
    return finish


def test_gate_classifies_without_nx_or_node(pr):
    result = pr("product/services/catalog/main.go")
    assert result["affected"] == ["catalog", "orders"]


def test_a_package_json_change_is_not_executed_and_affects_everything(pr):
    # The review's example: product code plus package.json. The gate only reads it.
    result = pr("product/services/catalog/foo.py", "package.json")
    assert set(result["affected"]) == {"catalog", "orders"}
    assert result["tier"] in {"R1", "R2", "R3"}


def test_gate_flags_a_reference_nobody_declared(pr, tmp_path):
    # catalog starts importing orders, which it never declared. Orders changes would
    # then not rebuild catalog, so the affected set could miss it.
    result = pr("product/services/catalog/client.py", content="from orders import api\n")
    assert "catalog" in result["affected"]
    record = json.loads((tmp_path / "out/evidence/declared-dependencies.json").read_text())
    assert record["status"] == "fail"
    assert "catalog uses orders" in record["details"]
