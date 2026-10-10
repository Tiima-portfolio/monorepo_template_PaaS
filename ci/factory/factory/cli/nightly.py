"""The nightly full run's reports: every project's tests, not only affected
ones. It reports, never blocks merges.

Usage:
  nightly coverage <metrics.json>   diff-coverage and the ratchet for every
                                    project with tests, then main's metrics
  nightly mutation-summary          each mutation report's score, to the log
                                    and the run summary
  nightly drop-issue                an issue when coverage dropped below main's
Env: GITHUB_SHA, FACTORY_OUT, GITHUB_REPOSITORY, GH_TOKEN.
"""

import math
import os
import sys
from datetime import date
from pathlib import Path

from ..numbers import num
from ..scm import get_scm
from . import diff_coverage, metrics
from .common import append, env, nx_json, out_dir, read_json, write_json


def coverage(metrics_file: str) -> None:
    Path("gate").mkdir(exist_ok=True)
    write_json("gate/gate.json", {"affected": nx_json("show", "projects", "--withTarget=test")}, indent=None)
    # Every project's whole code counts as unchanged: only the ratchet decides.
    env.update({"FACTORY_BASE": "HEAD", "FACTORY_HEAD": "HEAD", "FACTORY_SHA": env.get("GITHUB_SHA") or "",
                "FACTORY_GATE": "gate/gate.json", "FACTORY_METRICS_FILE": metrics_file})
    diff_coverage.main([])
    metrics.main([metrics_file, str(out_dir() / "coverage-totals.json"), env.get("GITHUB_SHA") or ""])


def mutation_line(project: str, report: dict) -> str:
    files = report.get("files") or {}
    statuses = [m.get("status") for f in (files.values() if isinstance(files, dict) else files) for m in (f or {}).get("mutations") or []]
    killed, lived = statuses.count("KILLED"), statuses.count("LIVED")
    if not killed + lived:
        return f"{project}: no mutants"
    return f"{project}: {num(math.floor(killed * 1000 / (killed + lived) + 0.5) / 10)}% of {killed + lived} mutants killed"


def mutation_summary() -> None:
    for root, dirs, files in os.walk("."):
        dirs[:] = sorted(d for d in dirs if d not in ("node_modules", ".git"))
        if Path(root).name == "mutation" and "report.json" in files:
            line = mutation_line(os.path.relpath(Path(root).parent), read_json(Path(root, "report.json")))
            print(line)
            append("GITHUB_STEP_SUMMARY", line + "\n")


def drop_issue() -> None:
    record = read_json(out_dir() / "evidence/coverage-ratchet.json", {})
    if record.get("status") != "fail":
        print("No coverage drops.")
        return
    url = get_scm().open_issue(f"test strength dropped on main ({date.today().isoformat()})",
                               f"The nightly run found coverage below the last recorded value: {record['details']}. "
                               "Affected services' next PRs should restore it.", ["test-adequacy"])
    print(f"Opened {url}")


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "coverage":
        coverage(argv[1] if len(argv) > 1 else "factory-metrics.json")
    elif cmd == "mutation-summary":
        mutation_summary()
    elif cmd == "drop-issue":
        drop_issue()
    else:
        sys.exit("usage: nightly coverage|mutation-summary|drop-issue")
