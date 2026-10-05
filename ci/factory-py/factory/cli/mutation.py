"""Writes mutation-score evidence from the affected projects' mutation reports
(written by their toolchain's mutation target). Run from the base branch's
copy by the verify job, from risk tier R2 up.

Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_SHA, FACTORY_OUT, FACTORY_GATE.
"""

from pathlib import Path

from ..coverage import diff_mutation
from ..numbers import num
from ..policy import load_policy
from .common import criticality, env, nx_json, read_json, write_record
from .strength import added_code_lines, threshold


def main(argv):
    gate = read_json(env.get("FACTORY_GATE") or "gate/gate.json")
    test_paths = load_policy("risk")["test_paths"]
    floors = load_policy("test-adequacy")["mutation_score"]

    results = []
    for name in gate.get("affected") or []:
        project = nx_json("show", "project", name)
        report = Path(project["root"], "mutation/report.json")
        if not report.exists():
            continue
        r = diff_mutation(added_code_lines(project["root"], test_paths), read_json(report))
        if not r["total"]:
            continue
        minimum = num(threshold(floors, criticality(project), project["root"], "mutation_score"))
        results.append({"name": name, **r, "min": minimum, "ok": r["pct"] >= minimum})

    status = "skipped" if not results else "pass" if all(r["ok"] for r in results) else "fail"

    def describe(r):
        survived = f"; survived: {', '.join(r['survivors'][:5])}" if r["survivors"] else ""
        return f"{r['name']} {r['pct']}% of {r['total']} mutant(s) killed, needs {r['min']}%{survived}"

    details = "; ".join(map(describe, results)) if results else "no mutants on changed lines (or no mutation target for these languages yet)"
    write_record("mutation-score", status, details)
    print(f"mutation-score: {status} ({details})")
