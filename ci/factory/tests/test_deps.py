#!/usr/bin/env python3
import re

from factory.contracts import contract_problems
from factory.deps import check_dependencies


def node(root):
    return {"data": {"root": root}}


def graph(**deps):
    return {
        "nodes": {"orders": node("product/services/orders"), "catalog": node("product/services/catalog"),
                  "sim": node("internal-services/sim"), "lint": node("internal-tools/lint")},
        "dependencies": {"orders": [], "catalog": [], "sim": [], "lint": [], **deps},
    }


def test_allowed_directions_pass():
    assert check_dependencies(graph(
        orders=[{"target": "catalog", "type": "static"}],
        sim=[{"target": "orders", "type": "implicit"}],
        lint=[{"target": "orders", "type": "implicit"}],
    )) == []


def test_product_may_never_depend_on_an_internal_tool():
    p = check_dependencies(graph(orders=[{"target": "lint", "type": "implicit"}]))
    assert "orders (product) may not depend on lint (internal-tools)" in p[0]


def test_cross_boundary_source_imports_are_refused():
    p = check_dependencies(graph(sim=[{"target": "orders", "type": "static"}]))
    assert "imports orders's code across boundaries" in p[0]


def test_cycles_are_refused():
    p = check_dependencies(graph(orders=[{"target": "catalog", "type": "implicit"}], catalog=[{"target": "orders", "type": "implicit"}]))
    assert any(re.search(r"cycle: (orders -> catalog -> orders|catalog -> orders -> catalog)", x) for x in p)


def test_external_packages_are_ignored():
    assert check_dependencies(graph(orders=[{"target": "npm:yaml", "type": "static"}])) == []


def test_build_tools_may_be_depended_on_from_anywhere():
    g = graph(orders=[{"target": "toolchain-go", "type": "implicit"}])
    g["nodes"]["toolchain-go"] = node("internal-tools/toolchains/go")
    g["dependencies"]["toolchain-go"] = []
    assert check_dependencies(g) == []


def test_declared_contracts_and_consumed_providers_are_covered():
    assert contract_problems([{
        "name": "orders", "service": {"contract": ["api/openapi.yaml"], "consumes": ["catalog"]},
        "files": ["api/openapi.yaml", "contracts/catalog/catalog_contract_test.go"],
    }]) == []


def test_a_missing_contract_file_or_consumer_test_is_reported():
    p = contract_problems([{"name": "orders", "service": {"contract": ["api/openapi.yaml"], "consumes": ["catalog"]}, "files": ["main.go"]}])
    assert len(p) == 2
    assert "no contract test under contracts/catalog/" in p[1]
