#!/usr/bin/env python3
"""Flaky test handling, per project test target.

A failing test target is retried once. A pass on the retry only makes it a
suspect: the factory reruns it FLAKE_RERUNS times on the same commit, and it
is a confirmed flake only if those runs both pass and fail. A quarantine
lasts at most 5 working days; while it lasts the target must still pass at
least one of three runs, so a broken test can't hide behind it.
"""

import json
import re
from datetime import datetime, timedelta, timezone

from .budgets import parse_time

FLAKE_RERUNS = 20
QUARANTINE_WORKING_DAYS = 5
QUARANTINE_ATTEMPTS = 3


def working_days_between(start: datetime, end: datetime) -> int:
    days = 0
    d = start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5 and d <= end:
            days += 1
    return days


def active_quarantine(issues, now: datetime | None = None) -> dict:
    """issues: [{title, created_at}] open issues labelled "quarantine", titled
    "quarantine: <project>:<test>" (or "<project>:test" for a whole project).
    Returns {project: set(tests)} still in quarantine."""
    now = now or datetime.now(timezone.utc)
    active = {}
    for i in issues:
        m = re.match(r"^quarantine: ([^:]+):(.+)$", i["title"])
        if not m or working_days_between(parse_time(i["created_at"]), now) >= QUARANTINE_WORKING_DAYS:
            continue
        active.setdefault(m.group(1), set()).add(m.group(2))
    return active


def parse_junit(xml: str) -> dict:
    """Per-test results from JUnit XML: {test id: "pass" | "fail"}."""
    results = {}
    for m in re.finditer(r"<testcase\b([^>]*?)(/>|>(.*?)</testcase>)", xml, re.DOTALL):
        def attr(k):
            a = re.search(f'{k}="([^"]*)"', m.group(1))
            return a.group(1) if a else None

        test_id = ".".join(x for x in (attr("classname"), attr("name")) if x)
        body = m.group(3) or ""
        if re.search(r"<skipped\b", body):
            continue
        failed = re.search(r"<(failure|error)\b", body)
        results[test_id] = "fail" if failed or results.get(test_id) == "fail" else "pass"
    return results


def parse_go_json(text: str) -> dict:
    """Per-test results from Go's JSON test events."""
    results = {}
    for line in text.split("\n"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("Test") and e.get("Action") in ("pass", "fail"):
            results[f"{e.get('Package')}.{e['Test']}"] = e["Action"]
    return results


def classify_tests(runs, quarantined=frozenset()) -> dict:
    """runs: [{test: status}] in order. Verdicts for the tests that failed in
    the first run."""
    verdicts = {}
    for test, status in runs[0].items():
        if status != "fail":
            continue
        later = [r[test] for r in runs[1:] if r.get(test)]
        if test in quarantined or "test" in quarantined:
            verdicts[test] = "pass-quarantined" if "pass" in later[: QUARANTINE_ATTEMPTS - 1] else "fail"
        elif not later or later[0] != "pass":
            verdicts[test] = "fail"
        else:
            confirm = later[1:]
            verdicts[test] = "flaky" if "pass" in confirm and "fail" in confirm else "pass-on-retry"
    return verdicts


def classify(runs, quarantined=False) -> str:
    """runs: booleans (True = passed), in order. One project's results."""
    if runs and runs[0]:
        return "pass"
    if quarantined:
        return "pass-quarantined" if any(runs[:QUARANTINE_ATTEMPTS]) else "fail"
    if len(runs) < 2 or not runs[1]:
        return "fail"
    confirm = runs[2:]
    return "flaky" if any(confirm) and not all(confirm) else "pass-on-retry"
