"""Fetches last week's PRs, issues and factory runs and prints the report.
Env: GITHUB_REPOSITORY, GH_TOKEN, FACTORY_METRICS_DAYS (default 7)."""

import json
import re
from datetime import datetime, timedelta, timezone

from ..metrics_report import report
from ..policy import load_policy
from .common import env, run


def iso(t: datetime) -> str:
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def gh(*args):
    return json.loads(run("gh", *args) or "[]")


def main(argv):
    repo = env.get("GITHUB_REPOSITORY")
    now = datetime.now(timezone.utc)
    until = iso(now)
    since = iso(now - timedelta(days=float(env.get("FACTORY_METRICS_DAYS") or 7)))
    prs = [{**p, "author": (p.get("author") or {}).get("login"), "labels": [l["name"] for l in p["labels"]]}
           for p in gh("pr", "list", "--repo", repo, "--state", "merged", "--limit", "1000", "--search", f"merged:>={since[:10]}",
                       "--json", "number,author,createdAt,mergedAt,labels,body")]
    issues = [{**i, "state": i["state"].lower(), "labels": [l["name"] for l in i["labels"]]}
              for i in gh("issue", "list", "--repo", repo, "--state", "all", "--limit", "1000", "--json", "title,labels,createdAt,closedAt,state")]
    runs = gh("run", "list", "--repo", repo, "--workflow", "factory.yml", "--event", "pull_request", "--created", f">={since[:10]}",
              "--limit", "1000", "--json", "conclusion")
    agents = [re.sub(r"\[bot\]$", "", a["account"]) for a in load_policy("agents")["agents"]]
    print(report(prs, issues, runs, since, until, agents=[*agents, "app/tiima-factory"]))
