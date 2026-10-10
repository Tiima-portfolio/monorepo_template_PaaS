#!/usr/bin/env python3
"""Writes the diff-coverage evidence record after the tests ran. Run from the
base branch's copy by the verify job.

Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_SHA, FACTORY_OUT, FACTORY_GATE (gate.json).
"""

import os
import re
from pathlib import Path

from ..coverage import diff_coverage, parse_go_cover, parse_lcov, ratchet, total_coverage
from ..numbers import num
from ..policy import load_policy
from .common import criticality, env, nx_json, out_dir, read_json, to_json, write_record
from .strength import added_code_lines, threshold


def main(argv):
    gate = read_json(env.get("FACTORY_GATE") or "gate/gate.json")
    test_paths = load_policy("risk")["test_paths"]
    floors = load_policy("test-adequacy")["diff_coverage"]

    results = []
    totals = {}
    for name in gate.get("affected") or []:
        project = nx_json("show", "project", name)
        root = project["root"]
        coverage = None
        if Path(root, "coverage/lcov.info").exists():
            coverage = parse_lcov(Path(root, "coverage/lcov.info").read_text())
        elif Path(root, "coverage/cover.out").exists():
            m = re.search(r"^module\s+(\S+)", Path(root, "go.mod").read_text(), re.M)
            coverage = parse_go_cover(Path(root, "coverage/cover.out").read_text(), m.group(1) if m else "")
        if not coverage:
            continue
        # Some tools (cargo llvm-cov) write absolute paths; make them project-relative.
        here = os.path.abspath(root)
        coverage = {os.path.relpath(f, here) if os.path.isabs(f) else f: ls for f, ls in coverage.items()}
        total = total_coverage(coverage)
        if total is not None:
            totals[name] = total
        result = diff_coverage(added_code_lines(root, test_paths), coverage)
        if result["total"] == 0:
            continue
        minimum = num(threshold(floors, criticality(project), root, "diff_coverage"))
        results.append({"name": name, **result, "min": minimum, "ok": result["pct"] >= minimum})

    status = "skipped" if not results else "pass" if all(r["ok"] for r in results) else "fail"

    def describe(r):
        missed = f"; not run: {', '.join(r['uncovered'][:5])}" if r["uncovered"] else ""
        return f"{r['name']} {r['pct']}% of {r['total']} changed line(s), needs {r['min']}%{missed}"

    details = "; ".join(map(describe, results)) if results else "no changed executable lines with coverage"
    write_record("diff-coverage", status, details)
    print(f"diff-coverage: {status} ({details})")

    # Coverage per project, for the ratchet and for main's metrics.
    (out_dir() / "coverage-totals.json").write_text(to_json(totals, indent=None))
    previous = read_json(env.get("FACTORY_METRICS_FILE"), {})
    drops = ratchet(totals, previous)
    ratchet_status = "skipped" if not totals else "fail" if drops else "pass"
    if drops:
        ratchet_details = "; ".join(f"{d['name']} coverage {d['now']}% is below main's {num(d['before'])}%" for d in drops)
    elif totals:
        ratchet_details = ", ".join(f"{n} {p}%" + (f" (main {num(previous[n].get('coverage'))}%)" if previous.get(n) else "") for n, p in totals.items())
    else:
        ratchet_details = "no coverage measured"
    write_record("coverage-ratchet", ratchet_status, ratchet_details)
    print(f"coverage-ratchet: {ratchet_status} ({ratchet_details})")
