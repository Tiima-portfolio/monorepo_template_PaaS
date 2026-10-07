"""Fetches last week's PRs, issues and factory runs and prints the report.
Env: GITHUB_REPOSITORY, GH_TOKEN, FACTORY_METRICS_DAYS (default 7)."""

import re
from datetime import datetime, timedelta, timezone

from ..metrics_report import report
from ..policy import load_policy
from ..scm import get_scm
from .common import env


def iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main(argv):
    now = datetime.now(timezone.utc)
    until = iso(now)
    since = iso(now - timedelta(days=float(env.get("FACTORY_METRICS_DAYS") or 7)))
    scm = get_scm()
    prs = scm.list_merged_changes(since)
    issues = scm.list_issues([], state="all")
    runs = scm.list_pipeline_runs(since)
    agents = [re.sub(r"\[bot\]$", "", a["account"]) for a in load_policy("agents")["agents"]]
    print(report(prs, issues, runs, since, until, agents=[*agents, "app/tiima-factory"]))
