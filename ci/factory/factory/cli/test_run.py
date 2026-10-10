#!/usr/bin/env python3
"""Runs the affected test targets with flaky-test handling and writes the
unit-tests evidence record plus flaky.json. Run from the base branch's copy
by the verify job.

Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_SHA, FACTORY_OUT, FACTORY_AFFECTED,
FACTORY_QUARANTINE_FILE (JSON list of open quarantine issues).
"""

from pathlib import Path

from ..flaky import FLAKE_RERUNS, QUARANTINE_ATTEMPTS, active_quarantine, classify, classify_tests, parse_go_json, parse_junit
from .common import env, nx, nx_json, out_dir, read_json, to_json, write_record


def write(status, details):
    write_record("unit-tests", status, details)
    print(f"unit-tests: {status} ({details})")


def test_results(project: str) -> dict:
    """Per-test results from the project's test-results/ folder, if it writes them."""
    folder = Path(nx_json("show", "project", project)["root"], "test-results")
    results = {}
    if not folder.exists():
        return results
    for f in sorted(folder.iterdir()):
        text = f.read_text(errors="replace")
        results.update(parse_junit(text) if f.suffix == ".xml" else parse_go_json(text) if f.suffix == ".json" else {})
    return results


def main(argv):
    if int(env.get("FACTORY_AFFECTED") or "0") == 0:
        write("skipped", "nothing affected")
        return 0
    rng = [f"--base={env.get('FACTORY_BASE')}", f"--head={env.get('FACTORY_HEAD')}"]
    flaky_file = out_dir() / "flaky.json"
    if nx("affected", "-t", "test", *rng):
        write("pass", "nx affected -t test")
        flaky_file.write_text("[]")
        return 0

    # A project the PR deletes still counts as affected, but has nothing to run.
    existing = set(nx_json("show", "projects", "--withTarget=test"))
    projects = [p for p in nx_json("show", "projects", "--affected", "--withTarget=test", *rng) if p in existing]
    quarantine = active_quarantine(read_json(env.get("FACTORY_QUARANTINE_FILE"), []))

    def rerun(p):
        return nx("run", f"{p}:test", "--skip-nx-cache")

    results = {}
    flaky_tests = []
    for p in projects:
        if nx("run", f"{p}:test"):
            results[p] = "pass"
            continue
        quarantined = quarantine.get(p, set())
        per_test = [test_results(p)]
        failed_tests = [t for t, s in per_test[0].items() if s == "fail"]
        if failed_tests:
            # Per test: rerun, and confirm suspects with more reruns.
            all_quarantined = all(t in quarantined or "test" in quarantined for t in failed_tests)
            for _ in range(QUARANTINE_ATTEMPTS - 1 if all_quarantined else 1):
                rerun(p)
                per_test.append(test_results(p))
            if not all_quarantined and any(per_test[1].get(t) == "pass" for t in failed_tests):
                for _ in range(FLAKE_RERUNS):
                    rerun(p)
                    per_test.append(test_results(p))
            verdicts = classify_tests(per_test, quarantined)
            flaky_tests += [f"{p}:{t}" for t, v in verdicts.items() if v == "flaky"]
            bad = [t for t, v in verdicts.items() if v == "fail"]
            results[p] = f"fail ({', '.join(bad[:3])})" if bad else "flaky" if "flaky" in verdicts.values() else "pass-on-retry"
            continue
        # No per-test report: whole-project handling.
        runs = [False]
        q = "test" in quarantined
        for _ in range(QUARANTINE_ATTEMPTS - 1 if q else 1):
            if any(runs):
                break
            runs.append(rerun(p))
        if not q and runs[1]:
            runs += [rerun(p) for _ in range(FLAKE_RERUNS)]
        results[p] = classify(runs, quarantined=q)
        if results[p] == "flaky":
            flaky_tests.append(f"{p}:test")

    flaky_file.write_text(to_json(flaky_tests, indent=None))
    failed = [p for p, r in results.items() if r.startswith("fail")]
    notes = ", ".join(f"{p}: {r}" for p, r in results.items() if r != "pass")
    # A confirmed flake doesn't block this PR; it is quarantined instead.
    write("fail" if failed else "pass", notes or "all passed")
    return 0
