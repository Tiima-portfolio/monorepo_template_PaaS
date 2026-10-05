"""Evidence collector, run by .github/workflows/evidence.yml on every push to
main, on the main runner pool and with base-branch code. It finds the PR the
commit came from, takes that PR's last admitted evidence bundle, checks it,
links it to the main commit and stores the result.

Env: GITHUB_REPOSITORY, GITHUB_SHA, GH_TOKEN, FACTORY_EVIDENCE_KEY (optional
HMAC key), FACTORY_EVIDENCE_S3_URI (optional, e.g. s3://factory-evidence).
"""

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ..collect import index_sql, link_to_main, sign
from .admission import now_iso
from .common import append, env, git, read_json, run, write_json


def try_run(fn):
    try:
        return fn()
    except (subprocess.CalledProcessError, ValueError):
        return None


def main(argv):
    repo = env.get("GITHUB_REPOSITORY")
    sha = env.get("GITHUB_SHA")
    main_commit = {"sha": sha, "tree": git("rev-parse", f"{sha}^{{tree}}")}
    pr = try_run(lambda: json.loads(run("gh", "api", f"repos/{repo}/commits/{sha}/pulls", "--jq",
                                        "[.[] | select(.merged_at != null)] | first | {number, head: .head.sha}")))

    pr_bundle = None
    if not (pr or {}).get("number"):
        # A commit on main without a PR bypassed the factory: break-glass.
        result = {"ok": False, "tree_match": False, "problems": ["commit reached main without a PR: recorded as a break-glass override"]}
    else:
        run_id = try_run(lambda: run("gh", "api", f"repos/{repo}/actions/workflows/factory.yml/runs?head_sha={pr['head']}&event=pull_request&per_page=30",
                                     "--jq", '[.workflow_runs[] | select(.conclusion == "success")] | first | .id').strip())
        folder = tempfile.mkdtemp(prefix="evidence-", dir=".")
        if run_id and run_id != "null":
            try_run(lambda: run("gh", "run", "download", run_id, "--repo", repo, "-n", "factory-evidence", "-D", folder))
        pr_bundle = read_json(Path(folder, "bundle.json"))
        result = link_to_main(pr_bundle, main_commit, pr["head"])

    body = {
        "version": 1,
        "main": main_commit,
        "pr": (pr or {}).get("number"),
        "pr_head": (pr or {}).get("head"),
        "linked": result["ok"] and result["tree_match"],
        "tree_match": result["tree_match"],
        "problems": result["problems"],
        "pr_bundle": pr_bundle,
        "collected_at": now_iso(),
    }
    key = env.get("FACTORY_EVIDENCE_KEY")
    write_json("main-bundle.json", {**body, "signature": sign(body, key) if key else None})

    bundle_uri = None
    if env.get("FACTORY_EVIDENCE_S3_URI"):
        bundle_uri = f"{env['FACTORY_EVIDENCE_S3_URI']}/{datetime.now(timezone.utc).strftime('%Y-%m')}/{sha}.json"
        run("aws", "s3", "cp", "main-bundle.json", bundle_uri)
        print(f"Stored {bundle_uri}")
    # For the evidence index; the workflow runs it when a database is configured.
    fallback = f"{env.get('GITHUB_SERVER_URL') or 'https://github.com'}/{repo}/actions/runs/{env.get('GITHUB_RUN_ID')}"
    Path("index.sql").write_text(index_sql(body, repo, bundle_uri or fallback))

    out = [
        f"### Evidence for {sha[:12]}",
        "",
        f"From PR #{pr['number']} (head {pr['head'][:12]})." if (pr or {}).get("number") else "No PR found for this commit.",
        f"Tree match with the verified commit: {'yes' if result['tree_match'] else 'no'}.",
    ]
    if result["problems"]:
        out += ["", *(f"- {p}" for p in result["problems"])]
    append("GITHUB_STEP_SUMMARY", "\n".join(out) + "\n")
    print("\n".join(out))
    if not result["tree_match"] and result["ok"]:
        print("::warning::main differs from the commit the PR verified; the full checks should run again on main.")
    if not result["ok"]:
        print(f"::error::{'; '.join(result['problems'])}")
        return 1
    return 0
