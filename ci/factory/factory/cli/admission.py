"""Admission, run by .github/workflows/factory.yml after the gate and verify
jobs. Reads gate.json and every evidence record under FACTORY_IN, decides,
writes the summary and exits non-zero when the merge is blocked."""

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..admission import decide
from ..budgets import feedback_budget
from ..owners import approvals_met
from ..policy import load_policy
from .common import append, env, read_json, to_json, write_json


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main(argv):
    folder = Path(env.get("FACTORY_IN") or "factory-in")
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    gate_file = next((f for f in files if f.name == "gate.json"), None)
    if not gate_file:
        print("No gate.json found: the gate job did not finish.", file=sys.stderr)
        return 1
    gate = read_json(gate_file)
    records = [read_json(f) for f in files if "evidence" in f.parent.parts and f.suffix == ".json"]

    # owner-approval: the routed approvals against the PR's current approvals.
    approvers = read_json(env.get("FACTORY_APPROVERS_FILE"))
    if approvers is not None and gate.get("approvals") is not None:
        met = approvals_met(gate["approvals"], approvers, load_policy("teams"), author=gate.get("author"), requester=gate.get("requester"))
        waiting = "; ".join(f"{m['service']}: {' or '.join(m['teams'])}" for m in met["missing"])
        records.append({
            "check": "owner-approval", "status": "pass" if met["ok"] else "fail", "sha": gate["sha"],
            "details": f"approved by {', '.join(approvers) or 'nobody needed'}" if met["ok"] else f"waiting for {waiting}",
        })
    jobs = read_json(env.get("FACTORY_JOBS_FILE"))
    run = read_json(env.get("FACTORY_RUN_FILE"))
    if run and run.get("run_started_at") and gate.get("tier"):
        b = feedback_budget(gate["tier"], run["run_started_at"], datetime.now(timezone.utc), load_policy("budgets"))
        records.append({"check": "time-budget", "status": "pass" if b["ok"] else "fail", "sha": gate["sha"],
                        "details": f"{b['minutes']} min for {gate['tier']}, budget {b['budget']}, hard limit {b['hard']}"})
    result = decide(gate["sha"], gate["tier"], gate["required"], records, needs_human=gate.get("needsHuman", False),
                    override=gate.get("override", False), reasons=gate.get("reasons") or [], jobs=jobs, run=run,
                    affected=gate.get("affected") or [])
    out = Path(env.get("FACTORY_OUT") or ".")
    (out / "admission.md").write_text(result["summary"] + "\n")
    write_json(out / "admission.json", {"allowed": result["allowed"], "blocking": result["blocking"], "tier": gate["tier"], "sha": gate["sha"]})
    # The evidence bundle for this commit: what was required, what was present,
    # what GitHub says the jobs did, and the decision.
    run_info = {k: v for k, v in (("id", env.get("GITHUB_RUN_ID")), ("attempt", env.get("GITHUB_RUN_ATTEMPT"))) if v is not None}
    bundle = {
        "version": 1,
        "sha": gate["sha"],
        "tree": gate.get("tree"),
        "event": gate.get("event"),
        "run": {**run_info, **(run or {})},
        "jobs": jobs or [],
        "tier": gate["tier"],
        "reasons": gate.get("reasons"),
        "boundary": gate.get("boundary"),
        "override": gate.get("override"),
        "required": gate["required"],
        "records": [{**r, "digest": hashlib.sha256(to_json(r, indent=None).encode()).hexdigest()} for r in records],
        "decision": {"allowed": result["allowed"], "blocking": result["blocking"]},
        "decided_at": now_iso(),
    }
    write_json(out / "bundle.json", bundle)
    append("GITHUB_STEP_SUMMARY", result["summary"] + "\n")
    print(result["summary"])
    return 0 if result["allowed"] else 1
