"""Factory gate, run by .github/workflows/factory.yml.

Works out the PR's boundary, risk tier and required evidence, records the
gate's own evidence, and writes the toolchain setup for the verify job.

Env: FACTORY_BASE, FACTORY_HEAD (commits to compare), FACTORY_SHA (commit
the evidence is for), FACTORY_OUT (output dir), GITHUB_EVENT_NAME,
GITHUB_EVENT_PATH, FACTORY_OVERRIDE_OK ("true" when a factory owner added
the override label).
"""

import json
import re
import sys
from pathlib import Path

from ..backpressure import agent_backpressure
from ..boundary import check_boundary
from ..checks import check_history, check_provenance, check_title
from ..contracts import contract_problems
from ..deps import check_dependencies
from ..evidence import required_evidence
from ..flaky import active_quarantine
from ..graph import affected as affected_projects
from ..graph import build_graph, owners_of, project_files
from ..identity import build_identity
from ..identity import environment as identity_environment
from ..identity import policy_version, toolchain_version, validator_version
from ..references import undeclared
from ..guardrails import agent_guardrails, owner_checks
from ..mise import mise_toml
from ..network import network_problems
from ..owners import route
from ..policy import CODE_DIR, load_policy, policy_dir
from ..risk import classify, test_only
from ..test_quality import lint_test_file
from .common import append, env, evidence_dir, git, git_text, git_yaml, lines, out_dir, read_json, run, to_json, write_json, write_record


def affected(files, base, head):
    """Affected projects, their criticality and toolchains, from the project
    declarations in git. Nothing from the PR is executed: see graph.py."""
    graph, base_graph = build_graph(head), build_graph(base)
    names = affected_projects(files, graph, base_graph)
    tags = [t for n in names for t in graph["nodes"][n]["data"]["tags"]]

    def pick(prefix):
        return list(dict.fromkeys(t[len(prefix):] for t in tags if t.startswith(prefix)))

    return {"names": names, "nodes": graph["nodes"], "graph": graph, "criticalities": pick("criticality:"), "toolchains": pick("toolchain:")}


def main(argv):
    out = out_dir()
    base = env.get("FACTORY_BASE")
    head = env.get("FACTORY_HEAD") or "HEAD"
    sha = env.get("FACTORY_SHA") or head
    event_name = env.get("GITHUB_EVENT_NAME") or "pull_request"
    event = read_json(env.get("GITHUB_EVENT_PATH"), {})
    pr = event.get("pull_request") or {}
    author = (pr.get("user") or {}).get("login")
    labels = [label["name"] for label in pr.get("labels") or []]

    evidence_dir()
    records = []

    def record(check, ok, details, status=None):
        rec = write_record(check, status or ("pass" if ok else "fail"), details, sha)
        records.append(rec)

    files = lines(git("diff", "--name-only", f"{base}...{head}"))
    commits = []
    for line in lines(git("log", "--format=%H %P", f"{base}..{head}")):
        c, *parents = line.split(" ")
        commits.append({"sha": c, "parents": parents, "message": git("log", "-1", "--format=%B", c)})

    is_pr = event_name == "pull_request"
    override = is_pr and load_policy("boundaries")["override"]["label"] in labels and env.get("FACTORY_OVERRIDE_OK") == "true"

    # PR-level checks. In the merge queue a group spans several PRs, each already
    # checked on its own, so these are carried as passed.
    boundary = {"ok": True, "boundary": None, "message": "Checked on each PR"}
    title = {"ok": True, "bump": "none", "message": "Checked on each PR"}
    provenance = {"ok": True, "needs_human": False, "raise": [], "message": "Checked on each PR"}
    if is_pr:
        boundary = check_boundary(files, load_policy("boundaries"), override=override)
        title = check_title(pr.get("title"))
    history = check_history(commits)

    aff = affected(files, base, head)
    deleted = lines(git("diff", "--diff-filter=D", "--name-only", f"{base}...{head}"))
    tests_removed = bool(commits) and any(test_only([f]) for f in deleted)

    def tier_of(raise_=()):
        return classify(files=files, affected_projects=len(aff["names"]), criticalities=aff["criticalities"],
                        override=boundary.get("override", False), major_bump=title["bump"] == "major", raise_=raise_)

    risk = tier_of()
    # Services this PR changes, read from the base branch (owners, guardrails) and
    # from the PR (a new owner), for approval routing.
    touched = []
    for n in (aff["nodes"] or {}).values():
        root = n["data"]["root"]
        head_service = git_yaml(head, f"{root}/service.yaml")
        if not any(f.startswith(f"{root}/") for f in files) or head_service is None:
            continue
        base_service = git_yaml(base, f"{root}/service.yaml")
        touched.append({
            "name": n["name"], "root": root, "boundary": root.split("/")[0],
            "base": {"service": base_service, "guardrails": git_yaml(base, f"{root}/guardrails.yaml") or {}} if base_service else None,
            "head": {"service": head_service},
        })
    routing = {"approvals": [], "raise": [], "owning_teams": []}
    if is_pr:
        provenance = check_provenance(author, commits, files, boundary=boundary.get("boundary"), tier=risk["tier"])
        routing = route(touched, files, author, risk["tier"], load_policy("teams"))
        issues = read_json(env.get("FACTORY_QUARANTINE_FILE"))
        quarantined = active_quarantine(issues) if issues is not None else {}
        in_quarantine = [n for n in aff["names"] if n in quarantined]
        raise_ = provenance["raise"] + routing["raise"] + (["quarantined_tests"] if in_quarantine else [])
        if raise_:
            risk = tier_of(raise_)
    requester = next((m.group(1) for c in commits if (m := re.search(r"^Requested-By:\s*(\S+)", c["message"], re.M))), None)

    record("boundary", boundary["ok"], boundary["message"])
    record("title", title["ok"], title["message"])
    record("history", history["ok"], history["message"])

    # Air-gap check on the lines this PR adds.
    added = {}
    file = None
    for line in git("diff", "-U0", f"{base}...{head}").split("\n"):
        if line.startswith("+++ "):
            file = line[6:] if line.startswith("+++ b/") else None
            if file:
                added[file] = []
        elif file and line.startswith("+"):
            added[file].append(line[1:])
    network = load_policy("network")
    if not network.get("air_gapped"):
        record("network", True, "air-gap check is off (air_gapped: false in ci/policy/network.yaml)", status="skipped")
    else:
        problems = network_problems(added, network)
        record("network", not problems, "; ".join(problems[:10]) if problems else "only allowed package and image hosts")

    # Lead time and escapes are reported per feature as well as per service.
    feature_id = next((m.group(1) for t in [pr.get("body") or "", *(c["message"] for c in commits)]
                       if (m := re.search(r"^Feature-Id:\s*(\S+)", t, re.M))), None)
    record("feature-id", not is_pr or bool(feature_id),
           "checked on each PR" if not is_pr else f"Feature-Id: {feature_id}" if feature_id else "add a Feature-Id: line to the PR description")
    record("provenance", provenance["ok"], provenance["message"])

    texts = {f: git_text(head, f) for f in files}
    problems = [p for f, text in texts.items() if text is not None for p in lint_test_file(f, text)]
    record("test-quality", not problems, "; ".join(problems) if problems else "no skipped or assertion-free tests in changed files")

    if aff["nodes"] is not None:
        # Contract coverage for the affected projects that are services.
        services = []
        for n in aff["names"]:
            root = ((aff["nodes"].get(n) or {}).get("data") or {}).get("root")
            service = git_yaml(head, f"{root}/service.yaml") if root else None
            if service is not None:
                services.append({"name": Path(root).name, "root": root, "service": service,
                                 "files": [f[len(root) + 1:] for f in lines(git("ls-tree", "-r", "--name-only", head, "--", root))]})
        problems = contract_problems(services)
        record("contract-tests", not problems, "; ".join(problems) if problems else
               "declared contracts exist and every consumes edge has a contract test" if services else "no affected services")
    if aff["graph"]:
        problems = [*aff["graph"]["unresolved"], *check_dependencies(aff["graph"])]
        record("dependency-rules", not problems, "; ".join(problems) if problems else "dependency directions and no cycles")
        # The affected set only knows declared dependencies: look for real ones nobody declared.
        scanned = {n: project_files(head, aff["graph"]["nodes"][n]["data"]["root"]) for n in owners_of(files, aff["graph"])}
        missing = undeclared(aff["graph"], scanned)
        shown = [f"{r['source']} uses {r['target']} ({r['kind']} in {r['file']})" for r in missing]
        record("declared-dependencies", not missing, "; ".join(shown[:10]) if shown else "every reference between projects is declared")

    # With nothing affected the verify job doesn't run; say so in the evidence.
    if not aff["names"]:
        for check in ("format-lint", "build", "unit-tests"):
            record(check, True, "nothing affected", status="skipped")

    # Owners' required checks, and their rules for agents.
    checks = owner_checks(touched, files)
    if is_pr and provenance.get("is_agent"):
        g = agent_guardrails(touched, files, risk["tier"])
        if not g["ok"]:
            provenance = {**provenance, "ok": False, "message": f"{provenance['message']}; {'; '.join(g['problems'])}"}
        if g["needs_human"]:
            provenance = {**provenance, "needs_human": True}
        record("provenance", provenance["ok"], provenance["message"])
    # Backpressure on agents: open-PR caps and the sponsor's review budget.
    if is_pr and provenance.get("is_agent") and env.get("GITHUB_REPOSITORY"):
        try:
            open_prs = [{**p, "author": (p.get("author") or {}).get("login")} for p in json.loads(run(
                "gh", "pr", "list", "--repo", env["GITHUB_REPOSITORY"], "--state", "open", "--limit", "500", "--json", "number,author,reviewDecision"))]
            agents = [{**a, "login": re.sub(r"\[bot\]$", "", a["account"])} for a in load_policy("agents")["agents"]]
            agent = next((a for a in agents if author in (a["account"], a["login"])), None)
            problems = agent_backpressure(agent, open_prs, agents, load_policy("teams"), pr.get("number")) if agent else []
            if problems:
                provenance = {**provenance, "ok": False, "message": f"{provenance['message']}; {'; '.join(problems)}"}
                record("provenance", False, provenance["message"])
        except Exception as e:  # noqa: BLE001
            print(f"Could not check agent backpressure: {e}", file=sys.stderr)
    escape_fix = is_pr and "escape-fix" in labels
    required = required_evidence(risk["tier"], agent=bool(provenance.get("is_agent")), tests_removed=tests_removed,
                                 escape_fix=escape_fix, owner_checks=bool(checks))

    # mise config for the toolchains the affected projects use.
    tools = {}
    for tc in aff["toolchains"]:
        tools.update(((git_yaml(head, f"internal-tools/toolchains/{tc}/toolchain.yaml") or {}).get("setup") or {}).get("mise") or {})
    (out / "mise.toml").write_text(mise_toml(tools))

    tree = git("rev-parse", f"{head}^{{tree}}")
    toolchain_specs = {tc: git_yaml(head, f"internal-tools/toolchains/{tc}/toolchain.yaml") or {} for tc in aff["toolchains"]}
    ident = build_identity(env.get("GITHUB_REPOSITORY"), tree, sha, policy_version(policy_dir()), toolchain_version(toolchain_specs),
                           validator_version(CODE_DIR), identity_environment(env))
    gate = {
        "sha": sha, "tree": tree, "identity": ident, "base": base, "head": head, "event": event_name,
        "tier": risk["tier"], "reasons": risk["reasons"], **({"boundary": boundary["boundary"]} if "boundary" in boundary else {}),
        "override": bool(boundary.get("override")), "needsHuman": provenance["needs_human"], "affected": aff["names"],
        "toolchains": aff["toolchains"], "files": len(files), "required": required,
        "author": author, "requester": requester, "ownerChecks": checks, "approvals": routing["approvals"],
        "owningTeams": routing["owning_teams"],
    }
    write_json(out / "gate.json", gate)

    reasons = "; ".join(risk["reasons"]) or "default"
    summary = [
        "### Factory gate",
        "",
        f"Tier **{risk['tier']}** ({reasons}). {len(files)} changed file(s), {len(aff['names'])} affected project(s).",
        "",
        *(f"- {'✅' if r['status'] == 'pass' else '❌'} {r['check']}: {r['details']}" for r in records),
    ]
    if routing["approvals"]:
        summary += ["", "Approvals needed:", *(f"- {a['service']}: {' or '.join(a['teams'])} ({a['reason']})" for a in routing["approvals"])]
    text = "\n".join(summary)
    append("GITHUB_STEP_SUMMARY", text + "\n")
    print(text)

    hard = load_policy("budgets")["feedback"][risk["tier"]]["hard"]
    append("GITHUB_OUTPUT", "".join([
        f"tier={risk['tier']}\n", f"affected={len(aff['names'])}\n", f"has_tools={to_json(bool(tools))}\n",
        f"escape_fix={to_json(escape_fix)}\n", f"hard_minutes={hard}\n",
        f"owner_checks={' '.join(c['project'] + ':' + c['target'] for c in checks)}\n",
    ]))
    # The gate never fails the job itself: admission decides, so the PR shows one
    # clear verdict with every reason in it.
