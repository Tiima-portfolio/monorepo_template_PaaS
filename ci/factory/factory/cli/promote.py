#!/usr/bin/env python3
"""Promotion bot, run by the release workflow after releases with the factory
App's token. For every pins.yaml whose consumer pins an older version of a
service released in this run, it opens one bump PR, labelled ready and P4,
so the queue controller merges it once the consumer's own checks pass.
Promotion of a service with an open escape issue is on hold.

Env: GITHUB_REPOSITORY, GH_TOKEN (pushes with it too, so the bump PRs start
the factory), FACTORY_GIT_USER. Reads released.json.
"""

from pathlib import Path

from ..policy import load_policy
from ..promote import bump_title, on_hold, plan_promotions, set_pin
from ..scm import get_scm
from .common import env, git, lines, read_json, read_yaml, set_git_identity


def main(argv):
    released = read_json("released.json", [])
    if not released:
        print("Nothing released; nothing to promote.")
        return 0

    pins_files = [{"path": p, "pins": (read_yaml(p) or {}).get("pins") or {}}
                  for p in lines(git("ls-files", "*pins.yaml")) if p.endswith("/pins.yaml")]
    scm = get_scm()
    escapes = [i["title"] for i in scm.list_issues(["escape"])]
    holds = [r["service"] for r in released if on_hold(r["service"], escapes)]
    for s in holds:
        print(f"::warning::Promotion of {s} is on hold: it has an open escape.")

    set_git_identity()
    if env.get("GITHUB_ACTIONS") == "true" and env.get("GH_TOKEN"):
        git("remote", "set-url", "origin", f"https://x-access-token:{env['GH_TOKEN']}@github.com/{env['GITHUB_REPOSITORY']}.git")
    boundaries = load_policy("boundaries")
    start = git("rev-parse", "HEAD")
    for b in plan_promotions(pins_files, released, holds):
        consumer = str(Path(b["path"]).parent)
        branch = f"promote/{consumer.replace('/', '-')}-{b['service']}-{b['to']}"
        if git("ls-remote", "--heads", "origin", branch):
            print(f"{branch} already exists")
            continue
        git("checkout", "-q", "-B", branch, start)
        pins = Path(b["path"])
        pins.write_text(set_pin(pins.read_text(), b["service"], b["to"]))
        title = bump_title(b["path"], b["service"], b["to"], boundaries)
        git("commit", "-q", "-am", f"{title}\n\nPromotes: {b['service']}@{b['to']}")
        git("push", "-q", "origin", branch)
        body = (f"{b['service']} released {b['to']}; {consumer} pinned {b['from']}. This bump runs {consumer}'s own checks "
                f"and merges through the queue as P4.\n\nPromotes: {b['service']}@{b['to']}")
        url = scm.open_change(branch, title, body, ["ready", "P4"])
        print(f"Opened {url}")
    git("checkout", "-q", start)
