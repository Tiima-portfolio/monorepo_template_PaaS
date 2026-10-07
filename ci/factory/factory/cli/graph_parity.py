"""Verify step: the Python graph the gate used against the Nx graph.
Writes the graph-parity evidence record. Usage: graph-parity"""

import json
import subprocess
import tempfile
from pathlib import Path

from ..graph import build_graph
from ..parity import parity_problems
from .common import env, write_record


def main(argv):
    head = env.get("FACTORY_HEAD") or "HEAD"
    with tempfile.TemporaryDirectory() as d:
        file = Path(d) / "graph.json"
        run = subprocess.run(["npx", "nx", "graph", f"--file={file}"], capture_output=True, text=True)
        if run.returncode != 0 or not file.exists():
            write_record("graph-parity", "fail", f"nx graph failed: {run.stderr.strip()[-200:]}")
            return 0
        nx = json.loads(file.read_text())["graph"]
    problems = parity_problems(build_graph(head), nx)
    write_record("graph-parity", "fail" if problems else "pass", "; ".join(problems[:10]) if problems else "the Python graph and the Nx graph agree")
