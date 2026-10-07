"""The graph is a safety property: a project missing from the blast radius
ships a defect. These are deliberately awkward cases, each in three forms:
the reference is found when undeclared, it is quiet once declared, and the
declared graph then expands the blast radius to the consumer."""

import pytest

from factory.graph import affected
from factory.references import undeclared

ROOTS = {"consumer": "product/services/consumer", "catalog": "product/services/catalog", "shared": "product/libs/shared"}


def graph(declared=()):
    nodes = {n: {"name": n, "data": {"root": r, "tags": []}} for n, r in ROOTS.items()}
    deps = {n: [] for n in nodes}
    deps["consumer"] = [{"source": "consumer", "target": t, "type": "implicit"} for t in declared]
    return {"nodes": nodes, "dependencies": deps, "unresolved": []}


CASES = {
    "python import": ("src/app.py", "import json\nfrom catalog import prices\n"),
    "python dynamic import": ("src/plugins.py", "mod = importlib.import_module('catalog.plugin')\n"),
    "python dynamic __import__": ("src/plugins.py", "__import__('catalog')\n"),
    "go replace": ("go.mod", "module x\nrequire example.com/catalog v1.0.0\nreplace example.com/catalog => ../catalog\n"),
    "go generate from a sibling": ("gen.go", "//go:generate protoc --go_out=. ../catalog/api/catalog.proto\n"),
    "node workspace dependency": ("package.json", '{"dependencies": {"@org/catalog": "workspace:*"}}'),
    "node file dependency": ("package.json", '{"dependencies": {"x": "file:../catalog"}}'),
    "pyproject dependency": ("pyproject.toml", '[project]\ndependencies = ["requests>=2", "catalog>=0.1"]\n'),
    "pyproject uv workspace source": ("pyproject.toml", "[tool.uv.sources]\ncatalog = { workspace = true }\n"),
    "openapi consumer": ("api/client.yaml", "$ref: '../../catalog/api/openapi.yaml#/components/Item'\n"),
    "protobuf import": ("api/x.proto", 'import "../../catalog/api/catalog.proto";\n'),
    "container COPY path": ("Dockerfile", "FROM scratch\nCOPY product/services/catalog/dist /app\n"),
    "relative container COPY": ("Dockerfile", "COPY ../catalog/dist /app\n"),
    "helm image": ("values.yaml", "image:\n  repository: ghcr.io/org/repo/catalog\n"),
    "runtime consumes": ("src/client.ts", 'const url = "http://catalog:8080/items";\n'),
}


@pytest.mark.parametrize("name", CASES)
def test_an_undeclared_reference_is_found(name):
    file, text = CASES[name]
    found = undeclared(graph(), {"consumer": {file: text}})
    assert {(r["source"], r["target"]) for r in found} == {("consumer", "catalog")}, found


@pytest.mark.parametrize("name", CASES)
def test_a_declared_reference_is_quiet_and_widens_the_blast_radius(name):
    file, text = CASES[name]
    g = graph(declared=["catalog"])
    assert undeclared(g, {"consumer": {file: text}}) == []
    assert affected(["product/services/catalog/anything.go"], g) == ["catalog", "consumer"]


@pytest.mark.parametrize("name", CASES)
def test_removing_the_declaration_is_caught(name):
    # Mutation: with and without the edge, the same code must flip from quiet to flagged.
    file, text = CASES[name]
    files = {"consumer": {file: text}}
    assert undeclared(graph(declared=["catalog"]), files) == []
    assert undeclared(graph(declared=[]), files) != []


def test_a_transitive_declaration_covers_the_reference():
    g = graph()
    g["dependencies"]["consumer"] = [{"source": "consumer", "target": "shared", "type": "implicit"}]
    g["dependencies"]["shared"] = [{"source": "shared", "target": "catalog", "type": "implicit"}]
    assert undeclared(g, {"consumer": {"a.py": "import catalog"}}) == []
    assert affected(["product/services/catalog/x.py"], g) == ["catalog", "consumer", "shared"]


def test_shared_generated_code_reaches_every_consumer():
    g = graph(declared=["shared"])
    g["dependencies"]["catalog"] = [{"source": "catalog", "target": "shared", "type": "implicit"}]
    assert affected(["product/libs/shared/generated/api.go"], g) == ["catalog", "consumer", "shared"]


def test_ordinary_code_is_not_flagged():
    files = {"consumer": {"main.go": "package main\nimport \"fmt\"\nfunc main() { fmt.Println(\"catalog\") }\n",
                          "README.md": "Talks to the catalog service.\n", "src/a.py": "import os, sys\n"}}
    assert undeclared(graph(), files) == []


def test_a_path_that_leaves_its_own_project_but_hits_nothing_is_ignored():
    assert undeclared(graph(), {"consumer": {"a.yaml": "x: ../../nowhere/else.yaml\n"}}) == []


def test_a_project_does_not_reference_itself():
    assert undeclared(graph(), {"catalog": {"a.py": "import catalog\n", "b.yaml": "x: ../catalog/y\n"}}) == []
