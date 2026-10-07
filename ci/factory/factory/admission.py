"""Admission: allow or block a merge by comparing the evidence present for a
commit with the evidence its risk tier requires.

A record is {check, status: "pass" | "fail" | "skipped", sha, details?}.
Only records for the exact commit being judged count.
"""

ICON = {"pass": "✅", "fail": "❌", "missing": "⚪", "skipped": "➖"}


def decide(sha, tier, required, records, needs_human=False, override=False, reasons=(), jobs=None, run=None, affected=()) -> dict:
    rows = []
    blocking = []
    for req in required:
        rec = next((r for r in records if r["check"] == req["name"] and r["sha"] == sha), None)
        stale = not rec and any(r["check"] == req["name"] for r in records)
        status = rec["status"] if rec else "missing"
        # The factory skips a check only when it doesn't apply (nothing affected,
        # or a check switched off in policy).
        ok = status in ("pass", "skipped")
        if not ok and req["mode"] == "enforce":
            blocking.append(f"{req['name']} (evidence is for another commit)" if stale else f"{req['name']} ({status})")
        details = (rec or {}).get("details") or ("evidence is for another commit" if stale else "")
        rows.append({**req, "status": status, "details": details})
    if needs_human:
        approval = next((r for r in records if r["check"] == "human-approval" and r["status"] == "pass"), None)
        rows.append({"name": "human-approval", "mode": "enforce", "about": "Agent PR above its trust level",
                     "status": "pass" if approval else "missing", "details": (approval or {}).get("details") or ""})
        if not approval:
            blocking.append("human-approval (missing)")
    # Pass or fail comes from GitHub's own record of the jobs, not only from the
    # records the jobs wrote.
    if jobs is not None:
        blocking += job_problems(sha, jobs, run, affected)
    allowed = not blocking
    would_block = [r["name"] for r in rows if r.get("example_mode") == "enforce" and r["mode"] != "enforce" and r["status"] not in ("pass", "skipped")]
    return {"allowed": allowed, "blocking": blocking, "rows": rows,
            "would_block": would_block, "summary": _summary(sha, tier, reasons, override, rows, allowed, blocking, would_block)}


def job_problems(sha, jobs, run=None, affected=()) -> list[str]:
    """jobs: [{name, conclusion}] from the GitHub API for this run.
    run: {path, head_sha} of this workflow run."""
    problems = []

    def job(name):
        return next((j for j in jobs if j["name"] == name), None)

    gate = job("factory/gate")
    if not gate or gate["conclusion"] != "success":
        problems.append(f"factory/gate job {gate['conclusion'] if gate else 'missing'}")
    verify = job("factory/verify")
    expected = ["success"] if affected else ["success", "skipped"]
    if not verify or verify["conclusion"] not in expected:
        problems.append(f"factory/verify job {verify['conclusion'] if verify else 'missing'}")
    if run:
        if run.get("path") and not run["path"].startswith(".github/workflows/factory.yml"):
            problems.append(f"evidence came from {run['path']}, not the factory workflow")
        if run.get("head_sha") and run["head_sha"] != sha:
            problems.append("workflow run is for another commit")
    return problems


def _summary(sha, tier, reasons, override, rows, allowed, blocking, would_block=()) -> str:
    because = f" ({'; '.join(reasons)})" if reasons else ""
    lines = [
        f"### Factory admission: {'allowed' if allowed else 'blocked'}",
        "",
        f"Risk tier **{tier}**{because}. Commit `{sha[:12]}`.",
    ]
    if override:
        lines += ["", "⚠️ Boundary override in use; this is recorded with the evidence."]
    lines += ["", "| Evidence | Mode | Result | Details |", "| --- | --- | --- | --- |"]
    for r in rows:
        text = (r.get("details") or r.get("about") or "").replace("|", "\\|")
        lines.append(f"| {r['name']} | {r['mode']} | {ICON.get(r['status'], '')} {r['status']} | {text} |")
    if not allowed:
        lines += ["", f"Blocked by: {', '.join(blocking)}."]
    lines += ["", "Shadow evidence is reported but never blocks."]
    if would_block:
        lines += ["", f"For information: the `production-example` profile would also block on {', '.join(would_block)}. It is not active here."]
    return "\n".join(lines)
