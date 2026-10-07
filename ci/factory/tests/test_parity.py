from factory.parity import parity_problems


def g(nodes, **deps):
    return {"nodes": {n: {} for n in nodes}, "dependencies": {n: [{"target": t} for t in deps.get(n, [])] for n in nodes}}


def test_equal_graphs_agree():
    assert parity_problems(g(["a", "b"], a=["b"]), g(["a", "b"], a=["b"])) == []


def test_an_edge_only_nx_found_is_reported():
    p = parity_problems(g(["a", "b"]), g(["a", "b"], a=["b"]))
    assert p == ["a -> b is only in the Nx graph (the declarations miss a dependency Nx found)"]


def test_a_project_missing_on_either_side_is_reported():
    assert parity_problems(g(["a"]), g(["a", "b"])) == ["project b is only in the Nx graph"]
    assert parity_problems(g(["a", "b"]), g(["a"])) == ["project b is only in the Python graph"]


def test_external_packages_are_ignored():
    assert parity_problems(g(["a"], a=["npm:left-pad"]), g(["a"])) == []
