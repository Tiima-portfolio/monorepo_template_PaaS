#!/usr/bin/env python3
"""Evidence collector checks: links a PR's evidence bundle to the commit that
landed on main."""

import hashlib
import hmac
import json

from .identity import identity_problems


def _stringify(value) -> str:
    """JSON as JavaScript's JSON.stringify writes it, so digests match."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def digest(record: dict) -> str:
    rest = {k: v for k, v in record.items() if k != "digest"}
    return hashlib.sha256(_stringify(rest).encode()).hexdigest()


def link_to_main(bundle, main, pr_head, main_identity=None) -> dict:
    """bundle: the PR's last admitted bundle. main: {sha, tree}. pr_head: PR head sha."""
    if not bundle:
        return {"ok": False, "tree_match": False, "problems": ["no evidence bundle found for the PR"]}
    problems = []
    if bundle.get("sha") != pr_head:
        problems.append(f"bundle is for {(bundle.get('sha') or '')[:12]}, PR head is {pr_head[:12]}")
    if not (bundle.get("decision") or {}).get("allowed"):
        problems.append("the bundle records a blocked decision")
    path = (bundle.get("run") or {}).get("path")
    if path and not path.startswith(".github/workflows/factory.yml"):
        problems.append(f"bundle came from {path}")
    for r in bundle.get("records") or []:
        if r.get("digest") and r["digest"] != digest(r):
            problems.append(f"record {r['check']} was altered")
    # Without a merge queue the squash commit can differ from what was verified,
    # if main moved on. Only an exact tree match carries the evidence over.
    tree_match = bool(bundle.get("tree")) and bundle.get("tree") == main.get("tree")
    result = {"ok": not problems, "tree_match": tree_match, "problems": problems}
    if main_identity is not None and bundle.get("identity"):
        # Evidence made under another policy or factory version is not evidence for main's rules.
        stale = identity_problems(bundle["identity"], main_identity["policy"], main_identity["validator"])
        result["identity_match"] = not stale
        result["identity_problems"] = stale
    return result


def sign(body, key: str) -> str:
    return hmac.new(key.encode(), _stringify(body).encode(), hashlib.sha256).hexdigest()


def _lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def index_sql(body, repo, bundle_uri) -> str:
    """SQL for the evidence index (platform/evidence/schema.sql): a row per check
    in the PR's bundle and one for the decision."""
    b = body.get("pr_bundle") or {}
    rows = [(r.get("check"), r.get("status"), r.get("details")) for r in b.get("records") or []]
    decision = b.get("decision") or {}
    rows.append(("admission", "allowed" if decision.get("allowed") else "blocked",
                 ", ".join(decision.get("blocking") or []) or "; ".join(body["problems"])))
    values = [
        "(" + ", ".join(_lit(v) for v in (repo, body["main"]["sha"], body.get("pr"), body.get("pr_head"), check, status,
                                          details, b.get("tier"), body.get("tree_match"), bundle_uri)) + ")"
        for check, status, details in rows
    ]
    return ("INSERT INTO evidence (repo, main_sha, pr, pr_head, check_name, status, details, tier, tree_match, bundle_uri) VALUES\n"
            + ",\n".join(values) + "\nON CONFLICT (repo, main_sha, check_name) DO NOTHING;\n")
