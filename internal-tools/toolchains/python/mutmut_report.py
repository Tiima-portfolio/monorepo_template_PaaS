"""Converts mutmut's results into the factory's mutation/report.json.

mutmut names mutants after the function it mutated (pkg.mod.x_func__mutmut_1,
or pkg.mod.xǁClassǁmethod__mutmut_1), so each mutant spans its function's
lines.
"""

import ast
import json
import pathlib
import re
import subprocess

STATUS = {"killed": "KILLED", "timeout": "KILLED", "survived": "LIVED", "no tests": "LIVED"}

out = subprocess.run(["mutmut", "results", "--all", "true"], capture_output=True, text=True).stdout
spans = {}


def span(module: str, name: str):
    if (module, name) in spans:
        return spans[(module, name)]
    base = pathlib.Path("src", *module.split("."))
    path = base.with_suffix(".py") if base.with_suffix(".py").exists() else base / "__init__.py"
    found = None
    if path.exists():
        parts = name.split("ǁ")
        tree = ast.parse(path.read_text())
        nodes = tree.body
        if len(parts) == 3:  # xǁClassǁmethod
            cls = next((n for n in nodes if isinstance(n, ast.ClassDef) and n.name == parts[1]), None)
            nodes, target = (cls.body if cls else []), parts[2]
        else:
            target = name[2:]  # x_func
        fn = next((n for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == target), None)
        if fn:
            found = (str(path), fn.lineno, fn.end_lineno)
    spans[(module, name)] = found
    return found


files = {}
for line in out.splitlines():
    m = re.match(r"\s*(.+)\.(x[^.]+?)__mutmut_\d+: (.+)$", line)
    if not m or m.group(3).strip() not in STATUS:
        continue
    where = span(m.group(1), m.group(2))
    if not where:
        continue
    file, start, end = where
    files.setdefault(file, []).append({"type": m.group(2), "line": start, "end_line": end, "status": STATUS[m.group(3).strip()]})

pathlib.Path("mutation").mkdir(exist_ok=True)
report = {"tool": "mutmut", "files": [{"file_name": f, "mutations": ms} for f, ms in files.items()]}
pathlib.Path("mutation/report.json").write_text(json.dumps(report, indent=2))
