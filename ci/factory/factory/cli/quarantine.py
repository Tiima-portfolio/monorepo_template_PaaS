#!/usr/bin/env python3
"""Flaky test quarantine, through the SCM adapter.

Usage:
  quarantine list <out.json>       open quarantine issues as [{title, created_at}],
                                   for the gate and the test run
  quarantine open <flaky.json>     an issue for each newly confirmed flaky test
Env: GITHUB_REPOSITORY, GH_TOKEN, FACTORY_SHA.
"""

import sys

from ..scm import get_scm
from .common import env, read_json, write_json

LABEL = "quarantine"


def open_issues(flaky: list[str], scm) -> list[str]:
    """Opens an issue per flaky test that has none open; returns the tests."""
    open_titles = {i["title"] for i in scm.list_issues([LABEL])}
    opened = []
    for test in flaky:
        title = f"quarantine: {test}"
        if title in open_titles:
            continue
        scm.open_issue(title, f"The test {test} failed and then passed on the same commit, and 20 reruns both passed and failed, so it "
                       "is flaky. It is quarantined for at most 5 working days: until then its failures only block if it fails three "
                       "runs in a row, and its project's PRs are one risk tier up. Fix or remove the flaky test, then close this issue. "
                       f"Found on {env.get('FACTORY_SHA')}.", [LABEL])
        open_titles.add(title)
        opened.append(test)
        print(f"Quarantined {test}")
    return opened


def main(argv):
    cmd, path = (argv + ["", ""])[:2]
    if cmd == "list":
        write_json(path, [{"title": i["title"], "created_at": i["createdAt"]} for i in get_scm().list_issues([LABEL])], indent=None)
    elif cmd == "open":
        flaky = read_json(path)
        if flaky:
            open_issues(flaky, get_scm())
    else:
        sys.exit("usage: quarantine list|open <file>")
