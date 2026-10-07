"""The project graph and the affected set, read as data from git objects.

The gate must run no code the PR controls, so it can't ask Nx (which needs
`npm ci` and loads a plugin from the PR). Every project is declared by a
`service.yaml` (or a `project.json`), and the declarations are plain data:
this module reads them with `git show` and builds the same graph the Nx
plugin does (internal-tools/toolchains/plugin.js).

It is conservative on purpose. A project too many costs compute; a project
too few ships a defect. Files outside every project that Nx treats as global
affect everything, and projects deleted by the change still count as changed.
"""

import json
import re
import subprocess

import yaml

SERVICE = re.compile(r"^(product|internal-services|internal-tools)/.+/service\.yaml$")
TOOLCHAIN = re.compile(r"^internal-tools/toolchains/([^/]+)/toolchain\.yaml$")
# Changing one of these can change every project's targets or inputs.
GLOBAL_FILES = ("nx.json", "package.json", "package-lock.json", ".node-version", "internal-tools/toolchains/plugin.js")


def _show(ref: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _tree(ref: str) -> list[str]:
    out = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", ref], check=True, capture_output=True, text=True).stdout
    return [f for f in out.split("\0") if f]


def _yaml(ref: str, path: str) -> dict:
    try:
        data = yaml.safe_load(_show(ref, path) or "")
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def build_graph(ref: str, tree: list[str] | None = None) -> dict:
    """Nx-shaped graph ({nodes, dependencies}) of the projects at a commit.
    `unresolved` lists dependencies on projects that don't exist."""
    tree = tree if tree is not None else _tree(ref)
    nodes: dict[str, dict] = {}
    deps: dict[str, list] = {}

    def add(name, root, tags, implicit):
        nodes[name] = {"name": name, "type": "lib", "data": {"root": root, "tags": tags}}
        deps[name] = [{"source": name, "target": t, "type": "implicit"} for t in implicit]

    toolchains = {m.group(1) for f in tree if (m := TOOLCHAIN.match(f))}
    for f in sorted(tree):
        root = f.rsplit("/", 1)[0]
        if TOOLCHAIN.match(f):
            add(f"toolchain-{root.rsplit('/', 1)[1]}", root, ["boundary:internal-tools", "build-tool"], [])
        elif SERVICE.match(f):
            s = _yaml(ref, f)
            used = [t for t in s.get("toolchains") or [] if isinstance(t, str)]
            tags = [f"boundary:{root.split('/')[0]}", *(f"toolchain:{t}" for t in used),
                    *([f"criticality:{s['criticality']}"] if s.get("criticality") else [])]
            implicit = [*(s.get("dependsOn") or []), *(s.get("consumes") or []), *(f"toolchain-{t}" for t in used if t in toolchains)]
            add(s.get("name") or root.rsplit("/", 1)[1], root, tags, implicit)
        elif f.endswith("/project.json") and f.count("/") >= 1:
            try:
                p = json.loads(_show(ref, f) or "{}")
            except json.JSONDecodeError:
                continue
            if isinstance(p, dict) and p.get("name") and root not in {n["data"]["root"] for n in nodes.values()}:
                add(p["name"], p.get("root") or root, list(p.get("tags") or []), list(p.get("implicitDependencies") or []))
    unresolved = [f"{src} depends on unknown project {e['target']}" for src, es in deps.items() for e in es if e["target"] not in nodes]
    return {"nodes": nodes, "dependencies": deps, "unresolved": unresolved}


def _owner(file: str, graph: dict) -> str | None:
    """The project whose root is the deepest folder containing the file."""
    best = None
    for name, n in graph["nodes"].items():
        root = n["data"]["root"]
        if file.startswith(root + "/") and (best is None or len(root) > len(graph["nodes"][best]["data"]["root"])):
            best = name
    return best


def affected(files: list[str], head: dict, base: dict | None = None) -> list[str]:
    """Names of the projects at head that the changed files affect: the
    projects owning them, any that the change deleted, and everything that
    depends on those, directly or not. A global file affects every project."""
    if any(f in GLOBAL_FILES for f in files):
        return sorted(head["nodes"])
    seeds = {o for f in files for g in (head, base) if g and (o := _owner(f, g))}
    reverse: dict[str, set] = {}
    for g in (head, base):
        for src, es in ((g or {}).get("dependencies") or {}).items():
            for e in es:
                reverse.setdefault(e["target"], set()).add(src)
    seen, todo = set(), list(seeds)
    while todo:
        n = todo.pop()
        if n not in seen:
            seen.add(n)
            todo.extend(reverse.get(n, ()))
    return sorted(n for n in seen if n in head["nodes"])


def owners_of(files: list[str], graph: dict) -> list[str]:
    """The projects that own at least one of the files."""
    return sorted({o for f in files if (o := _owner(f, graph))})


def project_files(ref: str, root: str, limit: int = 1500, max_bytes: int = 200_000) -> dict[str, str]:
    """A project's text files (relative path -> text) at a commit, read as data."""
    out = {}
    for f in subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", ref, "--", root], check=True, capture_output=True, text=True).stdout.split("\0"):
        if not f or len(out) >= limit:
            continue
        text = _show(ref, f)
        if text is not None and len(text) <= max_bytes and "\0" not in text:
            out[f[len(root) + 1:]] = text
    return out
