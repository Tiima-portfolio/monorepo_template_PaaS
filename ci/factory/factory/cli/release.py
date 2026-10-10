#!/usr/bin/env python3
"""Release controller, run by .github/workflows/release.yml on every push to
main. It walks main in history order from a cursor, so a run that is
cancelled or starts late loses nothing: the next run picks up from the
cursor. The cursor lives in the body of a draft release, not in a git ref:
GitHub won't let GITHUB_TOKEN point a ref at an older commit once workflow
files have changed since. For each release it publishes the artifact first (a
draft GitHub release with its files, and the image in the registry) and only
then publishes the release, which creates the <service>/v<version> tag.

Env: GITHUB_REPOSITORY, GH_TOKEN, FACTORY_GIT_USER, FACTORY_REGISTRY_TOKEN, FACTORY_REGISTRY (default
ghcr.io/<owner>/<repo>), FACTORY_DRY_RUN=true to only print the plan.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from ..release import plan_releases
from .common import env, git, lines, set_git_identity, to_json

CURSOR = "factory-release-cursor"
LEGACY_CURSOR_TAG = "factory/release-cursor"
ARTIFACT = re.compile(r"\.(tgz|tar\.gz|whl|tar)$")
REFUSED = re.compile(r"Resource not accessible by integration|refusing to allow")


def sh(*args, show=False, extra_env=None) -> str:
    """Runs a command; with show=True its output goes to the log."""
    run_env = {**os.environ, **(extra_env or {})}
    if show:
        subprocess.run(args, check=True, env=run_env)
        return ""
    return subprocess.run(args, check=True, capture_output=True, text=True, env=run_env).stdout.strip()


def gh(*args) -> None:
    """gh with stderr captured (and echoed), so a refusal can be recognised."""
    r = subprocess.run(["gh", *args], stdout=None, stderr=subprocess.PIPE, text=True)
    if r.returncode:
        sys.stderr.write(r.stderr)
        raise subprocess.CalledProcessError(r.returncode, ["gh", *args], stderr=r.stderr)


def try_run(fn):
    try:
        return fn()
    except (subprocess.CalledProcessError, ValueError, OSError):
        return None


def releasable_projects() -> dict:
    sh("npx", "nx", "graph", "--file=.release-graph.json")
    nodes = json.loads(Path(".release-graph.json").read_text())["graph"]["nodes"]
    Path(".release-graph.json").unlink()
    out = {}
    for name, n in nodes.items():
        tags = n["data"].get("tags") or []
        shipped = "boundary:product" in tags or "boundary:internal-services" in tags
        if shipped and (n["data"].get("targets") or {}).get("package"):
            out[name] = n["data"]["root"]
    return out


def main(argv):
    dry = env.get("FACTORY_DRY_RUN") == "true"
    if not dry:
        set_git_identity()
    repo = env.get("GITHUB_REPOSITORY") or ""
    registry = env.get("FACTORY_REGISTRY") or f"ghcr.io/{repo.lower()}"
    start = git("rev-parse", "HEAD")

    # Cursor state: {sha, pending: [release]} in the draft release's body. A
    # draft has no tag, so GitHub reports an "untagged-..." tag name; find it by
    # its name instead.
    def read_cursor():
        query = f'[.[] | select(.draft and .name == "{CURSOR}")] | sort_by(.created_at) | last'
        rel = None if dry else try_run(lambda: json.loads(sh("gh", "api", f"repos/{repo}/releases", "--paginate", "--jq", query) or "null"))
        if rel and rel.get("body"):
            return {"id": rel["id"], **json.loads(rel["body"])}
        legacy = try_run(lambda: git("rev-parse", "-q", "--verify", f"refs/tags/{LEGACY_CURSOR_TAG}^{{commit}}"))
        return {"id": (rel or {}).get("id"), "sha": legacy or None, "pending": []}

    def write_cursor(state):
        body = to_json({"sha": state["sha"], "pending": state["pending"]}, indent=None)
        if state.get("id"):
            sh("gh", "api", "-X", "PATCH", f"repos/{repo}/releases/{state['id']}", "-f", f"body={body}")
        else:
            created = json.loads(sh("gh", "api", f"repos/{repo}/releases", "-f", f"tag_name={CURSOR}", "-f", f"name={CURSOR}",
                                    "-F", "draft=true", "-f", f"body={body}"))
            state["id"] = created["id"]

    cursor_state = read_cursor()
    cursor = cursor_state.get("sha")
    shas = lines(git("rev-list", "--reverse", "--first-parent", f"{cursor}..HEAD")) if cursor else [start]
    print(f"Cursor at {cursor[:12]}; {len(shas)} new commit(s) on main." if cursor else "No cursor yet; starting from HEAD.")

    projects = releasable_projects()
    commits = []
    for sha in shas:
        parent = try_run(lambda: git("rev-parse", f"{sha}^"))
        affected = json.loads(sh("npx", "nx", "show", "projects", "--affected", f"--base={parent}", f"--head={sha}", "--json")) if parent else list(projects)

        # The graph is today's; keep only projects that already existed at this commit.
        def existed(p):
            return try_run(lambda: sh("git", "cat-file", "-e", f"{sha}:{projects[p]}/service.yaml")) is not None

        files = lines(git("diff", "--name-only", parent, sha)) if parent else []
        # A rerun after a partial failure skips services already released from this commit.
        done = {t.split("/v")[0] for t in lines(git("tag", "--points-at", sha, "*/v*"))}
        kept = [p for p in affected if p in projects and existed(p) and p not in done]
        changed = [p for p in kept if any(f.startswith(f"{projects[p]}/") for f in files)] if parent else kept
        commits.append({"sha": sha, "title": git("log", "-1", "--format=%s", sha), "affected": kept, "changed": changed})
    tags = lines(git("tag", "-l", "*/v*"))
    plan = plan_releases(commits, tags)
    print("\n".join(f"- {r['tag']} from {r['sha'][:12]} ({r['bump']})" for r in plan) if plan else "Nothing to release.")
    if dry:
        return 0

    releases = json.loads(sh("gh", "release", "list", "--repo", repo, "--limit", "1000", "--json", "tagName,isDraft") or "[]")

    def state(tag):
        return next((r for r in releases if r["tagName"] == tag), None)

    def changelog(service, root, sha):
        prev = [t for t in tags if t.startswith(f"{service}/v")]
        rng = f"{prev[-1]}..{sha}" if prev else sha
        return "\n".join(lines(git("log", "--format=- %s (%h)", rng, "--", root))) or "- First release"

    refused = []
    released_now = []

    def publish(r):
        existing = state(r["tag"])
        if existing and not existing["isDraft"]:
            print(f"{r['tag']} already published")
            return
        root = projects[r["service"]]
        # Packaging stamps versions into tracked files; start each release clean.
        git("reset", "-q", "--hard")
        git("checkout", "-q", r["sha"])
        sh("npx", "nx", "run", f"{r['service']}:package", "--skip-nx-cache", show=True, extra_env={"FACTORY_VERSION": r["version"]})
        dist = Path(root, "dist")
        files = [str(dist / f) for f in sorted(os.listdir(dist)) if ARTIFACT.search(f)] if dist.exists() else []
        # Artifact first: the image in the registry and the files on a draft release.
        for f in (x for x in files if x.endswith("-image.tar")):
            # An OCI layout has an oci-layout file; otherwise it's a docker save archive.
            fmt = "oci-archive" if "oci-layout" in sh("tar", "-tf", f).split("\n") else "docker-archive"
            creds = f"{env.get('GITHUB_ACTOR')}:{env.get('FACTORY_REGISTRY_TOKEN') or env.get('GH_TOKEN')}"
            sh("skopeo", "copy", "--dest-creds", creds, f"{fmt}:{f}", f"docker://{registry}/{r['service']}:{r['version']}", show=True)
        assets = [x for x in files if not x.endswith("-image.tar")]
        if not existing:
            gh("release", "create", r["tag"], "--repo", repo, "--draft", "--target", r["sha"], "--title", r["tag"],
               "--notes", changelog(r["service"], root, r["sha"]), *assets)
        elif assets:
            gh("release", "upload", r["tag"], "--repo", repo, "--clobber", *assets)
        # Then the tag: publishing the draft creates <service>/v<version>.
        gh("release", "edit", r["tag"], "--repo", repo, "--draft=false")
        tags.append(r["tag"])
        released_now.append({"service": r["service"], "version": r["version"], "tag": r["tag"], "sha": r["sha"]})
        print(f"Released {r['tag']}")

    # GitHub refuses a release on an older commit when the workflow files have
    # changed since, unless the token may write workflows (GITHUB_TOKEN can't).
    # Without the factory App's token such a release is skipped with a warning
    # instead of blocking every later release.
    def try_publish(r):
        try:
            publish(r)
        except subprocess.CalledProcessError as e:
            if not REFUSED.search(f"{e}\n{e.stderr or ''}"):
                raise
            refused.append(r)
            print(f"::warning::GitHub refused to create {r['tag']} with this token. Set the FACTORY_APP_ID and "
                  "FACTORY_APP_PRIVATE_KEY secrets (a GitHub App with contents and workflows write); the next run releases it.")

    try:
        # Releases refused earlier are retried first, in case a token is now set.
        retry = cursor_state.get("pending") or []
        cursor_state["pending"] = []
        for r in retry:
            if not state(r["tag"]) or state(r["tag"])["isDraft"]:
                try_publish(r)
        for c in commits:
            for r in (x for x in plan if x["sha"] == c["sha"]):
                try_publish(r)
            cursor_state["sha"] = c["sha"]
            cursor_state["pending"] = refused
            write_cursor(cursor_state)
        if not commits and retry:
            cursor_state["pending"] = refused
            write_cursor(cursor_state)
        # Reconcile: a published tag whose release is still a draft gets published.
        for r in (x for x in releases if x["isDraft"] and not any(p["tag"] == x["tagName"] for p in plan)):
            if try_run(lambda: git("rev-parse", "-q", "--verify", f"refs/tags/{r['tagName']}")):
                gh("release", "edit", r["tagName"], "--repo", repo, "--draft=false")
                print(f"Reconciled {r['tagName']}")
            else:
                print(f"::warning::Draft release {r['tagName']} has no tag yet; it will be published when its commit is released.")
        if refused:
            print(f"Waiting for the factory App token: {', '.join(r['tag'] for r in refused)}")
    finally:
        git("reset", "-q", "--hard")
        git("checkout", "-q", start)
        # For the promotion bot.
        Path("released.json").write_text(to_json(released_now))
    return 0
