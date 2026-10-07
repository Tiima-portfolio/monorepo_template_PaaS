import subprocess

import pytest

from factory.graph import affected, build_graph


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=a@b", "-c", "user.name=t", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    git(tmp_path, "init", "-q", "-b", "main")

    def write(path, text):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text(text)

    write("internal-tools/toolchains/go/toolchain.yaml", "targets: {}\n")
    write("product/services/orders/service.yaml", "name: orders\ntoolchains: [go]\nconsumes: [catalog]\ncriticality: critical\n")
    write("product/services/catalog/service.yaml", "name: catalog\ntoolchains: [go]\n")
    write("product/services/lone/service.yaml", "name: lone\n")
    write("ci/factory/project.json", '{"name": "factory", "root": "ci/factory", "tags": ["boundary:ci"]}')
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    return write, tmp_path


def test_graph_matches_the_nx_plugin_shape(repo):
    g = build_graph("HEAD")
    assert set(g["nodes"]) == {"toolchain-go", "orders", "catalog", "lone", "factory"}
    assert g["nodes"]["orders"]["data"]["tags"] == ["boundary:product", "toolchain:go", "criticality:critical"]
    assert [e["target"] for e in g["dependencies"]["orders"]] == ["catalog", "toolchain-go"]
    assert g["unresolved"] == []


def test_a_changed_file_affects_its_project_and_dependents(repo):
    g = build_graph("HEAD")
    assert affected(["product/services/catalog/main.go"], g) == ["catalog", "orders"]
    assert affected(["product/services/lone/x.py"], g) == ["lone"]


def test_a_toolchain_change_affects_every_service_using_it(repo):
    g = build_graph("HEAD")
    assert affected(["internal-tools/toolchains/go/go-test.mjs"], g) == ["catalog", "orders", "toolchain-go"]


def test_global_files_affect_everything_and_docs_nothing(repo):
    g = build_graph("HEAD")
    assert affected(["nx.json"], g) == sorted(g["nodes"])
    assert affected(["README.md", "docs/x.md"], g) == []


def test_a_deleted_project_still_counts_as_changed(repo):
    write, path = repo
    base = build_graph("HEAD")
    git(path, "rm", "-rq", "product/services/catalog")
    git(path, "commit", "-qm", "drop")
    head = build_graph("HEAD")
    assert "catalog" not in head["nodes"]
    assert head["unresolved"] == ["orders depends on unknown project catalog"]
    assert affected(["product/services/catalog/service.yaml"], head, base) == ["orders"]


def test_broken_yaml_is_data_not_a_crash(repo):
    write, path = repo
    write("product/services/bad/service.yaml", "name: [unclosed\n")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "bad")
    assert "bad" in build_graph("HEAD")["nodes"]
