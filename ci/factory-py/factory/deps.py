"""Dependency rules on the Nx project graph, from ci/policy/invariants.yaml."""

from .globs import matches_any
from .policy import load_policy


def _area(root: str) -> str:
    return root.split("/")[0]


def check_dependencies(graph: dict, policy: dict | None = None) -> list[str]:
    """graph: Nx graph JSON ({nodes, dependencies}). Returns violations."""
    policy = policy or load_policy("invariants")
    problems = []

    def root(name):
        return ((graph["nodes"].get(name) or {}).get("data") or {}).get("root")

    for source, edges in graph["dependencies"].items():
        if not root(source):
            continue
        frm = _area(root(source))
        for edge in edges:
            target = edge["target"]
            if not root(target):
                continue  # external packages
            if matches_any(target, policy.get("build_tools") or []):
                continue
            to = _area(root(target))
            if to not in (policy["dependencies"].get(frm) or []):
                problems.append(f"{source} ({frm}) may not depend on {target} ({to})")
            elif frm != to and edge.get("type") == "static":
                problems.append(f"{source} imports {target}'s code across boundaries; depend on its published contract or release instead")
    for cycle in _find_cycles(graph, policy["no_cycles"]):
        problems.append(f"dependency cycle: {' -> '.join(cycle)}")
    return problems


def _find_cycles(graph, areas) -> list[list[str]]:
    def in_scope(n):
        return n in graph["nodes"] and _area(graph["nodes"][n]["data"]["root"]) in areas

    state = {}
    stack = []
    cycles = []

    def visit(n):
        state[n] = "open"
        stack.append(n)
        for edge in graph["dependencies"].get(n) or []:
            t = edge["target"]
            if not in_scope(t):
                continue
            if state.get(t) == "open":
                cycles.append(stack[stack.index(t) :] + [t])
            elif not state.get(t):
                visit(t)
        stack.pop()
        state[n] = "done"

    for n in graph["nodes"]:
        if in_scope(n) and not state.get(n):
            visit(n)
    return cycles
