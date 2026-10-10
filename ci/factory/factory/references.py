#!/usr/bin/env python3
"""Real references between projects, to compare with the declared graph.

The affected set is only as good as the declared dependencies (`dependsOn`,
`consumes` in service.yaml). A reference the code makes but nobody declared is
a false negative: the dependent project is not rebuilt when the other changes.
This finds such references by reading files as text, never by running them:

- paths into another project (`../catalog/...`, `product/services/catalog/...`),
  which covers Dockerfile COPY, OpenAPI and protobuf paths, go.mod replace,
  `go:generate` and file: dependencies;
- package manifests naming a sibling (package.json, pyproject.toml, go.mod);
- Python imports, including `import_module("...")`, of a sibling's package;
- runtime consumers: `http://<sibling>` addresses;
- a Helm chart's image repository naming a sibling.

It is deliberately noisy in one direction. A reference too many is reported
for review; a reference too few is a hole in the blast radius.
"""

import json
import posixpath
import re

REL_PATH = re.compile(r"(?<![\w.])((?:\.\./)+[\w@.\-/]+)")
PY_IMPORT = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", re.M)
PY_DYNAMIC = re.compile(r"""(?:import_module|__import__)\(\s*['"]([A-Za-z_]\w*)""")
URL_HOST = re.compile(r"""\b[a-z][a-z0-9+.-]*://([a-z0-9][a-z0-9-]*)\b""")
HELM_IMAGE = re.compile(r"(?:repository|image):\s*['\"]?[\w.:/-]*?/([\w-]+)(?=[:@'\"\s]|$)")
PEP503 = re.compile(r"[-_.]+")


def _norm(name: str) -> str:
    return PEP503.sub("-", name).lower()


def _deps_of_manifest(path: str, text: str) -> set[str]:
    """Names a package manifest depends on."""
    base = path.rsplit("/", 1)[-1]
    names: set[str] = set()
    if base == "package.json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return names
        for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            names |= {n.rsplit("/", 1)[-1] for n in (data.get(key) or {})}
    elif base == "pyproject.toml":
        for m in re.finditer(r"""['"]([A-Za-z][\w.-]*)\s*(?:[<>=!~\[;@ ]|['"])""", text):
            names.add(m.group(1))
        names |= set(re.findall(r"^([A-Za-z][\w.-]*)\s*=\s*\{\s*(?:workspace|path)", text, re.M))
    elif base == "go.mod":
        names |= {m.rsplit("/", 1)[-1] for m in re.findall(r"^\s*(?:require\s+)?([\w.-]+(?:/[\w.-]+)+)\s+v", text, re.M)}
    return names


def references(project: str, root: str, files: dict[str, str], roots: dict[str, str]) -> list[dict]:
    """References from one project's files (relative path -> text) to other
    projects. `roots` maps every project name to its root."""
    others = {n: r for n, r in roots.items() if n != project and not n.startswith("toolchain-")}
    by_norm = {_norm(n): n for n in others}
    found: dict[tuple, dict] = {}

    def add(target, file, kind):
        found.setdefault((target, file, kind), {"source": project, "target": target, "file": file, "kind": kind})

    def owner_of(path):
        hit = [n for n, r in others.items() if path == r or path.startswith(r + "/")]
        return max(hit, key=lambda n: len(others[n])) if hit else None

    for rel, text in files.items():
        full = f"{root}/{rel}"
        for m in REL_PATH.finditer(text):
            target = owner_of(posixpath.normpath(posixpath.join(posixpath.dirname(full), m.group(1))))
            if target:
                add(target, rel, "path")
        for name, r in others.items():
            if f"{r}/" in text:
                add(name, rel, "path")
        for dep in _deps_of_manifest(rel, text):
            if _norm(dep) in by_norm:
                add(by_norm[_norm(dep)], rel, "manifest")
        if rel.endswith((".py", ".pyi")):
            for mod in [*PY_IMPORT.findall(text), *PY_DYNAMIC.findall(text)]:
                if _norm(mod) in by_norm:
                    add(by_norm[_norm(mod)], rel, "import")
        if rel.endswith((".go", ".ts", ".js", ".mjs", ".rs", ".sh", ".yaml", ".yml", ".json", ".toml", ".env", ".properties")):
            for host in URL_HOST.findall(text):
                if host in others:
                    add(host, rel, "runtime")
        if rel.rsplit("/", 1)[-1].startswith("values") or "/templates/" in f"/{rel}":
            for image in HELM_IMAGE.findall(text):
                if image in others:
                    add(image, rel, "image")
    return list(found.values())


def _closure(name: str, deps: dict) -> set[str]:
    seen, todo = set(), [name]
    while todo:
        for e in deps.get(todo.pop(), []):
            if e["target"] not in seen:
                seen.add(e["target"])
                todo.append(e["target"])
    return seen


def undeclared(graph: dict, project_files: dict[str, dict[str, str]]) -> list[dict]:
    """References not covered by the declared graph. project_files maps a
    project name to its files (relative path -> text)."""
    roots = {n: v["data"]["root"] for n, v in graph["nodes"].items()}
    out = []
    for name, files in project_files.items():
        declared = _closure(name, graph["dependencies"])
        out += [r for r in references(name, roots[name], files, roots) if r["target"] not in declared]
    return sorted(out, key=lambda r: (r["source"], r["target"], r["file"], r["kind"]))
