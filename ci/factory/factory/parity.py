"""Compares the Python graph with the one Nx built, so they can't drift apart."""


def parity_problems(python_graph: dict, nx_graph: dict) -> list[str]:
    """Both graphs are {nodes, dependencies}. Nx also reports static imports and
    external packages; only edges between workspace projects are compared, and
    Nx may know more edges than the declarations (that costs nothing). Anything
    the Python graph has that Nx lacks, or any edge Nx has that Python lacks,
    is a difference worth a look."""
    problems = []
    mine, theirs = set(python_graph["nodes"]), set(nx_graph["nodes"])
    problems += [f"project {n} is only in the Python graph" for n in sorted(mine - theirs)]
    problems += [f"project {n} is only in the Nx graph" for n in sorted(theirs - mine)]

    def edges(g, nodes):
        return {(s, e["target"]) for s, es in g["dependencies"].items() for e in es if s in nodes and e["target"] in nodes}

    common = mine & theirs
    a, b = edges(python_graph, common), edges(nx_graph, common)
    problems += [f"{s} -> {t} is only in the Python graph" for s, t in sorted(a - b)]
    problems += [f"{s} -> {t} is only in the Nx graph (the declarations miss a dependency Nx found)" for s, t in sorted(b - a)]
    return problems
